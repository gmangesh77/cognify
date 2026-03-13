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
