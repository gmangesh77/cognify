# API-002: JWT Authentication — Design Spec

**Ticket:** API-002 (JWT Authentication)
**Status:** Approved
**Date:** 2026-03-12
**Branch:** `feature/API-002-jwt-authentication`
**Depends on:** API-001 (FastAPI Application Setup) — Done

---

## Goal

Add JWT-based authentication to the Cognify API with RS256 signing, refresh token rotation, and logout. Build the auth logic and FastAPI dependencies with repository interfaces, stubbing actual persistence. No user registration endpoint — tests use fixtures.

## Approach

- **PyJWT[crypto]** for JWT encode/decode with RS256
- **bcrypt** for password hashing (cost factor >= 12)
- **Repository interfaces** (Protocol) for refresh tokens and users, with in-memory stubs
- Swappable for Redis/PostgreSQL when database layer is added

---

## 1. Dependencies

### New packages

| Package | Version | Purpose |
|---------|---------|---------|
| `PyJWT[crypto]` | `>=2.9.0` | JWT encode/decode with RS256 support |
| `bcrypt` | `>=4.2.0` | Password hashing |
| `email-validator` | `>=2.2.0` | Pydantic `EmailStr` validation |
| `freezegun` | `>=1.4.0` | Dev: time freezing for token expiry edge-case tests |

### New settings (`src/config/settings.py`)

```python
jwt_private_key: str = ""                    # RSA private key PEM
jwt_public_key: str = ""                     # RSA public key PEM
jwt_algorithm: str = "RS256"
jwt_access_token_expire_minutes: int = 15
jwt_refresh_token_expire_days: int = 7
```

Loaded from `COGNIFY_JWT_PRIVATE_KEY` / `COGNIFY_JWT_PUBLIC_KEY` environment variables. For dev/testing, a test fixture generates a throwaway RSA key pair.

---

## 2. Service Layer

### 2.1 Password Service (`src/api/auth/password.py`)

Pure functions, no state:

- `hash_password(plain: str) -> str` — bcrypt hash with cost factor 12
- `verify_password(plain: str, hashed: str) -> bool` — constant-time comparison (bcrypt native)

### 2.2 Token Service (`src/api/auth/tokens.py`)

Stateless JWT operations:

- `create_access_token(user_id: str, role: str, settings: Settings) -> str`
  - Signs JWT with RS256 private key
  - Claims: `sub` (user_id), `role`, `exp`, `iat`, `jti` (UUID)
- `create_refresh_token() -> str`
  - Generates opaque UUID (not a JWT)
- `decode_access_token(token: str, settings: Settings) -> TokenPayload`
  - Validates RS256 signature and expiry
  - Returns parsed claims as `TokenPayload`
  - Raises `AuthenticationError` on invalid/expired tokens

### 2.3 Refresh Token Repository (`src/api/auth/repository.py`)

Protocol + in-memory implementation:

```python
class RefreshTokenRepository(Protocol):
    def save(self, user_id: str, token: str, expires_at: datetime) -> None: ...
    def get(self, token: str) -> RefreshTokenData | None: ...
    def revoke(self, token: str) -> None: ...        # Mark as revoked (do NOT delete — needed for replay detection)
    def revoke_all_for_user(self, user_id: str) -> None: ...  # Revoke all tokens for user (replay attack response)

class UserRepository(Protocol):
    def get_by_email(self, email: str) -> UserData | None: ...
```

`InMemoryRefreshTokenRepository` and `InMemoryUserRepository` — dict-based implementations for dev/testing. Replaced by real implementations when database layer is added.

**Expiry ownership:** The repository's `get()` method returns the raw `RefreshTokenData` including `expires_at` and `revoked` fields. The `AuthService` is responsible for checking expiry and revocation status. This keeps the repository as a simple storage layer and puts business logic in the service.

### 2.4 Auth Service (`src/api/auth/service.py`)

Orchestrates login/refresh/logout flows:

