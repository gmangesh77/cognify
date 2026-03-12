# API-002: JWT Authentication — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JWT authentication with RS256 signing, refresh token rotation, and logout to the Cognify API.

**Architecture:** Auth logic lives in `src/api/auth/` with separate modules for password hashing, JWT tokens, repository interfaces, and an orchestrating service. Endpoints in `src/api/routers/auth.py`. Repository interfaces use `Protocol` with in-memory stubs for dev/testing — swapped for real persistence later.

**Tech Stack:** Python 3.12+, FastAPI, PyJWT[crypto], bcrypt, email-validator, pydantic, pytest, freezegun

**Spec:** `docs/superpowers/specs/2026-03-12-api-002-jwt-authentication-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | Add PyJWT[crypto], bcrypt, email-validator, freezegun |
| `src/config/settings.py` | Modify | Add JWT settings (keys, algorithm, expiry) |
| `src/api/errors.py` | Modify | Add AuthenticationError, AuthorizationError |
| `src/api/auth/__init__.py` | Create | Package marker (empty) |
| `src/api/auth/schemas.py` | Create | Role type, request/response/internal Pydantic models |
| `src/api/auth/password.py` | Create | bcrypt hash/verify (pure functions) |
| `src/api/auth/tokens.py` | Create | JWT create/decode (stateless) |
| `src/api/auth/repository.py` | Create | Protocol interfaces + in-memory implementations |
| `src/api/auth/service.py` | Create | AuthService orchestrator (login/refresh/logout) |
| `src/api/routers/auth.py` | Create | Login/refresh/logout endpoints |
| `src/api/dependencies.py` | Modify | Replace get_current_user stub with JWT validation |
| `src/api/main.py` | Modify | Register auth router, wire repositories to app.state |
| `tests/unit/api/test_auth.py` | Create | Service-level auth tests |
| `tests/unit/api/test_auth_endpoints.py` | Create | Endpoint-level auth tests |

---

## Chunk 1: Dependencies, Settings, Errors, and Schemas

### Task 1: Add dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add new packages**

Add to `[project] dependencies`:
```toml
    "PyJWT[crypto]>=2.9.0",
    "bcrypt>=4.2.0",
    "email-validator>=2.2.0",
```

Add to `[project.optional-dependencies] dev`:
```toml
    "freezegun>=1.4.0",
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -e ".[dev]"`
Expected: All packages install successfully.

- [ ] **Step 3: Verify imports**

Run: `python -c "import jwt; import bcrypt; from email_validator import validate_email; from freezegun import freeze_time; print('OK')"`
Expected: Prints `OK`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add PyJWT, bcrypt, email-validator, freezegun dependencies"
```

---

### Task 2: Add JWT settings and auth error classes

**Files:**
- Modify: `src/config/settings.py`
- Modify: `src/api/errors.py`
- Create: `tests/unit/api/test_auth.py` (initial test file)

- [ ] **Step 1: Write failing tests for new settings and errors**

Create `tests/unit/api/test_auth.py`:

```python
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from src.api.errors import AuthenticationError, AuthorizationError
from src.config.settings import Settings


class TestJwtSettings:
    def test_default_jwt_settings(self) -> None:
        settings = Settings()
        assert settings.jwt_private_key == ""
        assert settings.jwt_public_key == ""
        assert settings.jwt_algorithm == "RS256"
        assert settings.jwt_access_token_expire_minutes == 15
        assert settings.jwt_refresh_token_expire_days == 7


class TestAuthErrors:
    def test_authentication_error(self) -> None:
        err = AuthenticationError(code="invalid_credentials")
        assert err.status_code == HTTP_401_UNAUTHORIZED
        assert err.code == "invalid_credentials"

    def test_authentication_error_default_message(self) -> None:
        err = AuthenticationError()
        assert err.message == "Authentication failed"

    def test_authentication_error_custom_message(self) -> None:
        err = AuthenticationError(message="Token expired")
        assert err.message == "Token expired"

    def test_authorization_error(self) -> None:
        err = AuthorizationError()
        assert err.status_code == HTTP_403_FORBIDDEN
        assert err.code == "insufficient_permissions"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/api/test_auth.py::TestJwtSettings -v && pytest tests/unit/api/test_auth.py::TestAuthErrors -v`
Expected: FAIL — `ImportError` for `AuthenticationError`.

