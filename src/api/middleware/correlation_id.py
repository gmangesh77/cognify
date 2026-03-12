import re
import uuid
from contextvars import ContextVar

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

_VALID_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-_]{1,128}$")


def _generate_id() -> str:
    return str(uuid.uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming_id = request.headers.get("x-request-id", "")
        if incoming_id and _VALID_ID_PATTERN.match(incoming_id):
            request_id = incoming_id
        else:
            request_id = _generate_id()

        token = correlation_id_ctx.set(request_id)
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            return response
        finally:
            correlation_id_ctx.reset(token)
