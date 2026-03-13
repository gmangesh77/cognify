# API-003: RBAC Authorization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add role-based access control via `require_role()` FastAPI dependency factory, with convenience wrappers and an admin-only verification endpoint.

**Architecture:** `require_role(*Role)` factory returns a FastAPI dependency that chains onto the existing `get_current_user` (JWT validation → role check). Three convenience wrappers (`require_admin`, `require_editor_or_above`, `require_viewer_or_above`) cover all common patterns. A `/admin/check` endpoint demonstrates and verifies RBAC end-to-end.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, structlog, pytest, pytest-asyncio

**Spec:** [`docs/superpowers/specs/2026-03-13-api-003-rbac-authorization-design.md`](../specs/2026-03-13-api-003-rbac-authorization-design.md)

**Conda env:** `cognify` — run tests with `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest ...`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `tests/unit/api/conftest.py` | Create | Shared auth test fixtures: RSA keys, settings, app, client, `make_token`, `make_auth_header` |
| `tests/unit/api/test_auth_endpoints.py` | Modify | Remove duplicated fixtures (use shared conftest) |
| `tests/unit/api/test_rbac.py` | Create | Unit tests for `require_role` factory |
| `src/api/dependencies.py` | Modify | Add `require_role`, `require_admin`, `require_editor_or_above`, `require_viewer_or_above` |
| `tests/unit/api/test_admin_endpoints.py` | Create | Endpoint tests for `/admin/check` |
| `src/api/routers/admin.py` | Create | Admin check endpoint with `RoleCheckResponse` |
| `src/api/main.py` | Modify | Register `admin_router` |
| `project-management/PROGRESS.md` | Modify | Update ticket status |

---

## Chunk 1: Shared Test Fixtures and RBAC Unit Tests

### Task 1: Extract shared test fixtures into `tests/unit/api/conftest.py`

**Files:**
- Create: `tests/unit/api/conftest.py`
- Modify: `tests/unit/api/test_auth_endpoints.py` (remove duplicated fixtures)

The existing `test_auth_endpoints.py` defines RSA key generation, `auth_settings`, `auth_app`, `auth_client`, and `reset_rate_limiter` fixtures locally. These need to be shared with the new RBAC and admin endpoint tests. Extract them into a shared conftest and add `make_token` / `make_auth_header` helpers.

- [x] **Step 1: Create `tests/unit/api/conftest.py` with shared fixtures**

```python
"""Shared test fixtures for API unit tests.

Provides RSA key pair, auth-configured Settings, FastAPI app, and httpx client
fixtures used by auth, RBAC, and admin endpoint tests.
"""

from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.auth.password import hash_password
from src.api.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
from src.api.auth.schemas import Role, UserData
from src.api.auth.tokens import create_access_token
from src.api.main import create_app
from src.config.settings import Settings


def _generate_rsa_keys() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


_PRIVATE_KEY, _PUBLIC_KEY = _generate_rsa_keys()
TEST_PASSWORD = "test-password-123"
TEST_USER = UserData(
    id="user-1",
    email="test@example.com",
    password_hash=hash_password(TEST_PASSWORD),
    role="editor",
)


def make_token(role: Role, settings: Settings) -> str:
    """Create a valid access token for the given role."""
    return create_access_token("user-1", role, settings)


def make_auth_header(role: Role, settings: Settings) -> dict[str, str]:
    """Create an Authorization header dict for the given role."""
    return {"Authorization": f"Bearer {make_token(role, settings)}"}


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Reset the in-memory rate limiter storage before each test."""
    from src.api.rate_limiter import limiter

    limiter.reset()


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
    )


@pytest.fixture
def auth_app(auth_settings: Settings) -> FastAPI:
    app = create_app(auth_settings)
    app.state.user_repo = InMemoryUserRepository([TEST_USER])
    app.state.refresh_repo = InMemoryRefreshTokenRepository()
    return app


@pytest.fixture
async def auth_client(
    auth_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=auth_app),
        base_url="http://test",
    ) as ac:
        yield ac
```

- [x] **Step 2: Remove duplicated fixtures from `test_auth_endpoints.py`**

