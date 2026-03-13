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
