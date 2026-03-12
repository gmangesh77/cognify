# API-001: FastAPI Application Setup — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up the foundational FastAPI application with middleware, health endpoints, structured logging, configuration, error handling, and tests.

**Architecture:** App factory pattern (`create_app()`) with router-per-domain organization. Middleware stack handles correlation IDs, request logging, CORS, rate limiting, and security headers. Configuration via pydantic-settings from environment variables.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, pydantic-settings, structlog, slowapi, pytest, httpx, ruff, mypy

**Spec:** `docs/superpowers/specs/2026-03-12-api-001-fastapi-setup-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Create | Package config, deps, tool settings |
| `.env.example` | Create | Document expected environment variables |
| `src/__init__.py` | Create | Package marker (empty) |
| `src/config/__init__.py` | Create | Package marker (empty) |
| `src/config/settings.py` | Create | Pydantic BaseSettings with COGNIFY_ prefix |
| `src/utils/__init__.py` | Create | Package marker (empty) |
| `src/utils/logging.py` | Create | structlog processor chain setup |
| `src/api/__init__.py` | Create | Package marker (empty) |
| `src/api/errors.py` | Create | CognifyError hierarchy + exception handlers |
| `src/api/dependencies.py` | Create | Shared Depends() stubs |
| `src/api/rate_limiter.py` | Create | Shared slowapi Limiter instance |
| `src/api/routers/__init__.py` | Create | Package marker (empty) |
| `src/api/routers/health.py` | Create | Health + readiness endpoints |
| `src/api/middleware/__init__.py` | Create | Package marker (empty) |
| `src/api/middleware/correlation_id.py` | Create | X-Request-ID generation + propagation |
| `src/api/middleware/security_headers.py` | Create | Security response headers |
| `src/api/middleware/request_logging.py` | Create | structlog request/response logging |
| `src/api/main.py` | Create | create_app() factory, middleware registration |
| `src/models/__init__.py` | Create | Package marker (empty) |
| `src/services/__init__.py` | Create | Package marker (empty) |
| `src/agents/__init__.py` | Create | Package marker (empty) |
| `src/pipelines/__init__.py` | Create | Package marker (empty) |
| `tests/__init__.py` | Create | Package marker (empty) |
| `tests/conftest.py` | Create | Shared fixtures (app, client, settings) |
| `tests/unit/__init__.py` | Create | Package marker (empty) |
| `tests/unit/api/__init__.py` | Create | Package marker (empty) |
| `tests/unit/test_settings.py` | Create | Settings tests |
| `tests/unit/test_logging.py` | Create | Logging setup tests |
| `tests/unit/api/test_errors.py` | Create | Error handling tests |
| `tests/unit/api/test_health.py` | Create | Health + readiness endpoint tests |
| `tests/unit/api/test_middleware.py` | Create | Middleware tests |
| `tests/unit/api/test_app.py` | Create | App factory tests |
| `tests/integration/__init__.py` | Create | Package marker (empty) |

---

## Chunk 1: Project Tooling & Configuration

### Task 1: Create pyproject.toml and install dependencies

**Files:**
- Create: `pyproject.toml`

- [x] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cognify"
version = "0.1.0"
description = "Self-driving content platform — trend discovery, multi-agent research, article generation"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic-settings>=2.6.0",
    "structlog>=24.4.0",
    "slowapi>=0.1.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.27.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
disallow_any_generics = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
source = ["src"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

- [x] **Step 2: Install dependencies**

Run: `pip install -e ".[dev]"`
Expected: All packages install successfully, no version conflicts.

- [x] **Step 3: Verify tools work**

Run: `python -c "import fastapi; import structlog; import slowapi; print('OK')" && ruff --version && mypy --version && pytest --version`
Expected: All imports succeed, tools print versions.

- [x] **Step 4: Commit** (2fbb94f)

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml with runtime and dev dependencies"
```

---

### Task 2: Create Settings and .env.example