- `login(email: str, password: str) -> TokenPair` — validates credentials, creates both tokens, stores refresh token
- `refresh(refresh_token: str) -> TokenPair` — validates refresh token, revokes old, issues new pair (rotation)
- `logout(refresh_token: str) -> None` — revokes refresh token

Depends on: Token Service, Password Service, RefreshTokenRepository, UserRepository.

---

## 3. Schemas (`src/api/auth/schemas.py`)

### Request schemas

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class RefreshRequest(BaseModel):
    refresh_token: str
```

### Response schemas

```python
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
```

### Shared types

```python
Role = Literal["admin", "editor", "viewer"]
```

### Internal data models

```python
class TokenPayload(BaseModel):
    sub: str        # user_id
    role: Role
    exp: int        # expiry timestamp
    iat: int        # issued at
    jti: str        # unique token ID

class RefreshTokenData(BaseModel):
    user_id: str
    token: str
    expires_at: datetime
    revoked: bool = False    # Needed for replay detection

class UserData(BaseModel):
    id: str
    email: str
    password_hash: str
    role: Role
```

---

## 4. Router & Endpoints (`src/api/routers/auth.py`)

All under `/api/v1/auth`:

| Method | Path | Auth | Rate Limit | Response | Description |
|--------|------|------|------------|----------|-------------|
| POST | `/auth/login` | Public | 5/minute | 200 `TokenResponse` | Authenticate with email + password |
| POST | `/auth/refresh` | Public | 10/minute | 200 `TokenResponse` | Rotate refresh token, return new pair |
| POST | `/auth/logout` | Public | 10/minute | 204 No Content | Revoke refresh token |

### Login flow

1. Validate `LoginRequest` (email + password)
2. Look up user by email via `UserRepository`
3. Verify password hash
4. Create access token + refresh token
5. Store refresh token in repository
6. Return `TokenResponse`
7. On failure: 401 `"invalid_credentials"` (same message for bad email or bad password)

### Refresh flow

1. Validate `RefreshRequest`
2. Look up refresh token in repository
3. If not found: 401 `"invalid_refresh_token"`
4. If found but already revoked (replay detected): call `revoke_all_for_user(user_id)` to invalidate all sessions for that user, then return 401 `"invalid_refresh_token"`. This defends against refresh token theft per RFC 6749 Section 10.4.
5. If found but expired: 401 `"invalid_refresh_token"`
6. Revoke old refresh token (mark as revoked, do not delete — needed for replay detection)
7. Create new access + refresh token pair
8. Store new refresh token
9. Return `TokenResponse`

### Logout flow

1. Accept `RefreshRequest` body (no bearer token required — a user with an expired access token can still log out)
2. Look up refresh token in repository
3. If found and active: revoke it
4. Return 204 No Content (idempotent — always returns 204 regardless of whether token existed)

**Rationale:** Logout does not require a valid access token. The refresh token itself is sufficient proof of session ownership. Requiring a valid access token would block users whose access token just expired from logging out.

---

## 5. FastAPI Dependency (`src/api/dependencies.py`)

Replace the existing `get_current_user` stub:

```python
async def get_current_user(
    request: Request,
    authorization: str = Header(alias="Authorization"),
) -> TokenPayload:
    # 1. Validate header format: must be "Bearer <token>" (split on space, expect 2 parts)
    # 2. Extract token string (second part after "Bearer ")
    # 3. Decode with decode_access_token() using request.app.state.settings
    #    - Must pass algorithms=["RS256"] explicitly to prevent algorithm confusion attacks
    # 4. Return TokenPayload
    # 5. On any failure: raise AuthenticationError(401, "invalid_token", "Invalid or expired token")
