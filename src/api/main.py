from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
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
from src.api.routers.research import research_router
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
from src.services.content_repositories import ContentRepositories
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
from src.services.topic_persistence import TopicPersistenceService
from src.services.trends import init_registry
from src.utils.logging import setup_logging

logger = structlog.get_logger()


def _get_or_create_embedding_service(app: FastAPI) -> "EmbeddingService":
    if not hasattr(app.state, "embedding_service"):
        from src.services.embeddings import EmbeddingService
        app.state.embedding_service = EmbeddingService(
            model_name=app.state.settings.embedding_model,
        )
    return app.state.embedding_service  # type: ignore[no-any-return]


@asynccontextmanager
async def _lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Lifespan handler: wires PG repos when database_url is configured."""
    db_url = app.state.settings.database_url
    if db_url:
        engine = create_db_engine(db_url)
        app.state.db_engine = engine
        sf = get_session_factory(engine)
        repos = ResearchRepositories(
            sessions=PgResearchSessionRepository(sf),
            steps=PgAgentStepRepository(sf),
            topics=PgTopicRepository(sf),
        )
        app.state.research_service = ResearchService(
            repos, app.state.research_service._orchestrator
        )
        article_repo = PgArticleRepository(sf)
        app.state.article_repo = article_repo
        app.state.content_repos = ContentRepositories(
            drafts=PgArticleDraftRepository(sf),
            research=PgResearchSessionRepository(sf),
            articles=article_repo,
        )
        # Topic persistence service
        topic_repo = PgTopicRepository(sf)
        app.state.topic_repo = topic_repo
        app.state.topic_persistence_service = TopicPersistenceService(
            repo=topic_repo,
            embedding_service=_get_or_create_embedding_service(app),
            threshold=app.state.settings.dedup_similarity_threshold,
        )
        logger.info("database_connected", url=db_url.split("@")[-1])
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


def _init_research_service(app: FastAPI) -> None:
    """Initialize research service with in-memory repositories."""

    class NoOpOrchestrator:
        async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
            return {
                "status": "complete",
                "findings": [],
                "round_number": 1,
                "indexed_count": 0,
            }

    repos = ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=InMemoryTopicRepository(),
    )
    app.state.research_service = ResearchService(repos, NoOpOrchestrator())  # type: ignore[arg-type]
    logger.info("research_service_initialized")


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
        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            exc_message=str(exc),
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
        allow_methods=["*"],
        allow_headers=["*"],
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
