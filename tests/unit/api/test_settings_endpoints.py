"""Endpoint tests for settings CRUD routes."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from src.config.settings import Settings
from src.models.settings import ApiKeyConfig, DomainConfig, GeneralConfig, LlmConfig, SeoDefaults

from .conftest import make_auth_header


def _make_domain(**kwargs) -> DomainConfig:
    defaults = dict(
        name="Cybersecurity",
        status="active",
        trend_sources=["hackernews"],
        keywords=["security"],
        article_count=3,
    )
    defaults.update(kwargs)
    return DomainConfig(**defaults)


def _make_key(**kwargs) -> ApiKeyConfig:
    defaults = dict(
        service="anthropic",
        masked_key="sk-ant-ap••••••••7f3a",
        status="active",
    )
    defaults.update(kwargs)
    return ApiKeyConfig(**defaults)


def _make_settings_repos(
    domains=None, api_keys=None, llm=None, seo=None, general=None,
) -> MagicMock:
    repos = MagicMock()
    repos.domains = MagicMock()
    repos.api_keys = MagicMock()
    repos.llm = MagicMock()
    repos.seo = MagicMock()
    repos.general = MagicMock()
    return repos


@pytest.fixture
def settings_app(auth_app, ):
    repos = _make_settings_repos()
    auth_app.state.settings_repos = repos
    return auth_app


@pytest.fixture
async def settings_client(settings_app) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=settings_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestDomainEndpoints:
    """Tests for domain config CRUD endpoints."""

    async def test_list_domains_admin_ok(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        domain = _make_domain()
        settings_app.state.settings_repos.domains.list_all = AsyncMock(return_value=[domain])
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.get("/api/v1/settings/domains", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Cybersecurity"

    async def test_list_domains_editor_denied(
        self,
        settings_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await settings_client.get("/api/v1/settings/domains", headers=headers)
        assert resp.status_code == 403

    async def test_create_domain_returns_201(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        domain = _make_domain()
        settings_app.state.settings_repos.domains.create = AsyncMock(return_value=domain)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.post(
            "/api/v1/settings/domains",
            json={"name": "Cybersecurity", "trend_sources": ["hackernews"], "keywords": ["security"]},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Cybersecurity"

    async def test_update_domain_not_found_returns_404(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        settings_app.state.settings_repos.domains.get = AsyncMock(return_value=None)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.put(
            f"/api/v1/settings/domains/{uuid4()}",
            json={"name": "New Name"},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_update_domain_ok(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        domain = _make_domain()
        updated = domain.model_copy(update={"name": "AI"})
        settings_app.state.settings_repos.domains.get = AsyncMock(return_value=domain)
        settings_app.state.settings_repos.domains.update = AsyncMock(return_value=updated)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.put(
            f"/api/v1/settings/domains/{domain.id}",
            json={"name": "AI"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "AI"

    async def test_delete_domain_returns_204(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        settings_app.state.settings_repos.domains.delete = AsyncMock(return_value=None)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.delete(
            f"/api/v1/settings/domains/{uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 204


class TestApiKeyEndpoints:
    """Tests for API key CRUD endpoints."""

    async def test_list_api_keys_admin_ok(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        key = _make_key()
        settings_app.state.settings_repos.api_keys.list_all = AsyncMock(return_value=[key])
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.get("/api/v1/settings/api-keys", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1
        assert resp.json()["items"][0]["service"] == "anthropic"

    async def test_add_api_key_returns_201(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        key = _make_key()
        settings_app.state.settings_repos.api_keys.create = AsyncMock(return_value=key)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.post(
            "/api/v1/settings/api-keys",
            json={"service": "anthropic", "key": "sk-ant-api12345678abcd7f3a"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert "masked_key" in resp.json()

    async def test_rotate_api_key_returns_200(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        key = _make_key()
        settings_app.state.settings_repos.api_keys.rotate = AsyncMock(return_value=key)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.put(
            f"/api/v1/settings/api-keys/{key.id}/rotate",
            json={"key": "sk-ant-api12345678abcd7f3a"},
            headers=headers,
        )
        assert resp.status_code == 200

    async def test_delete_api_key_returns_204(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        settings_app.state.settings_repos.api_keys.delete = AsyncMock(return_value=None)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.delete(
            f"/api/v1/settings/api-keys/{uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 204


class TestLlmConfigEndpoints:
    """Tests for LLM config endpoints."""

    async def test_get_llm_config_ok(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        config = LlmConfig()
        settings_app.state.settings_repos.llm.get_or_create = AsyncMock(return_value=config)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.get("/api/v1/settings/llm", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["primary_model"] == "claude-opus-4"

    async def test_update_llm_config_ok(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        config = LlmConfig(primary_model="claude-opus-4-5")
        settings_app.state.settings_repos.llm.get_or_create = AsyncMock(return_value=LlmConfig())
        settings_app.state.settings_repos.llm.update = AsyncMock(return_value=config)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.put(
            "/api/v1/settings/llm",
            json={"primary_model": "claude-opus-4-5"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["primary_model"] == "claude-opus-4-5"


class TestSeoDefaultsEndpoints:
    """Tests for SEO defaults endpoints."""

    async def test_get_seo_defaults_ok(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        config = SeoDefaults()
        settings_app.state.settings_repos.seo.get_or_create = AsyncMock(return_value=config)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.get("/api/v1/settings/seo", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["auto_meta_tags"] is True

    async def test_update_seo_defaults_ok(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        updated = SeoDefaults(auto_meta_tags=False)
        settings_app.state.settings_repos.seo.get_or_create = AsyncMock(return_value=SeoDefaults())
        settings_app.state.settings_repos.seo.update = AsyncMock(return_value=updated)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.put(
            "/api/v1/settings/seo",
            json={"auto_meta_tags": False},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["auto_meta_tags"] is False


class TestGeneralConfigEndpoints:
    """Tests for general config endpoints."""

    async def test_get_general_config_ok(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        config = GeneralConfig()
        settings_app.state.settings_repos.general.get_or_create = AsyncMock(return_value=config)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.get("/api/v1/settings/general", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["article_length_target"] == "3000-5000"

    async def test_update_general_config_ok(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        updated = GeneralConfig(content_tone="casual")
        settings_app.state.settings_repos.general.get_or_create = AsyncMock(return_value=GeneralConfig())
        settings_app.state.settings_repos.general.update = AsyncMock(return_value=updated)
        headers = make_auth_header("admin", auth_settings)
        resp = await settings_client.put(
            "/api/v1/settings/general",
            json={"content_tone": "casual"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content_tone"] == "casual"


class TestApiKeyMasking:
    """Tests for the _mask_key helper."""

    def test_mask_long_key(self) -> None:
        from src.api.routers.settings_domains import _mask_key
        result = _mask_key("sk-ant-api12345678abcd7f3a")
        assert result.startswith("sk-ant-a")
        assert "7f3a" in result
        assert "••••••••" in result

    def test_mask_short_key(self) -> None:
        from src.api.routers.settings_domains import _mask_key
        result = _mask_key("abcd")
        assert "••••••••" in result