Remove everything from the top of `test_auth_endpoints.py` down to (but not including) `class TestLoginEndpoint`. Replace with imports from conftest. The file should start with:

```python
import fastapi
import httpx
from fastapi import FastAPI

from src.api.auth.tokens import create_access_token
from src.config.settings import Settings

from .conftest import TEST_PASSWORD
```

Remove these items that are now in conftest:
- `_generate_rsa_keys()` function
- `_PRIVATE_KEY`, `_PUBLIC_KEY` module-level variables
- `_TEST_PASSWORD`, `_TEST_USER` module-level variables
- `reset_rate_limiter` fixture
- `auth_settings` fixture
- `auth_app` fixture
- `auth_client` fixture

Update all references from `_TEST_PASSWORD` to `TEST_PASSWORD` (imported from conftest).

- [x] **Step 3: Run existing tests to verify no regressions**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_auth_endpoints.py -v`
Expected: All existing tests PASS (fixtures now come from shared conftest)

- [x] **Step 4: Run full auth unit tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_auth.py -v`
Expected: All PASS (these tests have their own local fixtures, unaffected)

- [x] **Step 5: Commit**

```bash
git add tests/unit/api/conftest.py tests/unit/api/test_auth_endpoints.py
git commit -m "refactor: extract shared auth test fixtures into conftest"
```

---

### Task 2: Write failing RBAC unit tests

**Files:**
- Create: `tests/unit/api/test_rbac.py`

Write all unit tests for `require_role` factory. These test the dependency logic in isolation by constructing `TokenPayload` objects directly (no HTTP requests, no app needed).

- [x] **Step 1: Write `tests/unit/api/test_rbac.py`**

```python
"""Unit tests for RBAC authorization dependencies."""

import pytest
import structlog.testing

from src.api.auth.schemas import TokenPayload
from src.api.errors import AuthorizationError


def _make_payload(role: str) -> TokenPayload:
    """Create a TokenPayload with the given role for testing."""
    return TokenPayload(
        sub="user-1",
        role=role,  # type: ignore[arg-type]
        exp=9999999999,
        iat=0,
        jti="test-jti",
    )


class TestRequireRole:
    """Test the require_role dependency factory."""

    async def test_admin_allowed_for_admin_only(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin")
        result = await checker(current_user=_make_payload("admin"))
        assert result.sub == "user-1"
        assert result.role == "admin"

    async def test_editor_denied_for_admin_only(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin")
        with pytest.raises(AuthorizationError) as exc_info:
            await checker(current_user=_make_payload("editor"))
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == "insufficient_permissions"
        assert "editor" in exc_info.value.message

    async def test_viewer_denied_for_admin_only(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin")
        with pytest.raises(AuthorizationError) as exc_info:
            await checker(current_user=_make_payload("viewer"))
        assert exc_info.value.status_code == 403
        assert "viewer" in exc_info.value.message

    async def test_admin_allowed_for_editor_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor")
        result = await checker(current_user=_make_payload("admin"))
        assert result.role == "admin"

    async def test_editor_allowed_for_editor_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor")
        result = await checker(current_user=_make_payload("editor"))
        assert result.role == "editor"

    async def test_viewer_denied_for_editor_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor")
        with pytest.raises(AuthorizationError):
            await checker(current_user=_make_payload("viewer"))

    async def test_admin_allowed_for_viewer_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor", "viewer")
        result = await checker(current_user=_make_payload("admin"))
        assert result.role == "admin"

    async def test_editor_allowed_for_viewer_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor", "viewer")
        result = await checker(current_user=_make_payload("editor"))
        assert result.role == "editor"

    async def test_viewer_allowed_for_viewer_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor", "viewer")
        result = await checker(current_user=_make_payload("viewer"))
        assert result.role == "viewer"

    async def test_empty_roles_denies_all(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role()
        with pytest.raises(AuthorizationError):
            await checker(current_user=_make_payload("admin"))

    async def test_denial_logs_warning(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin")
        with structlog.testing.capture_logs() as logs:
            with pytest.raises(AuthorizationError):
                await checker(current_user=_make_payload("editor"))
        denied = [l for l in logs if l["event"] == "authorization_denied"]
        assert len(denied) == 1
        assert denied[0]["user_id"] == "user-1"
        assert denied[0]["role"] == "editor"
        assert denied[0]["log_level"] == "warning"


class TestConvenienceWrappers:
    """Test pre-built convenience wrappers."""

    async def test_require_admin_allows_admin(self) -> None:
        from src.api.dependencies import require_admin

        result = await require_admin(current_user=_make_payload("admin"))
        assert result.role == "admin"

    async def test_require_admin_denies_editor(self) -> None:
        from src.api.dependencies import require_admin

        with pytest.raises(AuthorizationError):
            await require_admin(current_user=_make_payload("editor"))

    async def test_require_editor_or_above_allows_editor(self) -> None:
        from src.api.dependencies import require_editor_or_above

        result = await require_editor_or_above(
            current_user=_make_payload("editor")
        )
        assert result.role == "editor"

    async def test_require_editor_or_above_denies_viewer(self) -> None:
        from src.api.dependencies import require_editor_or_above

        with pytest.raises(AuthorizationError):
            await require_editor_or_above(
                current_user=_make_payload("viewer")
            )

    async def test_require_viewer_or_above_allows_viewer(self) -> None:
        from src.api.dependencies import require_viewer_or_above

        result = await require_viewer_or_above(
            current_user=_make_payload("viewer")
        )
        assert result.role == "viewer"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_rbac.py -v`