- [ ] **Step 3: Add JWT settings**

Modify `src/config/settings.py` — add these fields to the `Settings` class:

```python
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
```

- [ ] **Step 4: Add auth error classes**

Modify `src/api/errors.py` — replace the existing `starlette.status` import with:

```python
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_429_TOO_MANY_REQUESTS,
)
```

Add these classes after `RateLimitError`:

```python
class AuthenticationError(CognifyError):
    def __init__(
        self,
        code: str = "authentication_failed",
        message: str = "Authentication failed",
    ) -> None:
        super().__init__(
            status_code=HTTP_401_UNAUTHORIZED,
            code=code,
            message=message,
        )


class AuthorizationError(CognifyError):
    def __init__(
        self,
        message: str = "Insufficient permissions",
    ) -> None:
        super().__init__(
            status_code=HTTP_403_FORBIDDEN,
            code="insufficient_permissions",
            message=message,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/api/test_auth.py -v`
Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/config/settings.py src/api/errors.py tests/unit/api/test_auth.py
git commit -m "feat: add JWT settings and auth error classes"
```

---

### Task 3: Create schemas

**Files:**
- Create: `src/api/auth/__init__.py`
- Create: `src/api/auth/schemas.py`
- Modify: `tests/unit/api/test_auth.py` (append schema tests)

- [ ] **Step 1: Write failing tests for schemas**

Append to `tests/unit/api/test_auth.py`:

```python
import pytest
from pydantic import ValidationError

from src.api.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RefreshTokenData,
    Role,
    TokenPayload,
    TokenResponse,
    UserData,
)


