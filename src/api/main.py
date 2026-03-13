import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.errors import CognifyError, build_error_response
from src.api.middleware.correlation_id import CorrelationIdMiddleware
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.api.middleware.security_headers import SecurityHeadersMiddleware
from src.api.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
from src.api.rate_limiter import limiter
from src.api.routers.auth import auth_router
from src.api.routers.health import health_router
from src.config.settings import Settings
from src.utils.logging import setup_logging

logger = structlog.get_logger()


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    setup_logging(debug=settings.debug)

    app = FastAPI(
        title="Cognify API",
        version=settings.app_version,
        debug=False,
    )
    app.state.settings = settings
    app.state.limiter = limiter
    app.state.refresh_repo = InMemoryRefreshTokenRepository()
    app.state.user_repo = InMemoryUserRepository([])

    _register_exception_handlers(app)
    _register_middleware(app, settings)
    _register_routers(app, settings)

    return app


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