**Files:**
- Create: `src/__init__.py`, `src/config/__init__.py`, `src/config/settings.py`, `.env.example`
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/unit/api/__init__.py`, `tests/unit/test_settings.py`

- [x] **Step 1: Write the failing test for Settings**

Create all `__init__.py` package markers (empty files):
- `tests/__init__.py`
- `tests/unit/__init__.py`
- `tests/unit/api/__init__.py`

Create `tests/unit/test_settings.py`:

```python
import pytest

from src.config.settings import Settings


class TestSettings:
    def test_default_values(self) -> None:
        settings = Settings()
        assert settings.app_name == "Cognify"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.cors_allowed_origins == ["http://localhost:3000"]
        assert settings.rate_limit_default == "100/minute"
        assert settings.api_v1_prefix == "/api/v1"

    def test_env_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COGNIFY_DEBUG", "true")
        monkeypatch.setenv("COGNIFY_LOG_LEVEL", "DEBUG")
        settings = Settings()
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.config.settings'`

- [x] **Step 3: Create package markers and Settings**

Create `src/__init__.py` (empty).
Create `src/config/__init__.py` (empty).
Create `src/config/settings.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COGNIFY_")

    app_name: str = "Cognify"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]
    rate_limit_default: str = "100/minute"
    api_v1_prefix: str = "/api/v1"
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_settings.py -v`
Expected: 2 tests PASS.

- [x] **Step 5: Create .env.example**

```env
# Cognify Configuration
# All vars prefixed with COGNIFY_
# List values use JSON array format (pydantic-settings JSON parsing)

COGNIFY_DEBUG=true
COGNIFY_LOG_LEVEL=DEBUG
COGNIFY_CORS_ALLOWED_ORIGINS=["http://localhost:3000"]
COGNIFY_RATE_LIMIT_DEFAULT=100/minute
```

- [x] **Step 6: Commit** (0940ed4)

```bash
git add pyproject.toml src/__init__.py src/config/ tests/__init__.py tests/unit/ .env.example
git commit -m "feat: add pydantic-settings config with COGNIFY_ env prefix"
```

---

### Task 3: Set up structlog configuration

**Files:**
- Create: `src/utils/__init__.py`, `src/utils/logging.py`
- Create: `tests/unit/test_logging.py`

- [x] **Step 1: Write the failing test**

Create `tests/unit/test_logging.py`:

```python
import structlog

from src.utils.logging import setup_logging


class TestLogging:
    def test_setup_logging_production_mode(self) -> None:
        setup_logging(debug=False)
        config = structlog.get_config()
        processors = config["processors"]
        assert any(
            "JSONRenderer" in type(p).__name__
            for p in processors
        )

    def test_setup_logging_debug_mode(self) -> None:
        setup_logging(debug=True)
        config = structlog.get_config()
        processors = config["processors"]
        assert any(
            "ConsoleRenderer" in type(p).__name__
            for p in processors
        )
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_logging.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.utils.logging'`

- [x] **Step 3: Implement structlog setup**

Create `src/utils/__init__.py` (empty).
Create `src/utils/logging.py`:

```python
import logging

import structlog


def setup_logging(debug: bool = False) -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        renderer: structlog.types.Processor = (
            structlog.dev.ConsoleRenderer()
        )
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_logging.py -v`
Expected: 2 tests PASS.

- [x] **Step 5: Commit** (3863606)

```bash
git add src/utils/ tests/unit/test_logging.py
git commit -m "feat: add structlog configuration with JSON/console rendering"
```

---

## Chunk 2: Error Handling & Health Endpoints

### Task 4: Create error handling

**Files:**
- Create: `src/api/__init__.py`, `src/api/errors.py`
- Create: `tests/unit/api/test_errors.py`

- [x] **Step 1: Write the failing test**

Create `tests/unit/api/test_errors.py`:

```python
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
)

from src.api.errors import (
    CognifyError,
    CognifyValidationError,
    NotFoundError,
    RateLimitError,
    build_error_response,
)


class TestCognifyErrors:
    def test_cognify_error_base(self) -> None:
        err = CognifyError(
            status_code=400, code="bad_request", message="Bad"
        )
        assert err.status_code == 400
        assert err.code == "bad_request"
        assert err.message == "Bad"

    def test_not_found_error(self) -> None:
        err = NotFoundError(message="Topic not found")
        assert err.status_code == HTTP_404_NOT_FOUND
        assert err.code == "not_found"

    def test_validation_error(self) -> None:
        err = CognifyValidationError(message="Invalid input")
        assert err.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        assert err.code == "validation_error"

    def test_rate_limit_error(self) -> None:
        err = RateLimitError()
        assert err.status_code == HTTP_429_TOO_MANY_REQUESTS
        assert err.code == "rate_limited"

    def test_build_error_response(self) -> None:
        body = build_error_response(
            code="test_error", message="Test", details=["detail1"]
        )
        assert body == {
            "error": {
                "code": "test_error",
                "message": "Test",
                "details": ["detail1"],
            }
        }
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.errors'`

- [x] **Step 3: Implement error handling**

Create `src/api/__init__.py` (empty).
Create `src/api/errors.py`:

```python
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
)


def build_error_response(
    code: str,
    message: str,
    details: list[str] | None = None,
) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }


class CognifyError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(CognifyError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(
            status_code=HTTP_404_NOT_FOUND,
            code="not_found",
            message=message,
        )


class CognifyValidationError(CognifyError):
    def __init__(self, message: str = "Validation error") -> None:
        super().__init__(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message=message,
        )


class RateLimitError(CognifyError):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            code="rate_limited",
            message=message,
        )
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/api/test_errors.py -v`
Expected: 5 tests PASS.

- [x] **Step 5: Commit** (6e11112)

```bash
git add src/api/__init__.py src/api/errors.py tests/unit/api/test_errors.py
git commit -m "feat: add CognifyError hierarchy and standard error response builder"
```

---

### Task 5: Create health and readiness endpoints

**Files:**
- Create: `src/api/routers/__init__.py`, `src/api/routers/health.py`
- Create: `tests/unit/api/test_health.py`

Note: These tests intentionally use a bare FastAPI instance with only the health router to test the endpoints in isolation (no middleware). Full integration with the middleware stack is verified in Task 9 when the app factory is built.

- [x] **Step 1: Write the failing tests**

Create `tests/unit/api/test_health.py`:

```python
from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.routers.health import health_router
from src.config.settings import Settings


@pytest.fixture
def health_app() -> FastAPI:
    settings = Settings()
    app = FastAPI()
    app.state.settings = settings
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    return app


@pytest.fixture
async def health_client(
    health_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=health_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestHealthEndpoint:
    async def test_health_returns_200(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_health_response_shape(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "checks" in data

    async def test_health_version_matches_settings(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        data = response.json()
        assert data["version"] == "0.1.0"

    async def test_health_checks_all_unavailable(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        checks = response.json()["checks"]
        expected_keys = {"database", "redis", "weaviate", "celery"}
        assert set(checks.keys()) == expected_keys
        for value in checks.values():
            assert value == "unavailable"

    async def test_health_timestamp_valid_iso(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        ts = response.json()["timestamp"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo == timezone.utc

    async def test_health_status_healthy(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        assert response.json()["status"] == "healthy"


class TestReadinessEndpoint:
    async def test_readiness_returns_503_when_unavailable(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health/ready")
        assert response.status_code == 503

    async def test_readiness_response_has_same_shape(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health/ready")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "checks" in data

    async def test_readiness_status_unavailable(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health/ready")
        assert response.json()["status"] == "unavailable"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.routers.health'`

- [x] **Step 3: Implement health router**

Create `src/api/routers/__init__.py` (empty).
Create `src/api/routers/health.py`:

```python
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

CheckStatus = Literal["ok", "unavailable", "degraded"]


class DependencyChecks(BaseModel):
    database: CheckStatus = "unavailable"
    redis: CheckStatus = "unavailable"
    weaviate: CheckStatus = "unavailable"
    celery: CheckStatus = "unavailable"


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    checks: DependencyChecks


health_router = APIRouter()


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description=(
        "Returns service health status."
        " Public — no auth required."
    ),
)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    checks = DependencyChecks()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        checks=checks,
    )


@health_router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
    summary="Readiness check",
    description=(
        "Returns 200 when all dependencies are ready."
        " Internal — for k8s readiness probes."
    ),
)
async def readiness(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    checks = DependencyChecks()
    all_ok = all(
        v == "ok" for v in checks.model_dump().values()
    )
    response = HealthResponse(
        status="healthy" if all_ok else "unavailable",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        checks=checks,
    )
    return JSONResponse(
        content=response.model_dump(),
        status_code=200 if all_ok else 503,
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/api/test_health.py -v`
Expected: 9 tests PASS.