Expected: FAIL — `require_role` does not exist yet in `src/api/dependencies.py`

- [x] **Step 3: Commit failing tests**

```bash
git add tests/unit/api/test_rbac.py
git commit -m "test: add failing RBAC unit tests (red phase)"
```

---

### Task 3: Implement `require_role` and convenience wrappers

**Files:**
- Modify: `src/api/dependencies.py`

- [x] **Step 1: Add `require_role` factory and wrappers to `src/api/dependencies.py`**

Add the following imports at the top of the file (merge with existing imports):

```python
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Depends, Header, Request

from src.api.auth.schemas import Role, TokenPayload
from src.api.auth.tokens import decode_access_token
from src.api.errors import AuthenticationError, AuthorizationError

logger = structlog.get_logger()
```

Add after the existing `get_db_session` function:

```python
def require_role(
    *allowed_roles: Role,
) -> Callable[..., Awaitable[TokenPayload]]:
    """Factory that returns a FastAPI dependency checking user role.

    Usage: ``user: TokenPayload = Depends(require_role("admin", "editor"))``
    """

    async def _check_role(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if current_user.role not in allowed_roles:
            logger.warning(
                "authorization_denied",
                user_id=current_user.sub,
                role=current_user.role,
                required_roles=allowed_roles,
            )
            raise AuthorizationError(
                message=f"Role '{current_user.role}' is not authorized"
                " for this resource",
            )
        return current_user

    return _check_role


require_admin = require_role("admin")
require_editor_or_above = require_role("admin", "editor")
require_viewer_or_above = require_role("admin", "editor", "viewer")
```

- [x] **Step 2: Run RBAC unit tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_rbac.py -v`
Expected: All 15 tests PASS

- [x] **Step 3: Run full test suite to check for regressions**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v`
Expected: All tests PASS

- [x] **Step 4: Commit**

```bash
git add src/api/dependencies.py
git commit -m "feat: add require_role RBAC dependency factory with convenience wrappers"
```

---

## Chunk 2: Admin Endpoint and Finalization

### Task 4: Write failing admin endpoint tests

**Files:**
- Create: `tests/unit/api/test_admin_endpoints.py`

- [x] **Step 1: Write `tests/unit/api/test_admin_endpoints.py`**

