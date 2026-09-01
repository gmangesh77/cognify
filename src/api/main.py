from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.services.embeddings import EmbeddingService
    from src.services.milvus_service import MilvusRetriever
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.auth.password import hash_password
from src.api.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
from src.api.auth.schemas import UserData
from src.api.auth.user_status import UserStatusCache
from src.api.errors import CognifyError, build_error_response
from src.api.middleware.correlation_id import CorrelationIdMiddleware
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.api.middleware.security_headers import SecurityHeadersMiddleware
from src.api.rate_limiter import limiter
from src.api.routers.admin import admin_router
from src.api.routers.article_metadata import article_metadata_router
from src.api.routers.articles import articles_router
from src.api.routers.auth import auth_router
from src.api.routers.briefs import briefs_router
from src.api.routers.canonical_articles import canonical_articles_router
from src.api.routers.content import content_router
from src.api.routers.content_humanize_stream import content_humanize_stream_router
from src.api.routers.content_regenerate import content_regenerate_router
from src.api.routers.health import health_router
from src.api.routers.metrics import metrics_router
from src.api.routers.oauth import oauth_router
from src.api.routers.outline import outline_router
from src.api.routers.personas import personas_router
from src.api.routers.pipeline_debug import pipeline_debug_router
from src.api.routers.prompts import prompts_router
from src.api.routers.publishing import publishing_router
from src.api.routers.research import research_router
from src.api.routers.session_events import session_events_router
from src.api.routers.settings import settings_router
from src.api.routers.topics import topics_router
from src.api.routers.trends import trends_router
from src.api.routers.usage import usage_router
from src.api.routers.visuals import visuals_router
from src.config.settings import Settings
from src.db.engine import create_async_engine as create_db_engine
from src.db.engine import get_session_factory
from src.db.llm_call_repository import PgLlmCallRepository
from src.db.persona_repository import InMemoryPersonaRepository
from src.db.prompt_override_repository import InMemoryPromptOverrideRepository
from src.db.repositories import (
    PgAgentStepRepository,
    PgArticleDraftRepository,
    PgArticleRepository,
    PgResearchSessionRepository,
    PgTopicRepository,
)
from src.db.settings_repositories import PgApiKeyRepository, PgDomainConfigRepository
from src.db.settings_singleton_repositories import (
    PgGeneralConfigRepository,
    PgLlmConfigRepository,
    PgSeoDefaultsRepository,
)
from src.services.bootstrap import apply_llm_config_overlay
from src.services.bootstrap_builders import (
    _build_llm,
    _build_real_orchestrator,
    _NoOpOrchestrator,
)
from src.services.briefs import BriefService, InMemoryBriefRepository
from src.services.content import ContentService
from src.services.content.outline_gate import OutlineGateService
from src.services.content_repositories import (
    ContentDeps,
    ContentRepositories,
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from src.services.persona.service import PersonaService
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
from src.services.session_tasks import SessionTaskRegistry
from src.services.topic_persistence import TopicPersistenceService
from src.services.trends import init_registry
from src.utils.key_resolver import ApiKeyResolver
from src.utils.logging import setup_logging

logger = structlog.get_logger()


class _SettingsRepos:
    """Container for all settings repository instances."""

    def __init__(
        self,
        domains: PgDomainConfigRepository,
        api_keys: PgApiKeyRepository,
        llm: PgLlmConfigRepository,
        seo: PgSeoDefaultsRepository,
        general: PgGeneralConfigRepository,
    ) -> None:
        self.domains = domains
        self.api_keys = api_keys
        self.llm = llm
        self.seo = seo
        self.general = general


def _try_build_retriever(
    app: FastAPI,
    settings: Settings,
) -> MilvusRetriever | None:
    """Build MilvusRetriever if Milvus is available, else None."""
    try:
        from src.services.milvus_retriever import MilvusRetriever
        from src.services.milvus_service import MilvusService

        milvus_svc = MilvusService(
            uri=settings.milvus_uri,
            collection_name=settings.milvus_collection_name,
        )
        milvus_svc.ensure_collection()
        embed_svc = _get_or_create_embedding_service(app)
        return MilvusRetriever(milvus_svc, embed_svc)
    except Exception as exc:
        logger.warning(
            "milvus_unavailable",
            error=str(exc),
            hint=(
                "RAG retrieval disabled. "
                "Articles will be generated without vector context."
            ),
        )
        return None


def _get_or_create_embedding_service(app: FastAPI) -> EmbeddingService:
    if not hasattr(app.state, "embedding_service"):
        from src.services.embeddings import EmbeddingService

        app.state.embedding_service = EmbeddingService(
            model_name=app.state.settings.embedding_model,
        )
    return app.state.embedding_service  # type: ignore[no-any-return]


def _wire_persona_repo(
    app: FastAPI,
    sf: async_sessionmaker[AsyncSession],
    content_deps: ContentDeps,
) -> ContentDeps:
    """AUTHOR-011 — build the PG persona repo/service and fold it into
    `content_deps` BEFORE `ContentService` is constructed.

    `ContentDeps` is frozen: a later `app.state.persona_repo` reassignment
    does not reach a `ContentService` already built from an earlier
    `content_deps` snapshot. Review round 1 found the DB branch used to
    build `ContentService` first and only reassign `app.state.persona_repo`
    afterward — the pipeline silently kept reading the in-memory seed repo
    from `create_app()` instead of Postgres whenever the anthropic key came
    from `.env` (the only rebuild path was gated on a *resolved* DB key).
    """
    from src.db.persona_repository import PgPersonaRepository

    app.state.persona_repo = PgPersonaRepository(sf)
    app.state.persona_service = PersonaService(
        app.state.persona_repo,
        embed=lambda texts: _get_or_create_embedding_service(app).try_embed(texts),
    )
    return replace(content_deps, persona_repo=app.state.persona_repo)


@asynccontextmanager
async def _lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Lifespan handler: wires PG repos and LLM services."""
    settings = app.state.settings
    db_url = settings.database_url

    # AUTHOR-002 — registry of in-flight per-session background pipeline
    # tasks, shared by the research create/cancel/approve endpoints.
    app.state.session_tasks = SessionTaskRegistry()

    # INFRA-008 — warm the embedding model on a daemon thread so the first
    # dedup/RAG call never blocks the event loop on a model load (PR #72
    # baked the weights into the image; this removes the first-call stall).
    if settings.embedding_warmup:
        _get_or_create_embedding_service(app).warm_up_in_background()

    # --- Build LLM + content deps (shared by DB and non-DB paths) ---
    # AUTHOR-011 — `create_app()` always seeds `app.state.persona_repo`
    # (in-memory or PG) before lifespan runs, so it's safe here too.
    content_deps = ContentDeps(
        settings=settings,
        persona_repo=app.state.persona_repo,
        embedding_service=_get_or_create_embedding_service(app),
    )
    if settings.anthropic_api_key:
        try:
            llm = _build_llm(settings)
            retriever = _try_build_retriever(app, settings)
            content_deps = ContentDeps(
                llm=llm,
                retriever=retriever,
                settings=settings,
                persona_repo=app.state.persona_repo,
                embedding_service=_get_or_create_embedding_service(app),
            )
            app.state.drafting_llm = llm
            logger.info(
                "content_deps_initialized",
                mode="real_llm",
                rag_enabled=retriever is not None,
            )
        except Exception as exc:
            logger.error("content_deps_init_failed", error=str(exc))

    if db_url:
        engine = create_db_engine(db_url)
        app.state.db_engine = engine
        sf = get_session_factory(engine)

        # AUTHOR-011 — must run before `ContentService(...)` below so the
        # PG persona repo (not the in-memory seed) is baked into the deps
        # it is built from (review round 1 — see `_wire_persona_repo`).
        content_deps = _wire_persona_repo(app, sf, content_deps)

        # Re-wire research service with PG repos
        step_repo = PgAgentStepRepository(sf)
        llm_call_repo = PgLlmCallRepository(sf)
        app.state.llm_call_repo = llm_call_repo
        repos = ResearchRepositories(
            sessions=PgResearchSessionRepository(sf),
            steps=step_repo,
            topics=PgTopicRepository(sf),
        )
        # Re-build orchestrator with PG step_repo if real LLM
        orchestrator = app.state.research_service._orchestrator
        if settings.anthropic_api_key and not isinstance(
            orchestrator, _NoOpOrchestrator
        ):
            try:
                orchestrator = _build_real_orchestrator(
                    settings,
                    step_repo=step_repo,
                    llm_call_repo=llm_call_repo,
                )
            except Exception as exc:
                logger.error(
                    "orchestrator_rebuild_failed",
                    error=str(exc),
                )
        app.state.research_service = ResearchService(
            repos,
            orchestrator,
        )

        article_repo = PgArticleRepository(sf)
        app.state.article_repo = article_repo
        content_repos = ContentRepositories(
            drafts=PgArticleDraftRepository(sf),
            research=PgResearchSessionRepository(sf),
            articles=article_repo,
        )
        app.state.content_repos = content_repos
        app.state.content_service = ContentService(
            repos=content_repos,
            deps=content_deps,
            step_repo=step_repo,
        )
        app.state.outline_gate = OutlineGateService(app.state.content_service)
        # Topic persistence service
        topic_repo = PgTopicRepository(sf)
        app.state.topic_repo = topic_repo
        app.state.topic_persistence_service = TopicPersistenceService(
            repo=topic_repo,
            embedding_service=_get_or_create_embedding_service(app),
            threshold=settings.dedup_similarity_threshold,
        )
        # Settings repositories
        api_key_repo = PgApiKeyRepository(sf)
        app.state.settings_repos = _SettingsRepos(
            domains=PgDomainConfigRepository(sf),
            api_keys=api_key_repo,
            llm=PgLlmConfigRepository(sf),
            seo=PgSeoDefaultsRepository(sf),
            general=PgGeneralConfigRepository(sf),
        )
        # VISUAL-010 / Phase 7 — image-asset-tag repo for the saved gallery's
        # curation feature. Imported lazily so the API can boot without the
        # new table existing yet (the migration lands separately).
        from src.db.image_asset_tag_repository import (
            PgImageAssetTagRepository,
        )

        app.state.image_asset_tag_repo = PgImageAssetTagRepository(sf)
        # VISUAL-011 / Phase 8 — section version sidecar for prose history.
        # Imported lazily so the API can boot before the migration runs.
        from src.db.section_version_repository import (
            PgSectionVersionRepository,
        )

        app.state.section_version_repo = PgSectionVersionRepository(sf)
        # AUTHOR-003 — briefs (ADR-007). Lazy import: API boots before migration.
        from src.db.brief_repository import PgBriefRepository

        app.state.brief_service = BriefService(PgBriefRepository(sf))
        # AUTHOR-012 — prompt overrides. Lazy import: API boots before migration.
        from src.db.prompt_override_repository import PgPromptOverrideRepository

        app.state.prompt_override_repo = PgPromptOverrideRepository(sf)
        # Resolve API keys: DB overrides .env
        resolver = ApiKeyResolver(api_key_repo, settings)
        resolved = await resolver.resolve_all()
        app.state.key_resolver = resolver
        if resolved:
            settings = settings.model_copy(update=resolved)
            app.state.settings = settings
            logger.info(
                "api_keys_resolved",
                resolved_services=list(resolved.keys()),
            )
            # Rebuild LLM deps if anthropic key was resolved
            if "anthropic_api_key" in resolved and settings.anthropic_api_key:
                try:
                    llm = _build_llm(settings, llm_call_repo=llm_call_repo)
                    retriever = _try_build_retriever(app, settings)
                    content_deps = ContentDeps(
                        llm=llm,
                        retriever=retriever,
                        settings=settings,
                        persona_repo=app.state.persona_repo,
                        embedding_service=_get_or_create_embedding_service(app),
                    )
                    app.state.content_service = ContentService(
                        repos=content_repos,
                        deps=content_deps,
                        step_repo=step_repo,
                    )
                    app.state.outline_gate = OutlineGateService(
                        app.state.content_service
                    )
                    orchestrator = _build_real_orchestrator(
                        settings,
                        step_repo=step_repo,
                        llm_call_repo=llm_call_repo,
                    )
                    app.state.research_service = ResearchService(
                        repos,
                        orchestrator,
                    )
                    app.state.drafting_llm = llm
                    logger.info("llm_rebuilt_with_resolved_keys")
                except Exception as exc:
                    logger.error("llm_rebuild_failed", error=str(exc))
        # Rebuild trend registry with resolved API keys (AB#16751)
        # The registry was initially built at app creation with potentially
        # empty keys; now that DB keys are resolved, rebuild it.
        app.state.trend_registry = init_registry(settings)
        logger.info("trend_registry_rebuilt_with_resolved_keys")

        # Overlay persisted LlmConfig on Settings so user-selected image
        # provider/model from the Settings UI takes effect at render time.
        # Without this, settings.default_image_provider always reflects the
        # static .env default. Mirrors the api_keys overlay above.
        try:
            llm_cfg = await app.state.settings_repos.llm.get_or_create()
            overlaid = apply_llm_config_overlay(settings, llm_cfg)
            if overlaid is not settings:
                settings = overlaid
                app.state.settings = settings
        except Exception as exc:
            logger.warning("llm_config_overlay_skipped", error=str(exc))

        # Publishing service (requires article_repo)
        from src.db.repositories import PgPublicationRepository

        pub_repo = PgPublicationRepository(sf)
        app.state.pub_repo = pub_repo
        app.state.article_repo = article_repo
        _init_publishing_service(app, settings, article_repo, pub_repo)
        logger.info("database_connected", url=db_url.split("@")[-1])
    else:
        # In-memory fallback (no database configured)
        in_mem_repos = ContentRepositories(
            drafts=InMemoryArticleDraftRepository(),
            research=InMemoryResearchSessionRepository(),
            articles=InMemoryArticleRepository(),
        )
        app.state.content_repos = in_mem_repos
        app.state.content_service = ContentService(
            repos=in_mem_repos,
            deps=content_deps,
        )
        app.state.outline_gate = OutlineGateService(app.state.content_service)
    yield
    if hasattr(app.state, "db_engine"):
        await app.state.db_engine.dispose()
        logger.info("database_disconnected")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    setup_logging(debug=settings.debug)

    app = FastAPI(
        title="Cognify API",
        version=settings.app_version,
        debug=False,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.limiter = limiter
    app.state.refresh_repo = InMemoryRefreshTokenRepository()
    app.state.user_repo = InMemoryUserRepository(_seed_dev_users(settings))
    app.state.user_status_cache = UserStatusCache(
        ttl_seconds=settings.auth_recheck_ttl_seconds
    )
    app.state.trend_registry = init_registry(settings)
    _init_research_service(app)
    app.state.brief_service = BriefService(InMemoryBriefRepository())
    app.state.prompt_override_repo = InMemoryPromptOverrideRepository()
    app.state.persona_repo = InMemoryPersonaRepository()
    app.state.persona_service = PersonaService(
        app.state.persona_repo,
        embed=lambda texts: _get_or_create_embedding_service(app).try_embed(texts),
    )

    _register_exception_handlers(app)
    _register_middleware(app, settings)
    _register_routers(app, settings)

    return app


def _seed_dev_users(settings: Settings) -> list[UserData]:
    """Seed demo users for development. Skipped when debug=False."""
    if not settings.debug:
        return []
    logger.info("seeding_dev_users")
    return [
        UserData(
            id="user-1",
            email="admin@cognify.dev",
            password_hash=hash_password("admin123"),
            role="admin",
        ),
        UserData(
            id="user-2",
            email="editor@cognify.dev",
            password_hash=hash_password("editor123"),
            role="editor",
        ),
        UserData(
            id="user-3",
            email="viewer@cognify.dev",
            password_hash=hash_password("viewer123"),
            role="viewer",
        ),
    ]


# _build_llm / _build_real_orchestrator / _NoOpOrchestrator /
# _get_or_create_embedding_service_from_settings moved to
# src/services/bootstrap.py (INFRA-007) so the Celery worker can reuse them.


def _init_publishing_service(
    app: FastAPI,
    settings: Settings,
    article_repo: object,
    pub_repo: object | None = None,
) -> None:
    """Initialize publishing service with available platform adapters."""
    from src.services.publishing.service import PlatformPair, PublishingService

    svc = PublishingService(article_repo, pub_repo)
    if settings.ghost_api_url and settings.ghost_admin_api_key:
        from src.services.publishing.ghost.adapter import GhostAdapter
        from src.services.publishing.ghost.transformer import GhostTransformer

        api_base = "http://localhost:8000"
        pair = PlatformPair(
            transformer=GhostTransformer(api_base_url=api_base),
            adapter=GhostAdapter(settings.ghost_api_url, settings.ghost_admin_api_key),
        )
        svc.register("ghost", pair)
    if settings.medium_api_token and settings.medium_user_id:
        from src.services.publishing.medium.adapter import MediumAdapter
        from src.services.publishing.medium.transformer import MediumTransformer

        pair = PlatformPair(
            transformer=MediumTransformer(),
            adapter=MediumAdapter(settings.medium_api_token, settings.medium_user_id),
        )
        svc.register("medium", pair)
    if settings.linkedin_access_token:
        from src.services.publishing.linkedin.adapter import (
            LinkedInAdapter,
            LinkedInCredentials,
        )
        from src.services.publishing.linkedin.transformer import LinkedInTransformer

        creds = LinkedInCredentials(
            access_token=settings.linkedin_access_token,
            author_urn=settings.linkedin_author_urn,
            refresh_token=settings.linkedin_refresh_token,
            client_id=settings.linkedin_client_id,
            client_secret=settings.linkedin_client_secret,
        )
        pair = PlatformPair(
            transformer=LinkedInTransformer(),
            adapter=LinkedInAdapter(creds),
        )
        svc.register("linkedin", pair)
    app.state.publishing_service = svc
    logger.info("publishing_service_initialized", platforms=list(svc._platforms.keys()))


def _init_research_service(app: FastAPI) -> None:
    """Initialize research service. Uses real LLM when API key is set."""
    settings = app.state.settings
    repos = ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=InMemoryTopicRepository(),
    )
    if settings.anthropic_api_key:
        try:
            orchestrator = _build_real_orchestrator(settings)
            app.state.research_service = ResearchService(repos, orchestrator)
            logger.info("research_service_initialized", mode="real_llm")
            return
        except Exception as exc:
            logger.error(
                "real_orchestrator_init_failed",
                error=str(exc),
            )
    app.state.research_service = ResearchService(
        repos,
        _NoOpOrchestrator(),
    )  # type: ignore[arg-type]
    logger.info("research_service_initialized", mode="noop")


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CognifyError)
    async def cognify_error_handler(
        request: Request, exc: CognifyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(code=exc.code, message=exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [str(e) for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=build_error_response(
                code="validation_error",
                message="Request validation failed",
                details=details,
            ),
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=build_error_response(
                code="rate_limited",
                message="Rate limit exceeded",
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        import traceback

        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            exc_message=str(exc),
            traceback=traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content=build_error_response(
                code="internal_error",
                message="An unexpected error occurred",
            ),
        )


def _register_middleware(app: FastAPI, settings: Settings) -> None:
    # Registration order is REVERSED from execution order.
    # Execution order (outermost to innermost on request):
    # 1. Correlation ID (outermost)
    # 2. Security headers
    # 3. CORS
    # 4. Rate limiting (SlowAPIMiddleware)
    # 5. Request logging (innermost)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationIdMiddleware)


def _register_routers(app: FastAPI, settings: Settings) -> None:
    app.include_router(
        health_router,
        prefix=settings.api_v1_prefix,
        tags=["health"],
    )
    app.include_router(
        auth_router,
        prefix=settings.api_v1_prefix,
        tags=["auth"],
    )
    app.include_router(
        admin_router,
        prefix=settings.api_v1_prefix,
        tags=["admin"],
    )
    app.include_router(
        topics_router,
        prefix=settings.api_v1_prefix,
        tags=["topics"],
    )
    app.include_router(
        trends_router,
        prefix=settings.api_v1_prefix,
        tags=["trends"],
    )
    app.include_router(
        research_router,
        prefix=settings.api_v1_prefix,
        tags=["research"],
    )
    app.include_router(
        outline_router,
        prefix=settings.api_v1_prefix,
        tags=["research"],
    )
    app.include_router(
        session_events_router,
        prefix=settings.api_v1_prefix,
        tags=["research"],
    )
    app.include_router(
        usage_router,
        prefix=settings.api_v1_prefix,
        tags=["usage"],
    )
    app.include_router(
        briefs_router,
        prefix=settings.api_v1_prefix,
        tags=["briefs"],
    )
    app.include_router(
        articles_router,
        prefix=settings.api_v1_prefix,
        tags=["articles"],
    )
    app.include_router(
        canonical_articles_router,
        prefix=settings.api_v1_prefix,
        tags=["articles"],
    )
    app.include_router(
        article_metadata_router,
        prefix=settings.api_v1_prefix,
        tags=["articles"],
    )
    app.include_router(
        metrics_router,
        prefix=settings.api_v1_prefix,
        tags=["metrics"],
    )
    app.include_router(
        settings_router,
        prefix=settings.api_v1_prefix,
        tags=["settings"],
    )
    app.include_router(
        prompts_router,
        prefix=settings.api_v1_prefix,
        tags=["prompts"],
    )
    app.include_router(
        personas_router,
        prefix=settings.api_v1_prefix,
        tags=["personas"],
    )
    app.include_router(
        publishing_router,
        prefix=settings.api_v1_prefix,
        tags=["publishing"],
    )
    app.include_router(
        oauth_router,
        prefix=settings.api_v1_prefix,
        tags=["oauth"],
    )
    app.include_router(
        pipeline_debug_router,
        prefix=settings.api_v1_prefix,
        tags=["debug"],
    )
    app.include_router(
        visuals_router,
        prefix=settings.api_v1_prefix,
        tags=["visuals"],
    )
    app.include_router(
        content_router,
        prefix=settings.api_v1_prefix,
        tags=["content"],
    )
    app.include_router(
        content_humanize_stream_router,
        prefix=settings.api_v1_prefix,
        tags=["content"],
    )
    app.include_router(
        content_regenerate_router,
        prefix=settings.api_v1_prefix,
        tags=["content"],
    )
    assets_dir = Path("generated_assets")
    if assets_dir.exists():
        app.mount(
            "/generated_assets",
            StaticFiles(directory=str(assets_dir)),
            name="generated_assets",
        )


app = create_app()
