"""Endpoint tests for admin routes (RBAC enforcement)."""

import httpx
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
        response = await auth_client.get("/api/v1/admin/check", headers=headers)
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
        response = await auth_client.get("/api/v1/admin/check", headers=headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "insufficient_permissions"

    async def test_viewer_denied(
        self,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        response = await auth_client.get("/api/v1/admin/check", headers=headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "insufficient_permissions"

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
            response = await auth_client.get("/api/v1/admin/check", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_token"
