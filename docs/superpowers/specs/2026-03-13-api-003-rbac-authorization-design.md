# API-003: RBAC Authorization — Design Spec

**Ticket:** API-003 (RBAC Authorization)
**Status:** Draft
**Date:** 2026-03-13
**Branch:** `feature/API-003-rbac-authorization`
**Depends on:** API-002 (JWT Authentication) — Done

---

## Goal

Add role-based access control to the Cognify API using FastAPI dependencies. Three roles (admin, editor, viewer) form a clear hierarchy. Authorization is enforced per-route via `Depends()`, reusing the existing `get_current_user` dependency and `AuthorizationError` from API-002.

## Approach

**Simple role-check dependencies** — a factory function `require_role(*roles)` returns a FastAPI dependency that validates the authenticated user's role. Thin convenience wrappers provide common patterns. No permission enum, no role-permission mapping table — the three-role hierarchy doesn't warrant that complexity.

**Why not a permission-based system?** Three roles with a clear hierarchy (viewer < editor < admin) don't need indirection through a permission mapping. If granular permissions are ever needed, `require_role` can be extended to a permission-based check without breaking existing routes.

---

## 1. Authorization Dependencies (`src/api/dependencies.py`)

### 1.1 `require_role` Factory

```python
def require_role(
    *allowed_roles: Role,
) -> Callable[..., Awaitable[TokenPayload]]:
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
```

**Behavior:**
- Chains onto `get_current_user` — JWT validation happens first (401), then role check (403)
- Returns `TokenPayload` so routes can access user info
- Raises `AuthorizationError` (403, `"insufficient_permissions"`) on role mismatch
- Logs `authorization_denied` warning via structlog on denial (per security checklist)
- Uses `Role` type (not `str`) for `allowed_roles` to get static type checking — calling `require_role("admni")` is a mypy error
- `require_role()` with no arguments denies all roles (empty tuple, intentional behavior for testing)

### 1.2 Convenience Wrappers

```python
require_admin = require_role("admin")
require_editor_or_above = require_role("admin", "editor")
require_viewer_or_above = require_role("admin", "editor", "viewer")
```

**Usage in routes:**
```python
@router.get("/admin-only")
async def admin_endpoint(
    user: TokenPayload = Depends(require_admin),
) -> dict:
    return {"user_id": user.sub, "role": user.role}
```

### 1.3 Design Decisions

- **No middleware** — authorization is per-route, not global. Some routes (health, login) are public.
- **Factory, not decorator** — aligns with FastAPI's `Depends()` pattern used throughout the codebase.
- **Returns `TokenPayload`** — routes get both authentication and authorization in one dependency, no double-unwrapping.
- **Role hierarchy is implicit** — `require_editor_or_above` lists both "admin" and "editor" explicitly rather than encoding a hierarchy. This is simpler and more readable for 3 roles.

---

## 2. Error Handling

No changes needed. `AuthorizationError` already exists in `src/api/errors.py`:

```python
class AuthorizationError(CognifyError):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            status_code=HTTP_403_FORBIDDEN,
            code="insufficient_permissions",
            message=message,
        )
```

The existing `CognifyError` exception handler in `main.py` already catches and formats this as:

```json
{
  "error": {
    "code": "insufficient_permissions",
    "message": "Role 'viewer' is not authorized for this resource",
    "details": []
  }
}
```

---

## 3. Admin Check Route (`src/api/routers/admin.py`)

A minimal admin-only route to verify RBAC works end-to-end and serve as a reference for future admin routes.

| Method | Path | Auth | Role | Response | Description |
|--------|------|------|------|----------|-------------|
| GET | `/admin/check` | Bearer JWT | admin | 200 JSON | Verify admin access |

### Response schema (defined inline in `src/api/routers/admin.py`)

```python
class RoleCheckResponse(BaseModel):
    user_id: str
    role: str
    message: str  # "Admin access verified"
```

### Behavior

- Returns 200 with user info for admin role
- Returns 403 `"insufficient_permissions"` for editor/viewer
- Returns 401 `"invalid_token"` for unauthenticated requests

**Why a separate router file?** Keeps admin routes isolated from auth routes. Future admin-only endpoints (settings, API key management) will go here.

---

## 4. App Registration (`src/api/main.py`)

Register the admin router alongside existing routers:

```python
app.include_router(
    admin_router,
    prefix=settings.api_v1_prefix,
    tags=["admin"],
)
```

