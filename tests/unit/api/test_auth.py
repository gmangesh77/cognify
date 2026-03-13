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
