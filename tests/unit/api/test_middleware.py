import json
import re
from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from src.api.main import create_app
from src.api.middleware.correlation_id import (
    CorrelationIdMiddleware,
    correlation_id_ctx,
)
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.api.middleware.security_headers import SecurityHeadersMiddleware
from src.api.rate_limiter import limiter
from src.config.settings import Settings
from src.utils.logging import setup_logging


@pytest.fixture
def app_with_correlation_id() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request) -> JSONResponse:
        return JSONResponse({"correlation_id": correlation_id_ctx.get("")})

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
    async def test_generates_request_id(self, corr_client: httpx.AsyncClient) -> None:
        response = await corr_client.get("/test")
        request_id = response.headers.get("x-request-id", "")
        assert UUID_PATTERN.match(request_id)

    async def test_echoes_custom_request_id(
        self, corr_client: httpx.AsyncClient
    ) -> None:
        custom_id = "my-custom-request-id-123"
        response = await corr_client.get("/test", headers={"X-Request-ID": custom_id})
        assert response.headers["x-request-id"] == custom_id
        assert response.json()["correlation_id"] == custom_id

    async def test_rejects_invalid_request_id_too_long(
        self, corr_client: httpx.AsyncClient
    ) -> None:
        long_id = "a" * 200
        response = await corr_client.get("/test", headers={"X-Request-ID": long_id})
        returned_id = response.headers["x-request-id"]
        assert returned_id != long_id
        assert UUID_PATTERN.match(returned_id)

    async def test_rejects_invalid_request_id_bad_chars(
        self, corr_client: httpx.AsyncClient
    ) -> None:
        bad_id = "id-with-<script>alert(1)</script>"
        response = await corr_client.get("/test", headers={"X-Request-ID": bad_id})
        returned_id = response.headers["x-request-id"]
        assert returned_id != bad_id
        assert UUID_PATTERN.match(returned_id)

    async def test_sets_context_var(self, corr_client: httpx.AsyncClient) -> None:
        custom_id = "valid-id-123"
        response = await corr_client.get("/test", headers={"X-Request-ID": custom_id})
        assert response.json()["correlation_id"] == custom_id


@pytest.fixture
def app_with_security_headers() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    async def test_endpoint() -> JSONResponse:
        return JSONResponse({"ok": True})

    return app


@pytest.fixture
async def sec_client(
    app_with_security_headers: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_with_security_headers),
        base_url="http://test",
    ) as ac:
        yield ac


class TestSecurityHeadersMiddleware:
    async def test_x_content_type_options(self, sec_client: httpx.AsyncClient) -> None:
        response = await sec_client.get("/test")
        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_x_frame_options(self, sec_client: httpx.AsyncClient) -> None:
        response = await sec_client.get("/test")
        assert response.headers["x-frame-options"] == "DENY"

    async def test_content_security_policy(self, sec_client: httpx.AsyncClient) -> None:
        response = await sec_client.get("/test")
        assert response.headers["content-security-policy"] == "default-src 'self'"


@pytest.fixture
def app_with_logging() -> FastAPI:
    """App with both logging and correlation ID middleware."""
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/test")
    async def test_endpoint() -> JSONResponse:
        return JSONResponse({"ok": True})

    return app


@pytest.fixture
async def log_client(
    app_with_logging: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_with_logging),
        base_url="http://test",
    ) as ac:
        yield ac


class TestRequestLoggingMiddleware:
    async def test_logs_request_fields(
        self,
        log_client: httpx.AsyncClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(debug=False)
        await log_client.get("/test")
        captured = capsys.readouterr().out
        log_line = json.loads(captured.strip().split("\n")[-1])
        assert log_line["method"] == "GET"
        assert log_line["path"] == "/test"
        assert log_line["status_code"] == 200
        assert "duration_ms" in log_line
        assert "correlation_id" in log_line

    async def test_skips_docs_path(
        self,
        log_client: httpx.AsyncClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(debug=False)
        await log_client.get("/docs")
        captured = capsys.readouterr().out
        for line in captured.strip().split("\n"):
            if line.strip():
                data = json.loads(line)
                assert data.get("path") != "/docs"


@pytest.fixture
def _fresh_limiter() -> None:
    """Reset limiter state to isolate tests."""
    limiter._storage.reset()
    limiter._route_limits.clear()
    yield
    limiter._storage.reset()
    limiter._route_limits.clear()


@pytest.fixture
def rate_limited_app(_fresh_limiter: None) -> FastAPI:
    settings = Settings(rate_limit_default="1000/minute")
    app = create_app(settings)

    @app.get("/api/v1/test-rate-limit")
    @limiter.limit("2/minute")
    async def test_rate_limited(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    return app


@pytest.fixture
async def rate_client(
    rate_limited_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=rate_limited_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestRequestLoggingQueryParams:
    async def test_logs_query_params(
        self,
        log_client: httpx.AsyncClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(debug=False)
        await log_client.get("/test?page=1&size=20")
        captured = capsys.readouterr().out
        log_line = json.loads(captured.strip().split("\n")[-1])
        assert log_line["query_params"] == {"page": "1", "size": "20"}

    async def test_omits_query_params_when_empty(
        self,
        log_client: httpx.AsyncClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(debug=False)
        await log_client.get("/test")
        captured = capsys.readouterr().out
        log_line = json.loads(captured.strip().split("\n")[-1])
        assert "query_params" not in log_line

    async def test_redacts_sensitive_query_params(
        self,
        log_client: httpx.AsyncClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(debug=False)
        await log_client.get("/test?token=secret123&page=1")
        captured = capsys.readouterr().out
        log_line = json.loads(captured.strip().split("\n")[-1])
        assert log_line["query_params"]["token"] == "***REDACTED***"
        assert log_line["query_params"]["page"] == "1"


class TestRateLimiting:
    async def test_health_exempt_from_rate_limit(
        self, rate_client: httpx.AsyncClient
    ) -> None:
        for _ in range(5):
            response = await rate_client.get("/api/v1/health")
            assert response.status_code == 200

    async def test_readiness_exempt_from_rate_limit(
        self, rate_client: httpx.AsyncClient
    ) -> None:
        for _ in range(5):
            response = await rate_client.get("/api/v1/health/ready")
            assert response.status_code == 503

    async def test_rate_limit_returns_429_with_error_envelope(
        self, rate_client: httpx.AsyncClient
    ) -> None:
        # 2/minute limit — first 2 should succeed
        for _ in range(2):
            response = await rate_client.get("/api/v1/test-rate-limit")
            assert response.status_code == 200

        # 3rd request should be rate limited
        response = await rate_client.get("/api/v1/test-rate-limit")
        assert response.status_code == 429
        data = response.json()
        assert data["error"]["code"] == "rate_limited"
        assert data["error"]["message"] == "Rate limit exceeded"
