"""Pipeline service factory shared by the API lifespan and the Celery
worker (INFRA-007).

`build_pipeline_services` is a linear, app-free version of the wiring that
`src/api/main.py::_lifespan` performs: PG repos -> orchestrator ->
ResearchService -> ContentDeps -> ContentService -> OutlineGateService.
`resolve_runtime_settings` reproduces the DB API-key resolution and the
LlmConfig overlay so worker runs use the same keys and image provider as
the API. Construction is lazy — repos store the session factory and touch
the DB only on first use. Low-level builders live in
`src/services/bootstrap_builders.py`.

NOTE (deliberate deviation from the INFRA-007 plan): `_lifespan` still
builds its services inline (importing the same builders) instead of
calling `build_pipeline_services` — a conservative behaviour-preservation
choice. If you change the construction chain in EITHER place, mirror it
in the other; convergence is tracked as an INFRA-008-adjacent follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from src.config.settings import Settings
from src.db.llm_call_repository import PgLlmCallRepository
from src.db.persona_repository import PgPersonaRepository
from src.db.prompt_override_repository import PgPromptOverrideRepository
from src.db.repositories import (
    PgAgentStepRepository,
    PgArticleDraftRepository,
    PgArticleRepository,
    PgResearchSessionRepository,
    PgTopicRepository,
)
from src.services.bootstrap_builders import (
    _build_llm,
    _build_real_orchestrator,
    _NoOpOrchestrator,
    _try_build_retriever_from_settings,
    build_embedding_service,
)
from src.services.content import ContentService
from src.services.content.outline_gate import OutlineGateService
from src.services.content_repositories import ContentDeps, ContentRepositories
from src.services.research import ResearchRepositories, ResearchService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()


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
    prompt_override_repo: PgPromptOverrideRepository
    persona_repo: PgPersonaRepository


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
    # AUTHOR-011 — shared by both content_deps below, so the persona repo
    # and embedding service are always available for voice resolution,
    # whether or not the LLM/retriever build succeeds.
    persona_repo = PgPersonaRepository(sf)
    embedding_service = build_embedding_service(settings)
    content_deps = ContentDeps(
        settings=settings,
        persona_repo=persona_repo,
        embedding_service=embedding_service,
    )
    if settings.anthropic_api_key:
        try:
            orchestrator = _build_real_orchestrator(
                settings, step_repo=step_repo, llm_call_repo=llm_call_repo
            )
            llm = _build_llm(settings, llm_call_repo=llm_call_repo)
            retriever = _try_build_retriever_from_settings(settings)
            content_deps = ContentDeps(
                llm=llm,
                retriever=retriever,
                settings=settings,
                persona_repo=persona_repo,
                embedding_service=embedding_service,
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
        prompt_override_repo=PgPromptOverrideRepository(sf),
        persona_repo=persona_repo,
    )