- [x] **Step 5: Commit** (11d2c2f)

```bash
git add src/api/routers/ tests/unit/api/test_health.py
git commit -m "feat: add health and readiness endpoints with dependency checks"
```

---

## Chunk 3: Middleware Stack

### Task 6: Correlation ID middleware

**Files:**
- Create: `src/api/middleware/__init__.py`, `src/api/middleware/correlation_id.py`
- Create: `tests/unit/api/test_middleware.py`

- [x] **Step 1: Write the failing tests**

Create `tests/unit/api/test_middleware.py`:

```python
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_middleware.py::TestCorrelationIdMiddleware -v`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Implement correlation ID middleware**

Create `src/api/middleware/__init__.py` (empty).
Create `src/api/middleware/correlation_id.py`:

```python
import re
import uuid
from contextvars import ContextVar

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

correlation_id_ctx: ContextVar[str] = ContextVar(
    "correlation_id", default=""
)

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
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/api/test_middleware.py::TestCorrelationIdMiddleware -v`
Expected: 5 tests PASS.

- [x] **Step 5: Commit** (42a8b5d)

```bash
git add src/api/middleware/ tests/unit/api/test_middleware.py
git commit -m "feat: add correlation ID middleware with X-Request-ID header"
```

---

### Task 7: Security headers middleware

**Files:**
- Create: `src/api/middleware/security_headers.py`
- Modify: `tests/unit/api/test_middleware.py` (append tests)

- [x] **Step 1: Write the failing tests**

Append to `tests/unit/api/test_middleware.py`:

```python
from src.api.middleware.security_headers import SecurityHeadersMiddleware


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
    async def test_x_content_type_options(
        self, sec_client: httpx.AsyncClient
    ) -> None:
        response = await sec_client.get("/test")
        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_x_frame_options(
        self, sec_client: httpx.AsyncClient
    ) -> None:
        response = await sec_client.get("/test")
        assert response.headers["x-frame-options"] == "DENY"

    async def test_content_security_policy(
        self, sec_client: httpx.AsyncClient
    ) -> None:
        response = await sec_client.get("/test")
        assert (
            response.headers["content-security-policy"]
            == "default-src 'self'"
        )
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_middleware.py::TestSecurityHeadersMiddleware -v`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Implement security headers middleware**

Create `src/api/middleware/security_headers.py`:

```python
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["content-security-policy"] = (
            "default-src 'self'"
        )
        return response
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/api/test_middleware.py::TestSecurityHeadersMiddleware -v`
Expected: 3 tests PASS.

- [x] **Step 5: Commit** (3dc3d22)

```bash
git add src/api/middleware/security_headers.py tests/unit/api/test_middleware.py
git commit -m "feat: add security headers middleware (CSP, X-Frame, X-Content-Type)"
```

---

### Task 8: Request logging middleware

**Files:**
- Create: `src/api/middleware/request_logging.py`
- Modify: `tests/unit/api/test_middleware.py` (append tests)

- [x] **Step 1: Write the failing tests**

Append to `tests/unit/api/test_middleware.py`:

```python
import json

from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.api.middleware.correlation_id import CorrelationIdMiddleware
from src.utils.logging import setup_logging


@pytest.fixture
def app_with_logging() -> FastAPI:
    """App with both logging and correlation ID middleware to test
    that correlation_id appears in log output."""
    app = FastAPI()
    # Register innermost first (logging), then outermost (correlation ID)
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_middleware.py::TestRequestLoggingMiddleware -v`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Implement request logging middleware**

Create `src/api/middleware/request_logging.py`:

```python
import time

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

from src.api.middleware.correlation_id import correlation_id_ctx

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
        duration_ms = round(
            (time.monotonic() - start) * 1000, 2
        )

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            correlation_id=correlation_id_ctx.get(""),
        )
        return response
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/api/test_middleware.py::TestRequestLoggingMiddleware -v`
Expected: 2 tests PASS.

- [x] **Step 5: Commit** (f65abcb)

```bash
git add src/api/middleware/request_logging.py tests/unit/api/test_middleware.py
git commit -m "feat: add request logging middleware with structlog and correlation IDs"
```

---

## Chunk 4: App Factory, Rate Limiting & Final Integration

### Task 9: Create dependency stubs, rate limiter, and app factory

**Files:**
- Create: `src/api/dependencies.py`, `src/api/rate_limiter.py`, `src/api/main.py`
- Create: `src/models/__init__.py`, `src/services/__init__.py`, `src/agents/__init__.py`, `src/pipelines/__init__.py`
- Create: `tests/conftest.py`, `tests/unit/api/test_app.py`

- [x] **Step 1: Write the failing tests**

Create `tests/conftest.py`:

```python
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(
    app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
```

Create `tests/unit/api/test_app.py`:

```python
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings


class TestCreateApp:
    def test_returns_fastapi_instance(self) -> None:
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_accepts_custom_settings(self) -> None:
        settings = Settings(app_version="9.9.9")
        app = create_app(settings)
        assert app.state.settings.app_version == "9.9.9"

    def test_health_endpoint_accessible(self) -> None:
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/api/v1/health" in routes

    def test_readiness_endpoint_accessible(self) -> None:
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/api/v1/health/ready" in routes

    def test_openapi_title(self) -> None:
        app = create_app()
        assert app.title == "Cognify API"

    def test_debug_never_enabled_on_fastapi(self) -> None:
        settings = Settings(debug=True)
        app = create_app(settings)
        assert app.debug is False
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.main'`

- [x] **Step 3: Create dependency stubs**

Create `src/api/dependencies.py`:

```python
async def get_current_user() -> None:
    """Placeholder — replaced by API-002 (JWT auth)."""


async def get_db_session() -> None:
    """Placeholder — replaced when database layer is added."""
```

- [x] **Step 4: Create shared rate limiter instance**

Create `src/api/rate_limiter.py`:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

- [x] **Step 5: Update health router with @limiter.exempt**

Modify `src/api/routers/health.py` — add the exempt decorator to both endpoints:

At the top, add import:
```python
from src.api.rate_limiter import limiter
```

Add `@limiter.exempt` decorator above `@health_router.get(...)` on both endpoints (outermost decorator, idiomatic slowapi convention):

```python
@limiter.exempt
@health_router.get(
    "/health",
    ...
)
async def health(request: Request) -> HealthResponse:
    ...

@limiter.exempt
@health_router.get(
    "/health/ready",
    ...
)
async def readiness(request: Request) -> JSONResponse:
    ...
```

- [x] **Step 6: Create app factory**

Create `src/api/main.py`:

```python
import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.errors import CognifyError, build_error_response
from src.api.middleware.correlation_id import CorrelationIdMiddleware
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.api.middleware.security_headers import SecurityHeadersMiddleware
from src.api.rate_limiter import limiter
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
    limiter._default_limits = [settings.rate_limit_default]

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
            content=build_error_response(
                code=exc.code, message=exc.message
            ),
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
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
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


def _register_middleware(
    app: FastAPI, settings: Settings
) -> None:
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


def _register_routers(
    app: FastAPI, settings: Settings
) -> None:
    app.include_router(
        health_router,
        prefix=settings.api_v1_prefix,
        tags=["health"],
    )
```

Create remaining empty `__init__.py` files:
- `src/models/__init__.py`
- `src/services/__init__.py`
- `src/agents/__init__.py`
- `src/pipelines/__init__.py`

- [x] **Step 7: Run test to verify it passes**

Run: `pytest tests/unit/api/test_app.py -v`
Expected: 6 tests PASS.

- [x] **Step 8: Commit** (f49c700 — Tasks 9–12 committed together)

