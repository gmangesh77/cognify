import fastapi
import httpx
from fastapi import FastAPI

from src.api.auth.tokens import create_access_token
from src.config.settings import Settings

from .conftest import TEST_PASSWORD


class TestLoginEndpoint:
    async def test_login_success(self, auth_client: httpx.AsyncClient) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": TEST_PASSWORD,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900

    async def test_login_wrong_password(self, auth_client: httpx.AsyncClient) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrong-password",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"

    async def test_login_unknown_email(self, auth_client: httpx.AsyncClient) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "any-password-1",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"

    async def test_login_invalid_body(self, auth_client: httpx.AsyncClient) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "not-email", "password": "short"},
        )
        assert response.status_code == 422


class TestRefreshEndpoint:
    async def _login(self, client: httpx.AsyncClient) -> dict[str, object]:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": TEST_PASSWORD,
            },
        )
        return response.json()

    async def test_refresh_success(self, auth_client: httpx.AsyncClient) -> None:
        login_data = await self._login(auth_client)
        response = await auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] != login_data["access_token"]
        assert data["refresh_token"] != login_data["refresh_token"]

    async def test_refresh_revoked_token(self, auth_client: httpx.AsyncClient) -> None:
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

    async def test_refresh_unknown_token(self, auth_client: httpx.AsyncClient) -> None:
        response = await auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "no-such-token"},
        )
        assert response.status_code == 401


class TestLogoutEndpoint:
    async def test_logout_success(self, auth_client: httpx.AsyncClient) -> None:
        login_response = await auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": TEST_PASSWORD,
            },
        )
        login_data = login_response.json()
        response = await auth_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert response.status_code == 204

    async def test_logout_unknown_token(self, auth_client: httpx.AsyncClient) -> None:
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

    async def test_malformed_bearer_scheme(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
    ) -> None:
        from src.api.dependencies import get_current_user

        @auth_app.get("/api/v1/protected4")
        async def protected4(
            current_user: object = fastapi.Depends(get_current_user),
        ) -> dict[str, str]:
            return {"ok": "yes"}

        response = await auth_client.get(
            "/api/v1/protected4",
            headers={"Authorization": "Basic some-token"},
        )
        assert response.status_code == 401
