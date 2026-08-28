"""INFRA-008 — admin toggles a user's active flag; access changes immediately."""

from datetime import UTC, datetime, timedelta

import fastapi
import httpx
from fastapi import FastAPI

from src.api.auth.repository import InMemoryUserRepository
from src.api.auth.schemas import UserData
from src.api.auth.tokens import create_access_token
from src.config.settings import Settings

from .conftest import TEST_USER, make_auth_header

OTHER = UserData(
    id="user-2", email="other@example.com", password_hash="x", role="viewer"
)


def _seed(auth_app: FastAPI) -> None:
    auth_app.state.user_repo = InMemoryUserRepository([TEST_USER, OTHER])

    from src.api.dependencies import get_current_user

    @auth_app.get("/api/v1/whoami")
    async def whoami(
        current_user: object = fastapi.Depends(get_current_user),
    ) -> dict[str, str]:
        return {"user_id": current_user.sub}  # type: ignore[union-attr]


def _bearer(user_id: str, role: str, settings: Settings) -> dict[str, str]:
    token = create_access_token(user_id, role, settings)
    return {"Authorization": f"Bearer {token}"}


class TestSetUserActive:
    async def test_admin_deactivates_and_reactivates(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        _seed(auth_app)
        admin = make_auth_header("admin", auth_settings)
        other = _bearer("user-2", "viewer", auth_settings)
        ok = await auth_client.get("/api/v1/whoami", headers=other)
        assert ok.status_code == 200

        response = await auth_client.patch(
            "/api/v1/auth/users/user-2/active",
            json={"is_active": False},
            headers=admin,
        )
        assert response.status_code == 200
        assert response.json() == {"user_id": "user-2", "is_active": False}
        # Cache invalidated → the very next request is rejected.
        denied = await auth_client.get("/api/v1/whoami", headers=other)
        assert denied.status_code == 401

        response = await auth_client.patch(
            "/api/v1/auth/users/user-2/active",
            json={"is_active": True},
            headers=admin,
        )
        assert response.status_code == 200
        restored = await auth_client.get("/api/v1/whoami", headers=other)
        assert restored.status_code == 200

    async def test_deactivation_revokes_refresh_tokens(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        _seed(auth_app)
        auth_app.state.refresh_repo.save(
            "user-2", "refresh-2", datetime.now(UTC) + timedelta(days=1)
        )
        admin = make_auth_header("admin", auth_settings)
        await auth_client.patch(
            "/api/v1/auth/users/user-2/active",
            json={"is_active": False},
            headers=admin,
        )
        assert auth_app.state.refresh_repo.get("refresh-2").revoked is True

    async def test_editor_is_forbidden(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        _seed(auth_app)
        response = await auth_client.patch(
            "/api/v1/auth/users/user-2/active",
            json={"is_active": False},
            headers=make_auth_header("editor", auth_settings),
        )
        assert response.status_code == 403

    async def test_unknown_user_is_404(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        _seed(auth_app)
        response = await auth_client.patch(
            "/api/v1/auth/users/ghost/active",
            json={"is_active": False},
            headers=make_auth_header("admin", auth_settings),
        )
        assert response.status_code == 404
