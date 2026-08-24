"""Low-level service builders shared by the API lifespan and the worker.

Split out of `src/services/bootstrap.py` (INFRA-007 review) to keep both
files under the 200-line budget. These are verbatim moves of the builders
that historically lived in `src/api/main.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from langchain_core.language_models import BaseChatModel

from src.config.settings import Settings

if TYPE_CHECKING:
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


def build_embedding_service(settings: Settings) -> EmbeddingService:
    """Create EmbeddingService from settings (no app state, no cache)."""
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

        embedder = build_embedding_service(settings)
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
        embed_svc = build_embedding_service(settings)
        return MilvusRetriever(milvus_svc, embed_svc)
    except Exception as exc:
        logger.warning("milvus_unavailable", error=str(exc))
        return None


__all__ = [
    "_NoOpOrchestrator",
    "_build_llm",
    "_build_real_orchestrator",
    "_try_build_retriever_from_settings",
    "build_embedding_service",
]
