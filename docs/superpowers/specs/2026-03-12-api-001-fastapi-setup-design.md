# API-001: FastAPI Application Setup — Design Spec

**Story**: API-001 (Must, 5 SP)
**Date**: 2026-03-12
**Status**: Approved

## Overview

Foundational FastAPI application with middleware, health endpoint, structured logging, configuration, and project tooling. Auth (API-002) and RBAC (API-003) are separate stories — this setup leaves clean extension points for them.

## Scope

**In scope**: pyproject.toml, app factory, health + readiness endpoints, middleware (correlation ID, request logging, CORS, rate limiting, security headers), pydantic-settings config, error handling, structlog, tests, `.env.example`.

**Out of scope**: JWT auth, RBAC, database, Redis, Weaviate, Celery, WebSocket, any agent logic.

## 1. Project Tooling

### pyproject.toml

Single source of truth for packaging, dependencies, and tool configuration.

**Runtime dependencies**:
- `fastapi` — async web framework
- `uvicorn[standard]` — ASGI server
- `pydantic-settings` — env-driven config with `SecretStr`
- `structlog` — structured JSON logging
- `slowapi` — rate limiting (built on `limits`)

No `python-ulid` — correlation IDs use `uuid.uuid4()` from the standard library (sufficient for request tracing; sortability is not required).

**Dev dependencies**:
- `pytest`, `pytest-asyncio`, `pytest-cov` — testing
- `httpx` — async test client for FastAPI
- `ruff` — linting + formatting
- `mypy` — strict type checking

**Python**: 3.12+

### Tool Configuration (in pyproject.toml)

- **ruff**: line length 88, target Python 3.12, select rules (E, F, W, I, UP, B, SIM)
- **mypy**: strict mode, disallow `Any`
- **pytest**: asyncio_mode = "auto" (supersedes the per-test `@pytest.mark.asyncio` decorator convention from testing rules — all async tests auto-detected)
- **coverage**: source = ["src"], fail_under = 80

## 2. Application Structure

```
src/
  __init__.py
  api/
    __init__.py
    main.py              # create_app() factory, middleware registration
    routers/
      __init__.py
      health.py          # GET /api/v1/health, GET /api/v1/health/ready
    middleware/
      __init__.py
      correlation_id.py  # X-Request-ID generation + propagation
      request_logging.py # structlog request/response logging
    dependencies.py      # Shared Depends() stubs (see §2.1)
    errors.py            # CognifyError hierarchy + exception handlers
  config/
    __init__.py
    settings.py          # Pydantic BaseSettings
  utils/
    __init__.py
    logging.py           # structlog processor chain setup
tests/
  __init__.py
  conftest.py            # Shared fixtures (app, async client, test settings)
  unit/
    __init__.py
    api/
      __init__.py
      test_health.py     # Health + readiness endpoint tests
      test_middleware.py  # Correlation ID, logging, security headers, rate limiting
  integration/
    __init__.py
```

### Key Patterns

- **App factory**: `def create_app(settings: Settings | None = None) -> FastAPI`. When `settings` is `None`, constructs `Settings()` from environment. Tests pass explicit `Settings` instances with overrides.
- **Router-per-domain**: `health.py` is the first router, included via `app.include_router(health_router, prefix=settings.api_v1_prefix, tags=["health"])`. Future stories add `topics.py`, `articles.py`, etc. using the same convention.
- **Middleware as separate modules**: each does one thing, registered in order within `create_app()`.
- **All files < 200 lines, all functions < 20 lines, max 3 params** per coding standards.

### 2.1 Dependencies Stubs

`dependencies.py` contains placeholder signatures for future stories:

```python
async def get_current_user() -> None:
    """Placeholder — replaced by API-002 (JWT auth)."""

async def get_db_session() -> None:
    """Placeholder — replaced when database layer is added."""
```

These are not wired into any routes yet. They exist to document extension points.

## 3. Health Endpoints

### `GET /api/v1/health` — Liveness (public, no auth)

**Response model** (`HealthResponse`):
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-03-12T10:00:00Z",
  "checks": {
    "database": "unavailable",
    "redis": "unavailable",
    "weaviate": "unavailable",
    "celery": "unavailable"
  }
}
```

- Check status type: `Literal["ok", "unavailable", "degraded"]` — forward-compatible for when real checks land.
- All dependency checks return `"unavailable"` until those services are integrated in later stories.
- `version` read from `settings.app_version`.
- `timestamp` is current UTC in ISO 8601.
- OpenAPI: documented with `summary` and `description`.

### `GET /api/v1/health/ready` — Readiness (internal, for k8s readiness probe)

Returns 200 only when all dependency checks are `"ok"`. In this story, since all checks are `"unavailable"`, it returns **503 Service Unavailable** with the same `HealthResponse` body but `"status": "unavailable"`. This gives the infrastructure team a stable path to configure readiness probes from day one.

## 4. Middleware

### Correlation ID (`correlation_id.py`)
- Reads incoming `X-Request-ID` header; generates a `uuid4` string if absent.
- Validates incoming header: max 128 chars, `[A-Za-z0-9\-_]` only. Rejects invalid values by generating a new ID (prevents log injection).
- Stores in `contextvars.ContextVar` for structlog and downstream access.
- Sets `X-Request-ID` on response headers.

### Request Logging (`request_logging.py`)
- Logs on every request completion: `method`, `path`, `status_code`, `duration_ms`, `correlation_id`.
- Uses structlog — never logs request bodies (PII risk).
- Skips `/docs` and `/openapi.json` to reduce noise.

### CORS (FastAPI built-in `CORSMiddleware`)
- Origins from `Settings.cors_allowed_origins` — defaults to `["http://localhost:3000"]`.
- No wildcards in production.

### Rate Limiting (`slowapi`)
- Global default: 100 requests/minute per IP.
- Configurable via `Settings.rate_limit_default`.
- Health and readiness endpoints exempt via `@limiter.exempt` decorator on the route functions.

### Security Headers (custom middleware)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy: default-src 'self'` (permissive default; tightened in future stories)
- Note: `X-Request-ID` is handled by the correlation ID middleware. `Strict-Transport-Security` (HSTS) is handled at the ALB/ingress layer, not in-app.

