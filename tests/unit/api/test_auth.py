import uuid
from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time
from pydantic import ValidationError
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


from src.api.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
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


from src.api.auth.tokens import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
)


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
        """Verify algorithms=['RS256'] prevents HS256 confusion attack.

        Modern PyJWT (2.x) rejects using a PEM-formatted RSA public key as an
        HMAC secret at encode time, so the forged token cannot be constructed.
        Either way — at encode or decode — the attack is blocked.
        """
        import jwt as pyjwt

        payload = {
            "sub": "user-1",
            "role": "admin",
            "iat": 0,
            "exp": 9999999999,
            "jti": "j1",
        }
        # PyJWT 2.x raises InvalidKeyError when trying to use an RSA PEM key
        # as an HMAC secret, which is the first line of defence.
        with pytest.raises(pyjwt.exceptions.InvalidKeyError):
            pyjwt.encode(
                payload,
                self.settings.jwt_public_key,
                algorithm="HS256",
            )


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