```python
"""Endpoint tests for admin routes (RBAC enforcement)."""

import httpx
import pytest
from freezegun import freeze_time

from src.config.settings import Settings

from .conftest import make_auth_header


class TestAdminCheckEndpoint:
    """Test GET /api/v1/admin/check role enforcement."""

    async def test_admin_access_succeeds(
        self,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("admin", auth_settings)
        response = await auth_client.get(
            "/api/v1/admin/check", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user-1"
        assert data["role"] == "admin"
        assert data["message"] == "Admin access verified"

    async def test_editor_denied(
        self,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        response = await auth_client.get(
            "/api/v1/admin/check", headers=headers
        )
        assert response.status_code == 403
        assert (
            response.json()["error"]["code"] == "insufficient_permissions"
        )

    async def test_viewer_denied(
        self,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        response = await auth_client.get(
            "/api/v1/admin/check", headers=headers
        )
        assert response.status_code == 403
        assert (
            response.json()["error"]["code"] == "insufficient_permissions"
        )

    async def test_no_token_returns_401(
        self,
        auth_client: httpx.AsyncClient,
    ) -> None:
        response = await auth_client.get("/api/v1/admin/check")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_token"

    async def test_expired_token_returns_401(
        self,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        with freeze_time("2026-01-01 00:00:00"):
            headers = make_auth_header("admin", auth_settings)
        with freeze_time("2026-01-01 00:16:00"):
            response = await auth_client.get(
                "/api/v1/admin/check", headers=headers
            )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_token"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_admin_endpoints.py -v`
Expected: FAIL — `/api/v1/admin/check` route does not exist yet (404 or similar)

- [x] **Step 3: Commit failing tests**

```bash
git add tests/unit/api/test_admin_endpoints.py
git commit -m "test: add failing admin endpoint tests (red phase)"
```

---

### Task 5: Implement admin router and register it

**Files:**
- Create: `src/api/routers/admin.py`
- Modify: `src/api/main.py`

- [x] **Step 1: Create `src/api/routers/admin.py`**

```python
"""Admin routes — requires admin role."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_admin

admin_router = APIRouter()


class RoleCheckResponse(BaseModel):
    user_id: str
    role: str
    message: str


@admin_router.get(
    "/admin/check",
    response_model=RoleCheckResponse,
    summary="Verify admin access",
)
async def admin_check(
    user: TokenPayload = Depends(require_admin),
) -> RoleCheckResponse:
    return RoleCheckResponse(
        user_id=user.sub,
        role=user.role,
        message="Admin access verified",
    )
```

- [x] **Step 2: Register `admin_router` in `src/api/main.py`**

Add import at the top (alongside existing router imports):

```python
from src.api.routers.admin import admin_router
```

Add to the `_register_routers` function, after the existing `auth_router` registration:

```python
    app.include_router(
        admin_router,
        prefix=settings.api_v1_prefix,
        tags=["admin"],
    )
```

- [x] **Step 3: Run admin endpoint tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_admin_endpoints.py -v`
Expected: All 5 tests PASS

- [x] **Step 4: Run full test suite**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v`
Expected: All tests PASS (no regressions)

- [x] **Step 5: Commit**

```bash
git add src/api/routers/admin.py src/api/main.py
git commit -m "feat: add admin check endpoint with RBAC enforcement"
```

---

### Task 6: Lint, type-check, and final verification

**Files:** None (verification only)

- [x] **Step 1: Run linter**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/ tests/`
Expected: No errors

- [x] **Step 2: Run formatter check**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/ tests/`
Expected: No formatting issues

- [x] **Step 3: Run type checker**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/`
Expected: No errors (or only pre-existing ones)

- [x] **Step 4: Run full test suite with coverage**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ --cov=src --cov-report=term-missing -v`
Expected: All tests pass, new code has ≥80% coverage

- [x] **Step 5: Fix any issues found, then commit**

If lint/type/test issues are found, fix them and commit:
```bash
git commit -m "fix: resolve lint/type issues in RBAC implementation"
```

---

### Task 7: Update progress tracking

**Files:**
- Modify: `project-management/PROGRESS.md`

- [x] **Step 1: Update API-003 row in PROGRESS.md**

Change the API-003 row from:

```
| API-003 | RBAC Authorization        | Backlog | —                               | —                                                                     | —                                                                            |
```

To:

```
| API-003 | RBAC Authorization        | Done    | `feature/API-003-rbac-authorization` | [plan](../docs/superpowers/plans/2026-03-13-api-003-rbac-authorization.md) | [spec](../docs/superpowers/specs/2026-03-13-api-003-rbac-authorization-design.md) |
```

- [x] **Step 2: Commit**

```bash
git add project-management/PROGRESS.md
git commit -m "docs: update progress tracking for API-003 RBAC authorization"
```
