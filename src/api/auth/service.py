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

        access_token = create_access_token(user.id, user.role, self._settings)
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
        access_token = create_access_token(data.user_id, user.role, self._settings)
        new_refresh_token = create_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(
            days=self._settings.jwt_refresh_token_expire_days
        )
        self._refresh_repo.save(data.user_id, new_refresh_token, expires_at)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=self._settings.jwt_access_token_expire_minutes * 60,
        )

    def logout(self, refresh_token: str) -> None:
        data = self._refresh_repo.get(refresh_token)
        if data is not None and not data.revoked:
            self._refresh_repo.revoke(refresh_token)