```

**Notes:**
- No existing routes depend on the current `get_current_user` stub (only health.py exists and it does not use it), so replacing the stub is safe.
- Protected routes use: `current_user: TokenPayload = Depends(get_current_user)`
- Public routes (health, login, refresh, logout) simply don't include the dependency.

---

## 6. Error Handling

### New error subclasses (`src/api/errors.py`)

- `AuthenticationError(CognifyError)` — 401
  - Codes: `"invalid_credentials"`, `"invalid_token"`, `"invalid_refresh_token"`
- `AuthorizationError(CognifyError)` — 403
  - Code: `"insufficient_permissions"` (used by API-003 RBAC, defined now for completeness)

### Security hardening

- Same error message for bad email vs. bad password (prevents user enumeration)
- Constant-time password comparison (bcrypt handles natively)
- Refresh tokens are opaque UUIDs — no user info leaked if intercepted
- `jti` claim on access tokens enables future per-token revocation
- Sensitive fields excluded from structlog: `password`, `token`, `refresh_token`, `private_key`

### Rate limiting

- `/auth/login` — `5/minute` per IP
- `/auth/refresh` — `10/minute` per IP
- `/auth/logout` — `10/minute` per IP

---

## 7. Registration in App Factory

In `src/api/main.py`:

- Import and register `auth_router` with prefix `settings.api_v1_prefix` and tag `["auth"]`
- Wire `InMemoryRefreshTokenRepository` and `InMemoryUserRepository` into `app.state` for dependency access
- No new middleware — auth is per-route via `Depends()`

---

## 8. Testing Strategy

### Test fixtures (in `tests/conftest.py` or test-local conftest)

- RSA key pair generated once per test session
- `InMemoryRefreshTokenRepository` and `InMemoryUserRepository` pre-loaded with test user
- Settings override with test keys and short expiry for fast tests

### Unit tests (`tests/unit/api/test_auth.py`)

- **Password:** hash + verify roundtrip, wrong password rejects
- **Token creation:** valid JWT produced, correct claims, RS256 signature
- **Token decoding:** valid token decodes, expired rejects (use freezegun for exact-second boundary), tampered rejects, wrong algorithm rejects (verify `algorithms=["RS256"]` prevents HS256 confusion attack)
- **Auth service:** login success/failure, refresh success/expired/reused token, logout revokes
- **Replay detection:** refresh with already-revoked token triggers `revoke_all_for_user`
- **Concurrent refresh:** two refreshes with same token — first succeeds, second gets 401 (old token already revoked)

### Endpoint tests (`tests/unit/api/test_auth_endpoints.py`)

- **Login:** 200 valid creds, 401 wrong password, 401 unknown email, 422 invalid body
- **Refresh:** 200 valid token, 401 revoked token, 401 expired token
- **Logout:** 204 success, 204 with unknown token (idempotent)
- **get_current_user:** extracts valid token, rejects expired, rejects missing header

---

## 9. File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | Add PyJWT[crypto], bcrypt, email-validator |
| `src/config/settings.py` | Modify | Add JWT settings fields |
| `src/api/errors.py` | Modify | Add AuthenticationError, AuthorizationError |
| `src/api/dependencies.py` | Modify | Replace get_current_user stub with JWT validation |
| `src/api/main.py` | Modify | Register auth router, wire repositories to app.state |
| `src/api/auth/__init__.py` | Create | Package marker |
| `src/api/auth/schemas.py` | Create | Request/response Pydantic models |
| `src/api/auth/password.py` | Create | bcrypt hash/verify functions |
| `src/api/auth/tokens.py` | Create | JWT create/decode functions |
| `src/api/auth/repository.py` | Create | Repository protocols + in-memory implementations |
| `src/api/auth/service.py` | Create | AuthService orchestrator |
| `src/api/routers/auth.py` | Create | Login/refresh/logout endpoints |
| `tests/unit/api/test_auth.py` | Create | Service-level auth tests |
| `tests/unit/api/test_auth_endpoints.py` | Create | Endpoint-level auth tests |

---

## 10. Out of Scope

- User registration endpoint (comes with database layer)
- RBAC middleware / role checking (API-003)
- Real database persistence (future ticket)
- Redis-backed token blacklist (future optimization)
- Per-account lockout after 5 failed login attempts (security checklist requires "5 attempts → 30-min lockout"). The per-IP rate limiting in this ticket provides partial coverage but does not protect against distributed credential stuffing. Per-account lockout requires a failed-attempt counter in the user store, which should be added when the database layer is wired up. Track as a follow-up hardening item.