class TestSchemas:
    def test_login_request_valid(self) -> None:
        req = LoginRequest(email="test@example.com", password="password123")
        assert req.email == "test@example.com"

    def test_login_request_invalid_email(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest(email="not-an-email", password="password123")

    def test_login_request_short_password(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest(email="test@example.com", password="short")

    def test_refresh_request(self) -> None:
        req = RefreshRequest(refresh_token="some-token")
        assert req.refresh_token == "some-token"

    def test_token_response(self) -> None:
        resp = TokenResponse(
            access_token="acc",
            refresh_token="ref",
            expires_in=900,
        )
        assert resp.token_type == "bearer"

    def test_token_payload_role_validation(self) -> None:
        payload = TokenPayload(
            sub="user-1", role="admin", exp=999, iat=0, jti="j1"
        )
        assert payload.role == "admin"

    def test_token_payload_invalid_role(self) -> None:
        with pytest.raises(ValidationError):
            TokenPayload(
                sub="user-1", role="superadmin", exp=999, iat=0, jti="j1"
            )

    def test_refresh_token_data_defaults(self) -> None:
        from datetime import UTC, datetime

        data = RefreshTokenData(
            user_id="u1",
            token="t1",
            expires_at=datetime.now(UTC),
        )
        assert data.revoked is False

    def test_user_data_role_type(self) -> None:
        user = UserData(
            id="u1",
            email="test@example.com",
            password_hash="hash",
            role="editor",
        )
        assert user.role == "editor"

    def test_role_literal_values(self) -> None:
        valid_roles: list[Role] = ["admin", "editor", "viewer"]
        assert len(valid_roles) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/api/test_auth.py::TestSchemas -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.auth'`

- [ ] **Step 3: Create auth package and schemas**

Create `src/api/auth/__init__.py` (empty).

Create `src/api/auth/schemas.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["admin", "editor", "viewer"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    role: Role
    exp: int
    iat: int
    jti: str


class RefreshTokenData(BaseModel):
    user_id: str
    token: str
    expires_at: datetime
    revoked: bool = False


class UserData(BaseModel):
    id: str
    email: str
    password_hash: str
    role: Role
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/api/test_auth.py -v`
Expected: 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/auth/ tests/unit/api/test_auth.py
git commit -m "feat: add auth schemas with Role type and Pydantic models"
```

---

## Chunk 2: Password, Token, and Repository Services

### Task 4: Password service

**Files:**
- Create: `src/api/auth/password.py`
- Modify: `tests/unit/api/test_auth.py` (append tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/api/test_auth.py`:

```python
from src.api.auth.password import hash_password, verify_password


class TestPasswordService:
    def test_hash_and_verify(self) -> None:
        hashed = hash_password("my-secret-password")
        assert verify_password("my-secret-password", hashed)

    def test_wrong_password_rejects(self) -> None:
        hashed = hash_password("my-secret-password")
        assert not verify_password("wrong-password", hashed)

    def test_hash_uses_cost_factor_12(self) -> None:
        hashed = hash_password("test")
        assert hashed.startswith("$2b$12$")

    def test_different_hashes_for_same_input(self) -> None:
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/api/test_auth.py::TestPasswordService -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement password service**

Create `src/api/auth/password.py`:

```python
import bcrypt

_COST_FACTOR = 12


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=_COST_FACTOR)
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/api/test_auth.py::TestPasswordService -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/auth/password.py tests/unit/api/test_auth.py
git commit -m "feat: add bcrypt password hashing service"
```

---

### Task 5: Token service

**Files:**
- Create: `src/api/auth/tokens.py`
- Modify: `tests/unit/api/test_auth.py` (append tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/api/test_auth.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

from freezegun import freeze_time

from src.api.auth.tokens import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
)


def _make_test_settings(
    private_key: str, public_key: str
) -> Settings:
    return Settings(
        jwt_private_key=private_key,
        jwt_public_key=public_key,
    )


def _generate_rsa_keys() -> tuple[str, str]:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


class TestTokenService:
    def setup_method(self) -> None:
        private_pem, public_pem = _generate_rsa_keys()
        self.settings = _make_test_settings(private_pem, public_pem)

    def test_create_access_token_returns_string(self) -> None:
        token = create_access_token("user-1", "admin", self.settings)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_and_decode_roundtrip(self) -> None:
        token = create_access_token("user-1", "editor", self.settings)
        payload = decode_access_token(token, self.settings)
        assert payload.sub == "user-1"
        assert payload.role == "editor"

    def test_access_token_has_jti(self) -> None:
        token = create_access_token("user-1", "admin", self.settings)
        payload = decode_access_token(token, self.settings)
        uuid.UUID(payload.jti)  # validates it's a valid UUID

    def test_access_token_has_timestamps(self) -> None:
        token = create_access_token("user-1", "admin", self.settings)
        payload = decode_access_token(token, self.settings)
        now = int(datetime.now(UTC).timestamp())
        assert payload.iat <= now
        assert payload.exp > now

    def test_expired_token_rejected(self) -> None:
        with freeze_time("2026-01-01 00:00:00"):
            token = create_access_token("user-1", "admin", self.settings)
        with freeze_time("2026-01-01 00:16:00"):
            with pytest.raises(AuthenticationError) as exc_info:
                decode_access_token(token, self.settings)
            assert exc_info.value.code == "invalid_token"

    def test_tampered_token_rejected(self) -> None:
        token = create_access_token("user-1", "admin", self.settings)
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(AuthenticationError):
            decode_access_token(tampered, self.settings)

    def test_wrong_key_rejected(self) -> None:
        token = create_access_token("user-1", "admin", self.settings)
        _, other_public = _generate_rsa_keys()
        other_settings = _make_test_settings(
            self.settings.jwt_private_key, other_public
        )
        with pytest.raises(AuthenticationError):
            decode_access_token(token, other_settings)

    def test_create_refresh_token_is_uuid(self) -> None:
        token = create_refresh_token()
        uuid.UUID(token)  # validates format

    def test_refresh_tokens_are_unique(self) -> None:
        t1 = create_refresh_token()
        t2 = create_refresh_token()
        assert t1 != t2

    def test_hs256_confusion_attack_rejected(self) -> None:
        """Verify algorithms=['RS256'] prevents HS256 confusion attack."""
        import jwt as pyjwt

        payload = {
            "sub": "user-1",
            "role": "admin",
            "iat": 0,
            "exp": 9999999999,
            "jti": "j1",
        }
        # Sign with HS256 using public key as HMAC secret
        forged = pyjwt.encode(
            payload,
            self.settings.jwt_public_key,
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError):
            decode_access_token(forged, self.settings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/api/test_auth.py::TestTokenService -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement token service**

Create `src/api/auth/tokens.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from src.api.auth.schemas import TokenPayload
from src.api.errors import AuthenticationError
from src.config.settings import Settings


def create_access_token(
    user_id: str, role: str, settings: Settings
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(
            (
                now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
            ).timestamp()
        ),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload,
        settings.jwt_private_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token() -> str:
    return str(uuid.uuid4())


def decode_access_token(
    token: str, settings: Settings
) -> TokenPayload:
    try:
        # Hardcode RS256 to prevent algorithm confusion attacks (RFC 8725)
        payload = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=["RS256"],
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(
            code="invalid_token",
            message="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise AuthenticationError(
            code="invalid_token",
            message="Invalid or expired token",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/api/test_auth.py::TestTokenService -v`
Expected: 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/auth/tokens.py tests/unit/api/test_auth.py
git commit -m "feat: add JWT token service with RS256 create/decode"
```

---

### Task 6: Repository interfaces and in-memory implementations

**Files:**
- Create: `src/api/auth/repository.py`
- Modify: `tests/unit/api/test_auth.py` (append tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/api/test_auth.py`:

```python
from src.api.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
from src.api.auth.schemas import RefreshTokenData, UserData


class TestInMemoryRefreshTokenRepository:
    def setup_method(self) -> None:
        self.repo = InMemoryRefreshTokenRepository()
        self.expires = datetime.now(UTC) + timedelta(days=7)

    def test_save_and_get(self) -> None:
        self.repo.save("user-1", "token-abc", self.expires)
        data = self.repo.get("token-abc")
        assert data is not None
        assert data.user_id == "user-1"
        assert data.token == "token-abc"
        assert data.revoked is False

    def test_get_nonexistent_returns_none(self) -> None:
        assert self.repo.get("no-such-token") is None

    def test_revoke_marks_as_revoked(self) -> None:
        self.repo.save("user-1", "token-abc", self.expires)
        self.repo.revoke("token-abc")
        data = self.repo.get("token-abc")
        assert data is not None
        assert data.revoked is True

    def test_revoke_all_for_user(self) -> None:
        self.repo.save("user-1", "tok-1", self.expires)
        self.repo.save("user-1", "tok-2", self.expires)
        self.repo.save("user-2", "tok-3", self.expires)
        self.repo.revoke_all_for_user("user-1")
        assert self.repo.get("tok-1") is not None
        assert self.repo.get("tok-1").revoked is True
        assert self.repo.get("tok-2") is not None
        assert self.repo.get("tok-2").revoked is True
        assert self.repo.get("tok-3") is not None
        assert self.repo.get("tok-3").revoked is False


class TestInMemoryUserRepository:
    def test_get_by_email_found(self) -> None:
        user = UserData(
            id="u1", email="a@b.com", password_hash="h", role="admin"
        )
        repo = InMemoryUserRepository([user])
        assert repo.get_by_email("a@b.com") == user

    def test_get_by_email_not_found(self) -> None:
        repo = InMemoryUserRepository([])
        assert repo.get_by_email("x@y.com") is None

    def test_get_by_id_found(self) -> None:
        user = UserData(
            id="u1", email="a@b.com", password_hash="h", role="admin"
        )
        repo = InMemoryUserRepository([user])
        assert repo.get_by_id("u1") == user

    def test_get_by_id_not_found(self) -> None:
        repo = InMemoryUserRepository([])
        assert repo.get_by_id("no-such-id") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/api/test_auth.py::TestInMemoryRefreshTokenRepository -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement repositories**

Create `src/api/auth/repository.py`:

```python
from datetime import datetime
from typing import Protocol

from src.api.auth.schemas import RefreshTokenData, UserData


class RefreshTokenRepository(Protocol):
    def save(
        self, user_id: str, token: str, expires_at: datetime
    ) -> None: ...

    def get(self, token: str) -> RefreshTokenData | None: ...

    def revoke(self, token: str) -> None: ...

    def revoke_all_for_user(self, user_id: str) -> None: ...


class UserRepository(Protocol):
    def get_by_email(self, email: str) -> UserData | None: ...

    def get_by_id(self, user_id: str) -> UserData | None: ...


class InMemoryRefreshTokenRepository:
    def __init__(self) -> None:
        self._tokens: dict[str, RefreshTokenData] = {}

    def save(
        self, user_id: str, token: str, expires_at: datetime
    ) -> None:
        self._tokens[token] = RefreshTokenData(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )

    def get(self, token: str) -> RefreshTokenData | None:
        return self._tokens.get(token)

    def revoke(self, token: str) -> None:
        if token in self._tokens:
            data = self._tokens[token]
            self._tokens[token] = data.model_copy(
                update={"revoked": True}
            )

    def revoke_all_for_user(self, user_id: str) -> None:
        for key, data in self._tokens.items():
            if data.user_id == user_id:
                self._tokens[key] = data.model_copy(
                    update={"revoked": True}
                )


class InMemoryUserRepository:
    def __init__(self, users: list[UserData]) -> None:
        self._users_by_email = {u.email: u for u in users}
        self._users_by_id = {u.id: u for u in users}

    def get_by_email(self, email: str) -> UserData | None:
        return self._users_by_email.get(email)

    def get_by_id(self, user_id: str) -> UserData | None:
        return self._users_by_id.get(user_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/api/test_auth.py -v`
Expected: All tests PASS (37 tests).

- [ ] **Step 5: Commit**

```bash
git add src/api/auth/repository.py tests/unit/api/test_auth.py
git commit -m "feat: add repository protocols with in-memory implementations"
```

---

## Chunk 3: Auth Service

### Task 7: Auth service (login, refresh, logout)

**Files:**
- Create: `src/api/auth/service.py`
- Modify: `tests/unit/api/test_auth.py` (append tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/api/test_auth.py`:

```python
from src.api.auth.password import hash_password
from src.api.auth.service import AuthService


class TestAuthService:
    def setup_method(self) -> None:
        private_pem, public_pem = _generate_rsa_keys()
        self.settings = _make_test_settings(private_pem, public_pem)
        self.refresh_repo = InMemoryRefreshTokenRepository()
        test_user = UserData(
            id="user-1",
            email="test@example.com",
            password_hash=hash_password("correct-password"),
            role="editor",
        )
        self.user_repo = InMemoryUserRepository([test_user])
        self.service = AuthService(
            settings=self.settings,
            refresh_repo=self.refresh_repo,
            user_repo=self.user_repo,
        )

    def test_login_success(self) -> None:
        result = self.service.login("test@example.com", "correct-password")
        assert result.access_token
        assert result.refresh_token
        assert result.token_type == "bearer"
        assert result.expires_in == 15 * 60

    def test_login_wrong_password(self) -> None:
        with pytest.raises(AuthenticationError) as exc_info:
            self.service.login("test@example.com", "wrong-password")
        assert exc_info.value.code == "invalid_credentials"

    def test_login_unknown_email(self) -> None:
        with pytest.raises(AuthenticationError) as exc_info:
            self.service.login("nobody@example.com", "any-password")
        assert exc_info.value.code == "invalid_credentials"

    def test_refresh_success(self) -> None:
        login_result = self.service.login(
            "test@example.com", "correct-password"
        )
        new_result = self.service.refresh(login_result.refresh_token)
        assert new_result.access_token != login_result.access_token
        assert new_result.refresh_token != login_result.refresh_token

    def test_refresh_revokes_old_token(self) -> None:
        login_result = self.service.login(
            "test@example.com", "correct-password"
        )
        old_token = login_result.refresh_token
        self.service.refresh(old_token)
        data = self.refresh_repo.get(old_token)
        assert data is not None
        assert data.revoked is True

    def test_refresh_with_revoked_token_triggers_revoke_all(self) -> None:
        login_result = self.service.login(
            "test@example.com", "correct-password"
        )
        old_token = login_result.refresh_token
        # First refresh — revokes old token
        new_result = self.service.refresh(old_token)
        # Replay attack — use the already-revoked token again
        with pytest.raises(AuthenticationError):
            self.service.refresh(old_token)
        # New token should also be revoked (revoke_all_for_user triggered)
        new_data = self.refresh_repo.get(new_result.refresh_token)
        assert new_data is not None
        assert new_data.revoked is True

    def test_refresh_unknown_token(self) -> None:
        with pytest.raises(AuthenticationError) as exc_info:
            self.service.refresh("nonexistent-token")
        assert exc_info.value.code == "invalid_refresh_token"

    def test_refresh_expired_token(self) -> None:
        login_result = self.service.login(
            "test@example.com", "correct-password"
        )
        # Manually expire the token
        data = self.refresh_repo.get(login_result.refresh_token)
        assert data is not None
        expired_data = data.model_copy(
            update={"expires_at": datetime.now(UTC) - timedelta(hours=1)}
        )
        self.refresh_repo._tokens[login_result.refresh_token] = expired_data  # noqa: SLF001
        with pytest.raises(AuthenticationError) as exc_info:
            self.service.refresh(login_result.refresh_token)
        assert exc_info.value.code == "invalid_refresh_token"

    def test_logout_revokes_token(self) -> None:
        login_result = self.service.login(
            "test@example.com", "correct-password"
        )
        self.service.logout(login_result.refresh_token)
        data = self.refresh_repo.get(login_result.refresh_token)
        assert data is not None
        assert data.revoked is True

    def test_logout_unknown_token_no_error(self) -> None:
        self.service.logout("nonexistent-token")  # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/api/test_auth.py::TestAuthService -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement auth service**

Create `src/api/auth/service.py`:

```python
from datetime import UTC, datetime, timedelta

from src.api.auth.password import verify_password
from src.api.auth.repository import RefreshTokenRepository, UserRepository
from src.api.auth.schemas import TokenResponse
from src.api.auth.tokens import create_access_token, create_refresh_token
from src.api.errors import AuthenticationError
from src.config.settings import Settings


class AuthService:
    def __init__(
        self,
        settings: Settings,
        refresh_repo: RefreshTokenRepository,
        user_repo: UserRepository,
    ) -> None:
        self._settings = settings
        self._refresh_repo = refresh_repo
        self._user_repo = user_repo

    def login(self, email: str, password: str) -> TokenResponse:
        user = self._user_repo.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError(
                code="invalid_credentials",
                message="Invalid email or password",
            )

        access_token = create_access_token(
            user.id, user.role, self._settings
        )
        refresh_token = create_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(
            days=self._settings.jwt_refresh_token_expire_days
        )
        self._refresh_repo.save(user.id, refresh_token, expires_at)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._settings.jwt_access_token_expire_minutes * 60,
        )

    def refresh(self, refresh_token: str) -> TokenResponse:
        data = self._refresh_repo.get(refresh_token)
        if data is None:
            raise AuthenticationError(
                code="invalid_refresh_token",
                message="Invalid refresh token",
            )

        if data.revoked:
            self._refresh_repo.revoke_all_for_user(data.user_id)
            raise AuthenticationError(
                code="invalid_refresh_token",
                message="Invalid refresh token",
            )

        if data.expires_at < datetime.now(UTC):
            raise AuthenticationError(
                code="invalid_refresh_token",
                message="Refresh token has expired",
            )

        self._refresh_repo.revoke(refresh_token)

        user = self._user_repo.get_by_id(data.user_id)
        if user is None:
            raise AuthenticationError(
                code="invalid_refresh_token",
                message="User not found",
            )
        access_token = create_access_token(
            data.user_id, user.role, self._settings
        )
        new_refresh_token = create_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(
            days=self._settings.jwt_refresh_token_expire_days
        )
        self._refresh_repo.save(
            data.user_id, new_refresh_token, expires_at
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=self._settings.jwt_access_token_expire_minutes * 60,
        )

    def logout(self, refresh_token: str) -> None:
        data = self._refresh_repo.get(refresh_token)
        if data is not None and not data.revoked:
            self._refresh_repo.revoke(refresh_token)

```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/api/test_auth.py::TestAuthService -v`
Expected: 10 tests PASS.

- [ ] **Step 5: Run full test file**

Run: `pytest tests/unit/api/test_auth.py -v`
Expected: All tests PASS (47 tests).

- [ ] **Step 6: Commit**

```bash
git add src/api/auth/service.py tests/unit/api/test_auth.py
git commit -m "feat: add AuthService with login, refresh, and logout"
```

---

## Chunk 4: Endpoints, Dependency, and App Integration

### Task 8: Auth router and get_current_user dependency

**Files:**
- Create: `src/api/routers/auth.py`
- Modify: `src/api/dependencies.py`
- Create: `tests/unit/api/test_auth_endpoints.py`

- [ ] **Step 1: Write failing endpoint tests**

Create `tests/unit/api/test_auth_endpoints.py`:

```python
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import fastapi
import httpx
import pytest
from fastapi import FastAPI

from src.api.auth.password import hash_password
from src.api.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
from src.api.auth.schemas import UserData
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
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


_PRIVATE_KEY, _PUBLIC_KEY = _generate_rsa_keys()
_TEST_PASSWORD = "test-password-123"
_TEST_USER = UserData(
    id="user-1",
    email="test@example.com",
    password_hash=hash_password(_TEST_PASSWORD),
    role="editor",
)


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
    # Override repositories created by create_app with test-specific ones
    app.state.user_repo = InMemoryUserRepository([_TEST_USER])
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


class TestLoginEndpoint:
    async def test_login_success(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": _TEST_PASSWORD,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900

    async def test_login_wrong_password(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrong-password",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"

    async def test_login_unknown_email(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "any-password-1",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"

    async def test_login_invalid_body(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "not-email", "password": "short"},
        )
        assert response.status_code == 422


class TestRefreshEndpoint:
    async def _login(
        self, client: httpx.AsyncClient
    ) -> dict[str, object]:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": _TEST_PASSWORD,
            },
        )
        return response.json()

    async def test_refresh_success(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        login_data = await self._login(auth_client)
        response = await auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] != login_data["access_token"]
        assert data["refresh_token"] != login_data["refresh_token"]

    async def test_refresh_revoked_token(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        login_data = await self._login(auth_client)
        # First refresh succeeds
        await auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_data["refresh_token"]},
        )
        # Second refresh with same (now revoked) token fails
        response = await auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert response.status_code == 401

    async def test_refresh_unknown_token(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        response = await auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "no-such-token"},
        )
        assert response.status_code == 401


class TestLogoutEndpoint:
    async def test_logout_success(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        login_response = await auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": _TEST_PASSWORD,
            },
        )
        login_data = login_response.json()
        response = await auth_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert response.status_code == 204

    async def test_logout_unknown_token(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        response = await auth_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "unknown-token"},
        )
        assert response.status_code == 204  # Idempotent


class TestGetCurrentUser:
    async def test_valid_bearer_token(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        from src.api.dependencies import get_current_user

        # Add a protected test route
        @auth_app.get("/api/v1/protected")
        async def protected(
            current_user: object = fastapi.Depends(get_current_user),
        ) -> dict[str, str]:
            return {"user_id": current_user.sub}  # type: ignore[union-attr]

        token = create_access_token("user-1", "admin", auth_settings)
        response = await auth_client.get(
            "/api/v1/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == "user-1"

    async def test_missing_authorization_header(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
    ) -> None:
        from src.api.dependencies import get_current_user

        @auth_app.get("/api/v1/protected2")
        async def protected2(
            current_user: object = fastapi.Depends(get_current_user),
        ) -> dict[str, str]:
            return {"ok": "yes"}

        response = await auth_client.get("/api/v1/protected2")
        assert response.status_code == 401

    async def test_invalid_token(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
    ) -> None:
        from src.api.dependencies import get_current_user

        @auth_app.get("/api/v1/protected3")
        async def protected3(
            current_user: object = fastapi.Depends(get_current_user),
        ) -> dict[str, str]:
            return {"ok": "yes"}

        response = await auth_client.get(
            "/api/v1/protected3",
            headers={"Authorization": "Bearer invalid-jwt-token"},
        )
        assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/api/test_auth_endpoints.py -v`
Expected: FAIL — `ImportError` for auth router or missing routes.

- [ ] **Step 3: Create auth router**

Create `src/api/routers/auth.py`:

```python
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, Response

from src.api.auth.schemas import LoginRequest, RefreshRequest, TokenResponse
from src.api.auth.service import AuthService
from src.api.rate_limiter import limiter

auth_router = APIRouter()


def _get_auth_service(request: Request) -> AuthService:
    return AuthService(
        settings=request.app.state.settings,
        refresh_repo=request.app.state.refresh_repo,
        user_repo=request.app.state.user_repo,
    )


@auth_router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
@limiter.limit("5/minute")
async def login(
    request: Request, body: LoginRequest
) -> TokenResponse:
    service = _get_auth_service(request)
    return service.login(body.email, body.password)


@auth_router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
@limiter.limit("10/minute")
async def refresh(
    request: Request, body: RefreshRequest
) -> TokenResponse:
    service = _get_auth_service(request)
    return service.refresh(body.refresh_token)


@auth_router.post(
    "/auth/logout",
    status_code=204,
    summary="Logout and revoke refresh token",
)
@limiter.limit("10/minute")
async def logout(
    request: Request, body: RefreshRequest
) -> Response:
    service = _get_auth_service(request)
    service.logout(body.refresh_token)
    return Response(status_code=204)
```

- [ ] **Step 4: Replace get_current_user dependency**

Modify `src/api/dependencies.py`:

```python
from fastapi import Header, Request

from src.api.auth.schemas import TokenPayload
from src.api.auth.tokens import decode_access_token
from src.api.errors import AuthenticationError


async def get_current_user(
    request: Request,
    # default="" so FastAPI returns our 401, not its own 422 for missing header
    authorization: str = Header(alias="Authorization", default=""),
) -> TokenPayload:
    if not authorization:
        raise AuthenticationError(
            code="invalid_token",
            message="Missing authorization header",
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0] != "Bearer":
        raise AuthenticationError(
            code="invalid_token",
            message="Invalid authorization header format",
        )

    settings = request.app.state.settings
    return decode_access_token(parts[1], settings)


async def get_db_session() -> None:
    """Placeholder — replaced when database layer is added."""
```

- [ ] **Step 5: Register auth router in app factory**

Modify `src/api/main.py` — add imports at top:

```python
from src.api.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
from src.api.routers.auth import auth_router
```

In `_register_routers`, add after the health router:

```python
    app.include_router(
        auth_router,
        prefix=settings.api_v1_prefix,
        tags=["auth"],
    )
```

In `create_app`, after `app.state.limiter = limiter`, add:

```python
    app.state.refresh_repo = InMemoryRefreshTokenRepository()
    app.state.user_repo = InMemoryUserRepository([])
```

- [ ] **Step 6: Run endpoint tests**

Run: `pytest tests/unit/api/test_auth_endpoints.py -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/api/routers/auth.py src/api/dependencies.py src/api/main.py tests/unit/api/test_auth_endpoints.py
git commit -m "feat: add auth endpoints, get_current_user dependency, and app integration"
```

---

## Chunk 5: Full Validation and Cleanup

### Task 9: Full suite validation, lint, type check

**Files:**
- Modify: any files with lint/type issues

- [ ] **Step 1: Run full test suite with coverage**

Run: `pytest tests/ -v --cov=src --cov-report=term-missing`
Expected: All tests PASS, coverage >= 80%.

- [ ] **Step 2: Run linting**

Run: `ruff check src/ tests/ && ruff format --check src/ tests/`
Expected: No lint errors. If there are errors, fix them.

- [ ] **Step 3: Run type checking**

Run: `mypy src/`
Expected: No type errors. If there are errors, fix them. Common fixes:
- Add `# type: ignore[untyped-decorator]` on `@limiter.limit()` decorators
- Fix return type annotations

- [ ] **Step 4: Fix any issues found**

Iterate on lint, format, and type errors until all clean.

- [ ] **Step 5: Run full validation again**

Run: `pytest tests/ -v --cov=src --cov-report=term-missing && ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/`
Expected: All green.

- [ ] **Step 6: Verify existing tests still pass**

Run: `pytest tests/unit/api/test_health.py tests/unit/api/test_middleware.py tests/unit/api/test_app.py tests/unit/api/test_errors.py -v`
Expected: All existing tests still PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add src/ tests/
git commit -m "chore: fix lint/type issues for auth module"
```

---

### Task 10: Update documentation and progress tracking

**Files:**
- Modify: `project-management/PROGRESS.md`
- Modify: `CLAUDE.md`
- Modify: `.env.example`

- [ ] **Step 1: Update .env.example with JWT settings**

Add to `.env.example`:

```env
COGNIFY_JWT_PRIVATE_KEY=  # RSA private key PEM (generate with: openssl genrsa 2048)
COGNIFY_JWT_PUBLIC_KEY=   # RSA public key PEM (generate with: openssl rsa -pubout)
COGNIFY_JWT_ALGORITHM=RS256
COGNIFY_JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
COGNIFY_JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

- [ ] **Step 2: Update PROGRESS.md**

Change API-002 row:
- Status: `Done`
- Branch: `feature/API-002-jwt-authentication`
- Plan: link to this plan file
- Spec: link to the spec file

- [ ] **Step 3: Update CLAUDE.md session state**

Update the "Current Status" section:
- Last completed: API-002
- Next up: API-003 (RBAC Authorization)

- [ ] **Step 4: Commit**

```bash
git add .env.example project-management/PROGRESS.md CLAUDE.md
git commit -m "docs: update progress tracking and env example for API-002"
```
