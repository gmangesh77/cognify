"""Pipeline service construction shared by the API lifespan and the Celery
worker (INFRA-007).

`build_pipeline_services` is a linear, app-free version of the wiring that
`src/api/main.py::_lifespan` performs: PG repos -> orchestrator ->
ResearchService -> ContentDeps -> ContentService -> OutlineGateService.
`resolve_runtime_settings` reproduces the DB API-key resolution and the
LlmConfig overlay so worker runs use the same keys and image provider as
the API. Construction is lazy — repos store the session factory and touch
the DB only on first use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from langchain_core.language_models import BaseChatModel

from src.config.settings import Settings
from src.db.llm_call_repository import PgLlmCallRepository
from src.db.repositories import (
    PgAgentStepRepository,
    PgArticleDraftRepository,
    PgArticleRepository,
    PgResearchSessionRepository,
    PgTopicRepository,
)
from src.services.content import ContentService
from src.services.content.outline_gate import OutlineGateService
from src.services.content_repositories import ContentDeps, ContentRepositories
from src.services.research import (
    ResearchRepositories,
    ResearchService,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.agents.research.runner import LangGraphResearchOrchestrator
    from src.services.embeddings import EmbeddingService
    from src.services.milvus_retriever import MilvusRetriever
    from src.services.research import AgentStepRepository

logger = structlog.get_logger()


class _NoOpOrchestrator:
    """Stub orchestrator used when ANTHROPIC_API_KEY is not set."""

    async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
        return {
            "status": "complete",
            "findings": [],
            "round_number": 1,
            "indexed_count": 0,
        }


def _build_llm(
    settings: Settings,
    llm_call_repo: object | None = None,
) -> BaseChatModel:
    """Build ChatAnthropic LLM instance from settings."""
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(
        model=settings.anthropic_model,  # type: ignore[call-arg]
        api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
        max_tokens=4096,
    )
    if llm_call_repo is not None:
        from src.utils.tracked_llm import TrackedChatModel

        return TrackedChatModel(inner=llm, repo=llm_call_repo)
    return llm


def _get_or_create_embedding_service_from_settings(
    settings: Settings,
) -> EmbeddingService:
    """Create EmbeddingService from settings (no app state)."""
    from src.services.embeddings import EmbeddingService

    return EmbeddingService(model_name=settings.embedding_model)


def _build_real_orchestrator(
    settings: Settings,
    step_repo: AgentStepRepository | None = None,
    llm_call_repo: object | None = None,
) -> LangGraphResearchOrchestrator:
    """Build the full LangGraph research orchestrator."""
    from src.agents.research.literature_review import LiteratureReviewAgent
    from src.agents.research.orchestrator import GraphDeps, build_graph
    from src.agents.research.runner import LangGraphResearchOrchestrator
    from src.agents.research.web_search import WebSearchAgent
    from src.services.semantic_scholar import SemanticScholarClient
    from src.services.serpapi_client import SerpAPIClient
    from src.services.task_dispatch import AsyncIODispatcher

    llm = _build_llm(settings, llm_call_repo=llm_call_repo)
    serpapi = SerpAPIClient(
        api_key=settings.serpapi_api_key,
        base_url=settings.serpapi_base_url,
        timeout=settings.serpapi_timeout,
        results_per_query=settings.serpapi_results_per_query,
    )
    scholar = SemanticScholarClient(
        base_url=settings.semantic_scholar_base_url,
        timeout=settings.semantic_scholar_timeout,
        api_key=settings.semantic_scholar_api_key or None,
    )
    web_agent = WebSearchAgent(serpapi, llm)
    lit_agent = LiteratureReviewAgent(scholar, llm)
    dispatcher = AsyncIODispatcher(timeout_seconds=300.0)

    # Milvus indexing is optional (unavailable on Windows)
    vector_store = None
    embedder = None
    chunker = None
    try:
        from src.services.chunker import TokenChunker
        from src.services.milvus_service import MilvusService

        embedder = _get_or_create_embedding_service_from_settings(settings)
        vector_store = MilvusService(
            uri=settings.milvus_uri,
            collection_name=settings.milvus_collection_name,
        )
        vector_store.ensure_collection()
        chunker = TokenChunker(
            chunk_size=settings.chunk_size_tokens,
            overlap=settings.chunk_overlap_tokens,
        )
    except Exception as exc:
        logger.warning(
            "milvus_indexing_unavailable",
            error=str(exc),
            hint="Research will run without vector indexing.",
        )
    deps = GraphDeps(
        vector_store=vector_store,
        embedder=embedder,
        chunker=chunker,
        step_repo=step_repo,
        llm_call_repo=llm_call_repo,  # type: ignore[arg-type]
    )
    graph = build_graph(llm, dispatcher, web_agent, lit_agent, deps)
    return LangGraphResearchOrchestrator(graph, step_repo)


def _try_build_retriever_from_settings(
    settings: Settings,
) -> MilvusRetriever | None:
    """Build MilvusRetriever if Milvus is available, else None (app-free)."""
    try:
        from src.services.milvus_retriever import MilvusRetriever
        from src.services.milvus_service import MilvusService

        milvus_svc = MilvusService(
            uri=settings.milvus_uri,
            collection_name=settings.milvus_collection_name,
        )
        milvus_svc.ensure_collection()
        embed_svc = _get_or_create_embedding_service_from_settings(settings)
        return MilvusRetriever(milvus_svc, embed_svc)
    except Exception as exc:
        logger.warning("milvus_unavailable", error=str(exc))
        return None


@dataclass(frozen=True)
class PipelineServices:
    """Everything a pipeline run needs, keyed off one session factory."""

    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    research_service: ResearchService
    content_service: ContentService
    outline_gate: OutlineGateService
    llm_call_repo: PgLlmCallRepository
    step_repo: PgAgentStepRepository
    content_repos: ContentRepositories
    article_repo: PgArticleRepository


async def resolve_runtime_settings(
    settings: Settings,
    sf: async_sessionmaker[AsyncSession],
) -> Settings:
    """DB API keys override .env, then the LlmConfig overlay (image
    provider/model chosen in the Settings UI). Mirrors `_lifespan`."""
    from src.db.settings_repositories import PgApiKeyRepository
    from src.db.settings_singleton_repositories import PgLlmConfigRepository
    from src.utils.key_resolver import ApiKeyResolver

    resolver = ApiKeyResolver(PgApiKeyRepository(sf), settings)
    resolved = await resolver.resolve_all()
    if resolved:
        settings = settings.model_copy(update=resolved)
        logger.info("api_keys_resolved", resolved_services=list(resolved.keys()))
    try:
        llm_cfg = await PgLlmConfigRepository(sf).get_or_create()
        settings = apply_llm_config_overlay(settings, llm_cfg)
    except Exception as exc:
        logger.warning("llm_config_overlay_skipped", error=str(exc))
    return settings


def apply_llm_config_overlay(settings: Settings, llm_cfg: object) -> Settings:
    """Overlay persisted LlmConfig (image provider/model) onto Settings."""
    updates: dict[str, str | None] = {}
    provider = getattr(llm_cfg, "image_provider", None)
    model = getattr(llm_cfg, "image_model", None)
    if provider:
        updates["default_image_provider"] = provider
    if model:
        field = {
            "dalle_3": "dalle_model",
            "gemini_flash": "image_model_gemini_flash",
            "gemini_3_pro": "image_model_gemini_3_pro",
            "imagen_4": "image_model_imagen_4",
        }.get(provider or "")
        if field and hasattr(settings, field):
            updates[field] = model
    if not updates:
        return settings
    logger.info(
        "llm_config_overlay_applied", image_provider=provider, image_model=model
    )
    return settings.model_copy(update=updates)


async def build_pipeline_services(
    settings: Settings,
    sf: async_sessionmaker[AsyncSession],
) -> PipelineServices:
    """Build the pipeline service graph from resolved settings (app-free)."""
    step_repo = PgAgentStepRepository(sf)
    llm_call_repo = PgLlmCallRepository(sf)
    repos = ResearchRepositories(
        sessions=PgResearchSessionRepository(sf),
        steps=step_repo,
        topics=PgTopicRepository(sf),
    )
    orchestrator: object = _NoOpOrchestrator()
    content_deps = ContentDeps(settings=settings)
    if settings.anthropic_api_key:
        try:
            orchestrator = _build_real_orchestrator(
                settings, step_repo=step_repo, llm_call_repo=llm_call_repo
            )
            llm = _build_llm(settings, llm_call_repo=llm_call_repo)
            retriever = _try_build_retriever_from_settings(settings)
            content_deps = ContentDeps(
                llm=llm, retriever=retriever, settings=settings
            )
        except Exception as exc:
            logger.error("pipeline_llm_init_failed", error=str(exc))
    article_repo = PgArticleRepository(sf)
    content_repos = ContentRepositories(
        drafts=PgArticleDraftRepository(sf),
        research=PgResearchSessionRepository(sf),
        articles=article_repo,
    )
    content_service = ContentService(
        repos=content_repos, deps=content_deps, step_repo=step_repo
    )
    return PipelineServices(
        settings=settings,
        session_factory=sf,
        research_service=ResearchService(repos, orchestrator),  # type: ignore[arg-type]
        content_service=content_service,
        outline_gate=OutlineGateService(content_service),
        llm_call_repo=llm_call_repo,
        step_repo=step_repo,
        content_repos=content_repos,
        article_repo=article_repo,
    )
