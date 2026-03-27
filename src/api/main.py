from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
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
from src.api.errors import CognifyError, build_error_response
from src.api.middleware.correlation_id import CorrelationIdMiddleware
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.api.middleware.security_headers import SecurityHeadersMiddleware
from src.api.rate_limiter import limiter
from src.api.routers.admin import admin_router
from src.api.routers.articles import articles_router
from src.api.routers.auth import auth_router
from src.api.routers.canonical_articles import canonical_articles_router
from src.api.routers.health import health_router
from src.api.routers.metrics import metrics_router
from src.api.routers.publishing import publishing_router
from src.api.routers.research import research_router
from src.api.routers.settings import settings_router
from src.api.routers.topics import topics_router
from src.api.routers.trends import trends_router
from src.config.settings import Settings
from src.db.engine import create_async_engine as create_db_engine
from src.db.engine import get_session_factory
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
from src.services.content import ContentService
from src.services.content_repositories import (
    ContentDeps,
    ContentRepositories,
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
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
    app: FastAPI, settings: Settings,
) -> "MilvusRetriever | None":
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
            hint="RAG retrieval disabled. Articles will be generated without vector context.",
        )
        return None


def _get_or_create_embedding_service(app: FastAPI) -> "EmbeddingService":
    if not hasattr(app.state, "embedding_service"):
        from src.services.embeddings import EmbeddingService
        app.state.embedding_service = EmbeddingService(
            model_name=app.state.settings.embedding_model,
        )
    return app.state.embedding_service  # type: ignore[no-any-return]


@asynccontextmanager
async def _lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Lifespan handler: wires PG repos and LLM services."""
    settings = app.state.settings
    db_url = settings.database_url

    # --- Build LLM + content deps (shared by DB and non-DB paths) ---
    content_deps = ContentDeps(settings=settings)
    if settings.anthropic_api_key:
        try:
            llm = _build_llm(settings)
            retriever = _try_build_retriever(app, settings)
            content_deps = ContentDeps(
                llm=llm, retriever=retriever, settings=settings,
            )
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

        # Re-wire research service with PG repos
        step_repo = PgAgentStepRepository(sf)
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
                    settings, step_repo=step_repo,
                )
            except Exception as exc:
                logger.error(
                    "orchestrator_rebuild_failed", error=str(exc),
                )
        app.state.research_service = ResearchService(
            repos, orchestrator,
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
                    llm = _build_llm(settings)
                    retriever = _try_build_retriever(app, settings)
                    content_deps = ContentDeps(
                        llm=llm, retriever=retriever, settings=settings,
                    )
                    app.state.content_service = ContentService(
                        repos=content_repos, deps=content_deps,
                        step_repo=step_repo,
                    )
                    orchestrator = _build_real_orchestrator(
                        settings, step_repo=step_repo,
                    )
                    app.state.research_service = ResearchService(
                        repos, orchestrator,
                    )
                    logger.info("llm_rebuilt_with_resolved_keys")
                except Exception as exc:
                    logger.error("llm_rebuild_failed", error=str(exc))
        # Publishing service (requires article_repo)
        _init_publishing_service(app, settings, article_repo)
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
            repos=in_mem_repos, deps=content_deps,
        )
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
    app.state.trend_registry = init_registry(settings)
    _init_research_service(app)

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


def _build_llm(settings: Settings):  # type: ignore[no-untyped-def]
    """Build ChatAnthropic LLM instance from settings."""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    )


def _build_real_orchestrator(
    settings: Settings, step_repo: "AgentStepRepository | None" = None,
):  # type: ignore[no-untyped-def]
    """Build the full LangGraph research orchestrator."""
    from src.agents.research.literature_review import (
        LiteratureReviewAgent,
    )
    from src.agents.research.orchestrator import (
        GraphDeps,
        build_graph,
    )
    from src.agents.research.runner import (
        LangGraphResearchOrchestrator,
    )
    from src.agents.research.web_search import WebSearchAgent
    from src.services.semantic_scholar import SemanticScholarClient
    from src.services.serpapi_client import SerpAPIClient
    from src.services.task_dispatch import AsyncIODispatcher

    llm = _build_llm(settings)
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
    )
    graph = build_graph(llm, dispatcher, web_agent, lit_agent, deps)
    return LangGraphResearchOrchestrator(graph, step_repo)


def _get_or_create_embedding_service_from_settings(
    settings: Settings,
) -> "EmbeddingService":
    """Create EmbeddingService from settings (no app state)."""
    from src.services.embeddings import EmbeddingService

    return EmbeddingService(model_name=settings.embedding_model)


class _NoOpOrchestrator:
    """Stub orchestrator used when ANTHROPIC_API_KEY is not set."""

    async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
        return {
            "status": "complete",
            "findings": [],
            "round_number": 1,
            "indexed_count": 0,
        }


def _init_publishing_service(
    app: FastAPI, settings: Settings, article_repo: object,
) -> None:
    """Initialize publishing service with available platform adapters."""
    from src.services.publishing.service import PlatformPair, PublishingService

    svc = PublishingService(article_repo)
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
        repos, _NoOpOrchestrator(),
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
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
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
        publishing_router,
        prefix=settings.api_v1_prefix,
        tags=["publishing"],
    )
    assets_dir = Path("generated_assets")
    if assets_dir.exists():
        app.mount(
            "/generated_assets",
            StaticFiles(directory=str(assets_dir)),
            name="generated_assets",
        )