```bash
git add src/api/main.py src/api/dependencies.py src/api/rate_limiter.py src/api/routers/health.py src/models/ src/services/ src/agents/ src/pipelines/ tests/conftest.py tests/unit/api/test_app.py
git commit -m "feat: add create_app() factory with middleware stack and exception handlers"
```

---

### Task 10: Rate limiting tests (including 429 verification)

**Files:**
- Modify: `tests/unit/api/test_middleware.py` (append rate limiting tests)

- [x] **Step 1: Write the rate limiting tests**

Append to `tests/unit/api/test_middleware.py`:

```python
from src.api.main import create_app
from src.api.rate_limiter import limiter
from src.config.settings import Settings


@pytest.fixture
def rate_limited_app() -> FastAPI:
    settings = Settings(rate_limit_default="2/minute")
    app = create_app(settings)

    # Add a non-exempt test route with explicit rate limit
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
            response = await rate_client.get(
                "/api/v1/test-rate-limit"
            )
            assert response.status_code == 200

        # 3rd request should be rate limited
        response = await rate_client.get(
            "/api/v1/test-rate-limit"
        )
        assert response.status_code == 429
        data = response.json()
        assert data["error"]["code"] == "rate_limited"
        assert data["error"]["message"] == "Rate limit exceeded"
```

- [x] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/api/test_middleware.py::TestRateLimiting -v`
Expected: 3 tests PASS. The test route uses `@limiter.limit("2/minute")` and `SlowAPIMiddleware` is registered in `create_app()`, so the 3rd request should return 429.

- [x] **Step 3: Commit** (f49c700)

```bash
git add tests/unit/api/test_middleware.py
git commit -m "test: add rate limiting tests with 429 error envelope verification"
```

---

### Task 11: Full suite validation, lint, type check

**Files:**
- Modify: any files with lint/type issues
- Create: `tests/integration/__init__.py`

- [x] **Step 1: Create integration test package marker**

Create `tests/integration/__init__.py` (empty).

- [x] **Step 2: Run full test suite with coverage**

Run: `pytest tests/ -v --cov=src --cov-report=term-missing`
Expected: All tests PASS, coverage >= 80%.

- [x] **Step 3: Run linting**

Run: `ruff check src/ tests/ && ruff format --check src/ tests/`
Expected: No lint errors. If there are errors, fix them (import ordering, unused imports, line length, etc.).

- [x] **Step 4: Run type checking**

Run: `mypy src/`
Expected: No type errors. If there are errors, add missing type annotations or fix type mismatches.

- [x] **Step 5: Fix any issues found**

Iterate on lint and type errors until all clean. Common fixes:
- Move any function-body imports to module top level
- Add missing return type annotations
- Fix `dict[str, object]` vs `dict[str, Any]` issues (use `object`, never `Any`)

- [x] **Step 6: Run full validation again**

Run: `pytest tests/ -v --cov=src --cov-report=term-missing && ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/`
Expected: All green.

- [x] **Step 7: Commit** (f49c700 — lint/type fixes included in combined commit)

```bash
git add -A
git commit -m "chore: fix lint/type errors, add integration test scaffold"
```

---

### Task 12: Dev server smoke test and final commit

**Files:**
- Possibly modify: `src/api/main.py` (add module-level app for uvicorn)

- [x] **Step 1: Verify dev server starts**

Run: `timeout 5 uvicorn src.api.main:create_app --factory --port 8000 || true`

In a separate step, test:
Run: `curl http://localhost:8000/api/v1/health` (or use `httpx` in a script)

Expected: Health endpoint returns JSON with `"status": "healthy"`.

If uvicorn needs a module-level `app`, add to bottom of `src/api/main.py`:
```python
app = create_app()
```

- [x] **Step 2: Final full validation**

Run: `pytest tests/ -v --cov=src --cov-report=term-missing && ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/`
Expected: All tests pass, coverage >= 80%, no lint or type errors.

- [x] **Step 3: Final commit** (f49c700 — final combined commit for Tasks 9–12)

```bash
git add -A
git commit -m "feat(api-001): complete FastAPI application setup"
```
