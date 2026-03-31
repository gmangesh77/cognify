"""Endpoint tests for OAuth routes."""

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI

from src.config.settings import Settings

from .conftest import make_auth_header


@pytest.fixture
def oauth_app(auth_app: FastAPI, auth_settings: Settings) -> FastAPI:
    auth_app.state.settings = auth_settings
    auth_app.state.settings_repos = type("_Repos", (), {"api_keys": AsyncMock()})()
    return auth_app


@pytest.fixture
async def oauth_client(oauth_app: FastAPI) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=oauth_app),
        base_url="http://test",
    ) as ac:
        yield ac


def _parse_redirect(resp: httpx.Response) -> dict[str, str]:
    """Extract query params from a redirect Location header."""
    parsed = urlparse(resp.headers["location"])
    qs = parse_qs(parsed.query)
    return {k: v[0] for k, v in qs.items()}


class TestLinkedInAuthorize:
    async def test_returns_authorization_url(
        self,
        oauth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("admin", auth_settings)
        resp = await oauth_client.get(
            "/api/v1/oauth/linkedin/authorize",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_url" in data
        url = data["authorization_url"]
        assert "linkedin.com/oauth/v2/authorization" in url
        assert "response_type=code" in url

    async def test_requires_admin(
        self,
        oauth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await oauth_client.get(
            "/api/v1/oauth/linkedin/authorize",
            headers=headers,
        )
        assert resp.status_code == 403


class TestLinkedInCallback:
    async def test_invalid_state_redirects_with_error(
        self,
        oauth_client: httpx.AsyncClient,
    ) -> None:
        resp = await oauth_client.get(
            "/api/v1/oauth/linkedin/callback",
            params={"code": "abc", "state": "bad-state"},
        )
        assert resp.status_code == 307
        params = _parse_redirect(resp)
        assert params["oauth"] == "error"
        assert params["message"] == "expired"

    async def test_missing_code_redirects_with_error(
        self,
        oauth_client: httpx.AsyncClient,
    ) -> None:
        resp = await oauth_client.get(
            "/api/v1/oauth/linkedin/callback",
            params={"state": "some-state"},
        )
        assert resp.status_code == 307
        params = _parse_redirect(resp)
        assert params["oauth"] == "error"
        assert params["message"] == "no_code"

    @patch("src.api.routers.oauth._store_token", new_callable=AsyncMock)
    @patch("src.api.routers.oauth._exchange_code_for_tokens")
    async def test_exchanges_code_for_tokens(
        self,
        mock_exchange: AsyncMock,
        mock_store: AsyncMock,
        oauth_client: httpx.AsyncClient,
        oauth_app: FastAPI,
        auth_settings: Settings,
    ) -> None:
        mock_exchange.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 5184000,
        }
        # First, get a valid state by calling authorize
        headers = make_auth_header("admin", auth_settings)
        auth_resp = await oauth_client.get(
            "/api/v1/oauth/linkedin/authorize",
            headers=headers,
        )
        url = auth_resp.json()["authorization_url"]
        state = url.split("state=")[1].split("&")[0]

        # Now call callback with that state
        resp = await oauth_client.get(
            "/api/v1/oauth/linkedin/callback",
            params={"code": "auth-code-123", "state": state},
        )
        assert resp.status_code == 307
        params = _parse_redirect(resp)
        assert params["oauth"] == "success"
        mock_exchange.assert_called_once()

    @patch("src.api.routers.oauth._exchange_code_for_tokens")
    async def test_exchange_failure_redirects_with_error(
        self,
        mock_exchange: AsyncMock,
        oauth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        mock_exchange.side_effect = httpx.HTTPStatusError(
            "Bad",
            request=httpx.Request("POST", "https://x"),
            response=httpx.Response(400),
        )
        headers = make_auth_header("admin", auth_settings)
        auth_resp = await oauth_client.get(
            "/api/v1/oauth/linkedin/authorize",
            headers=headers,
        )
        url = auth_resp.json()["authorization_url"]
        state = url.split("state=")[1].split("&")[0]

        resp = await oauth_client.get(
            "/api/v1/oauth/linkedin/callback",
            params={"code": "bad-code", "state": state},
        )
        assert resp.status_code == 307
        params = _parse_redirect(resp)
        assert params["oauth"] == "error"
        assert params["message"] == "token_exchange_failed"