No new middleware, repositories, or app state needed.

---

## 5. Testing Strategy

### 5.1 Unit Tests — Dependencies (`tests/unit/api/test_rbac.py`)

Test `require_role` factory in isolation:

| Test Case | Input Role | Allowed Roles | Expected |
|-----------|-----------|---------------|----------|
| Admin accessing admin-only | admin | ("admin",) | Returns TokenPayload |
| Editor accessing admin-only | editor | ("admin",) | Raises AuthorizationError |
| Viewer accessing admin-only | viewer | ("admin",) | Raises AuthorizationError |
| Admin accessing editor-or-above | admin | ("admin", "editor") | Returns TokenPayload |
| Editor accessing editor-or-above | editor | ("admin", "editor") | Returns TokenPayload |
| Viewer accessing editor-or-above | viewer | ("admin", "editor") | Raises AuthorizationError |
| Any role accessing viewer-or-above | admin/editor/viewer | ("admin", "editor", "viewer") | Returns TokenPayload |
| Empty allowed roles | admin | () | Raises AuthorizationError |

Test that:
- `AuthorizationError` has status code 403
- `AuthorizationError` has code `"insufficient_permissions"`
- Error message includes the user's actual role

### 5.2 Endpoint Tests — Admin Route (`tests/unit/api/test_admin_endpoints.py`)

Test the `/api/v1/admin/check` endpoint:

| Test Case | Token Role | Expected Status | Expected Body |
|-----------|-----------|----------------|---------------|
| Admin access | admin | 200 | `{"user_id": ..., "role": "admin", "message": "Admin access verified"}` |
| Editor denied | editor | 403 | `{"error": {"code": "insufficient_permissions", ...}}` |
| Viewer denied | viewer | 403 | `{"error": {"code": "insufficient_permissions", ...}}` |
| No token | — | 401 | `{"error": {"code": "invalid_token", ...}}` |
| Expired token | admin (expired) | 401 | `{"error": {"code": "invalid_token", ...}}` |

### 5.3 Test Fixtures

Extract shared auth test helpers into `tests/unit/api/conftest.py`:

- Move RSA key pair generation, `auth_settings`, and `auth_app` fixtures from API-002 test files into the shared conftest
- Add `make_token(role: Role, settings: Settings) -> str` — a plain function wrapping `create_access_token` with a default user_id, used across both RBAC and admin endpoint tests
- Add `make_auth_header(role: Role, settings: Settings) -> dict` — returns `{"Authorization": f"Bearer {make_token(role, settings)}"}`
- API-002 tests continue to work unchanged (fixtures just move to a shared location)

---

## 6. Intended Role Mapping for Future Routes

| Route Category | Required Role | Dependency | Ticket |
|---------------|--------------|------------|--------|
| Health, docs | Public (no auth) | — | API-001 |
| Auth (login, refresh, logout) | Public (no auth) | — | API-002 |
| Admin (settings, API keys, platforms) | admin | `require_admin` | DASH-005, future |
| Content (articles, research, publishing) | admin, editor | `require_editor_or_above` | CONTENT-*, PUBLISH-* |
| Read-only (dashboard, topics, status) | admin, editor, viewer | `require_viewer_or_above` | DASH-001 through DASH-004 |

This mapping guides future ticket implementers. Each ticket decides its own per-route dependency.

---

## 7. File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/api/dependencies.py` | Modify | Add `require_role`, `require_admin`, `require_editor_or_above`, `require_viewer_or_above` |
| `src/api/routers/admin.py` | Create | Admin check endpoint with `RoleCheckResponse` schema |
| `src/api/main.py` | Modify | Register admin_router |
| `tests/unit/api/conftest.py` | Create | Shared auth fixtures (RSA keys, `make_token`, `make_auth_header`) |
| `tests/unit/api/test_rbac.py` | Create | Unit tests for role-check dependencies |
| `tests/unit/api/test_admin_endpoints.py` | Create | Endpoint tests for admin route |

---

## 8. Out of Scope

- Per-action permission checks (e.g., `can_edit_article`) — not needed until content management endpoints exist
- Role management endpoints (assign/change roles) — requires database layer
- Role hierarchy encoding (viewer < editor < admin) — explicit listing is sufficient for 3 roles
- Middleware-based authorization — per-route `Depends()` is the correct pattern
- Database-backed permission store — roles are in JWT claims, no lookup needed
