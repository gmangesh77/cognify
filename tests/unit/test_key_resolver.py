"""Tests for runtime API key resolver (DB -> env fallback)."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config.settings import Settings
from src.utils.key_resolver import ApiKeyResolver

_SERVICE_MAP = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "serpapi": "serpapi_api_key",
    "newsapi": "newsapi_api_key",
    "reddit_client_id": "reddit_client_id",
    "reddit_client_secret": "reddit_client_secret",
    "semantic_scholar": "semantic_scholar_api_key",
}


@pytest.fixture
def settings() -> Settings:
    return Settings(
        anthropic_api_key="env-anthropic",
        serpapi_api_key="env-serpapi",
    )


@pytest.fixture
def repo() -> AsyncMock:
    return AsyncMock()


class TestApiKeyResolver:
    async def test_returns_db_key_when_present(
        self,
        repo: AsyncMock,
        settings: Settings,
    ) -> None:
        repo.get_encrypted_key_by_service.return_value = "encrypted-db-key"
        resolver = ApiKeyResolver(repo, settings)
        decrypt_path = "src.utils.key_resolver.decrypt_value"
        with patch(decrypt_path, return_value="decrypted-db-key"):
            result = await resolver.resolve("anthropic")
        assert result == "decrypted-db-key"

    async def test_falls_back_to_env(
        self,
        repo: AsyncMock,
        settings: Settings,
    ) -> None:
        repo.get_encrypted_key_by_service.return_value = None
        resolver = ApiKeyResolver(repo, settings)
        result = await resolver.resolve("anthropic")
        assert result == "env-anthropic"

    async def test_returns_none_when_no_key(
        self,
        repo: AsyncMock,
        settings: Settings,
    ) -> None:
        repo.get_encrypted_key_by_service.return_value = None
        resolver = ApiKeyResolver(repo, settings)
        result = await resolver.resolve("newsapi")
        assert result is None

    async def test_resolve_all_returns_update_dict(
        self,
        repo: AsyncMock,
        settings: Settings,
    ) -> None:
        repo.get_encrypted_key_by_service.return_value = None
        resolver = ApiKeyResolver(repo, settings)
        updates = await resolver.resolve_all()
        assert updates["anthropic_api_key"] == "env-anthropic"
        assert updates["serpapi_api_key"] == "env-serpapi"

    async def test_unknown_service_returns_none(
        self,
        repo: AsyncMock,
        settings: Settings,
    ) -> None:
        repo.get_encrypted_key_by_service.return_value = None
        resolver = ApiKeyResolver(repo, settings)
        result = await resolver.resolve("unknown_service")
        assert result is None
