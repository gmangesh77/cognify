import time

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

from src.api.middleware.correlation_id import correlation_id_ctx
from src.utils.logging import SENSITIVE_KEYS

logger = structlog.get_logger()

_SKIP_PATHS = {"/docs", "/openapi.json", "/redoc"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        log_kwargs: dict[str, object] = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id_ctx.get(""),
        }

        params = dict(request.query_params)
        if params:
            log_kwargs["query_params"] = {
                k: "***REDACTED***" if k in SENSITIVE_KEYS else v
                for k, v in params.items()
            }

        logger.info("request_completed", **log_kwargs)
        return response