### Middleware Execution Order

ASGI middleware registered last in code runs first on request. The spec defines **execution order** (outermost to innermost on request path):

1. Correlation ID (outermost — ensures all downstream middleware has a request ID)
2. Security headers
3. CORS
4. Rate limiting
5. Request logging (innermost — captures final status after all other middleware)

Registration in `create_app()` is reversed (request logging registered first, correlation ID last).

## 5. Configuration

### `Settings` class (pydantic-settings `BaseSettings`)

```python
app_name: str = "Cognify"
app_version: str = "0.1.0"
debug: bool = False
log_level: str = "INFO"
cors_allowed_origins: list[str] = ["http://localhost:3000"]
rate_limit_default: str = "100/minute"
api_v1_prefix: str = "/api/v1"
```

- `model_config = SettingsConfigDict(env_prefix="COGNIFY_")`
- Future stories add `database_url: SecretStr`, `redis_url: SecretStr`, etc.
- No `.env` committed; `.env.example` documents expected vars.
- `debug` controls **logging verbosity only** (colored console + DEBUG level). `FastAPI(debug=...)` is always `False` — the interactive Starlette debugger is never enabled, preventing stack trace exposure per the security checklist.

## 6. Error Handling

### Standard Error Response
```json
{
  "error": {
    "code": "not_found",
    "message": "Resource not found",
    "details": []
  }
}
```

### Implementation
- `CognifyError` base exception with `status_code: int`, `code: str`, `message: str`.
- Common subclasses: `NotFoundError`, `CognifyValidationError`, `RateLimitError`. Named `CognifyValidationError` to avoid collision with `pydantic.ValidationError`.
- Global exception handler in `create_app()` catches `CognifyError` and returns standard format.
- Override FastAPI's default 422 handler to wrap Pydantic `RequestValidationError` in the standard error envelope (code: `"validation_error"`, details populated from Pydantic's error list).
- Fallback handler for unhandled exceptions: returns 500 generic message, logs full traceback via structlog. Never exposes stack traces to clients.
- Rate limit 429 responses from slowapi are also wrapped in the standard error envelope via a custom `_rate_limit_exceeded_handler`.

## 7. Structured Logging

### structlog Configuration (`utils/logging.py`)

- **Production** (`debug=False`): JSON output via `structlog.processors.JSONRenderer`
- **Development** (`debug=True`): colored console via `structlog.dev.ConsoleRenderer`
- **Processor chain**: timestamper (ISO 8601 UTC), log level, correlation ID injection, renderer.
- Configured once at app startup from `create_app()`.
- Log levels follow observability plan: ERROR (unrecoverable), WARNING (recoverable), INFO (business events), DEBUG (diagnostics).

## 8. Testing

### TDD Approach
Tests written before implementation per testing rules. Red/Green/Refactor.

### Test Files

**`tests/conftest.py`**:
- `settings` fixture: returns `Settings` with test overrides
- `app` fixture: calls `create_app(settings)` — fresh per test
- `client` fixture: `httpx.AsyncClient` bound to app — async

**`tests/unit/api/test_health.py`**:
- Health returns 200
- Response has correct shape (status, version, timestamp, checks)
- Version matches settings
- All check keys present with "unavailable" value
- Timestamp is valid ISO 8601
- Readiness returns 503 when checks are unavailable
- Readiness response has same shape as health

**`tests/unit/api/test_middleware.py`**:
- Response includes `X-Request-ID` header (auto-generated)
- Custom `X-Request-ID` in request is echoed back
- Invalid `X-Request-ID` (too long or bad chars) is replaced with generated ID
- `X-Content-Type-Options: nosniff` present
- `X-Frame-Options: DENY` present
- `Content-Security-Policy` header present
- Request logging produces structlog output with expected fields
- Rate limiter allows requests under threshold
- Rate limiter returns 429 with standard error envelope when threshold exceeded

### Coverage Target
- 90%+ on API routes (per test strategy)
- All new code >= 80%

## 9. `.env.example`

```env
# Cognify Configuration
# All vars prefixed with COGNIFY_
# List values use JSON array format (pydantic-settings JSON parsing)

COGNIFY_DEBUG=true
COGNIFY_LOG_LEVEL=DEBUG
COGNIFY_CORS_ALLOWED_ORIGINS=["http://localhost:3000"]
COGNIFY_RATE_LIMIT_DEFAULT=100/minute
```

## Acceptance Criteria Mapping

| API-001 Criterion | Where |
|---|---|
| FastAPI app with router organization by domain | `main.py` + `routers/` |
| Middleware: CORS, request ID, structured logging, rate limiting | `middleware/` modules |
| Health endpoint: `/api/v1/health` | `routers/health.py` |
| Readiness endpoint: `/api/v1/health/ready` | `routers/health.py` |
| Auto-generated OpenAPI documentation at `/docs` | FastAPI default + config |
| Pydantic settings for configuration | `config/settings.py` |
