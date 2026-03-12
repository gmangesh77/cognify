import re
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from src.api.middleware.correlation_id import (
    CorrelationIdMiddleware,
    correlation_id_ctx,
)


@pytest.fixture
def app_with_correlation_id() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(
            {"correlation_id": correlation_id_ctx.get("")}
        )

    return app


@pytest.fixture
async def corr_client(
    app_with_correlation_id: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_with_correlation_id),
        base_url="http://test",
    ) as ac:
        yield ac


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}"
    r"-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class TestCorrelationIdMiddleware:
    async def test_generates_request_id(
        self, corr_client: httpx.AsyncClient
    ) -> None:
        response = await corr_client.get("/test")
        request_id = response.headers.get("x-request-id", "")
        assert UUID_PATTERN.match(request_id)

    async def test_echoes_custom_request_id(
        self, corr_client: httpx.AsyncClient
    ) -> None:
        custom_id = "my-custom-request-id-123"
        response = await corr_client.get(
            "/test", headers={"X-Request-ID": custom_id}
        )
        assert response.headers["x-request-id"] == custom_id
        assert response.json()["correlation_id"] == custom_id

    async def test_rejects_invalid_request_id_too_long(
        self, corr_client: httpx.AsyncClient
    ) -> None:
        long_id = "a" * 200
        response = await corr_client.get(
            "/test", headers={"X-Request-ID": long_id}
        )
        returned_id = response.headers["x-request-id"]
        assert returned_id != long_id
        assert UUID_PATTERN.match(returned_id)

    async def test_rejects_invalid_request_id_bad_chars(
        self, corr_client: httpx.AsyncClient
    ) -> None:
        bad_id = "id-with-<script>alert(1)</script>"
        response = await corr_client.get(
            "/test", headers={"X-Request-ID": bad_id}
        )
        returned_id = response.headers["x-request-id"]
        assert returned_id != bad_id
        assert UUID_PATTERN.match(returned_id)

    async def test_sets_context_var(
        self, corr_client: httpx.AsyncClient
    ) -> None:
        custom_id = "valid-id-123"
        response = await corr_client.get(
            "/test", headers={"X-Request-ID": custom_id}
        )
        assert response.json()["correlation_id"] == custom_id
