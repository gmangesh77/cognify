"""Runtime API key resolver: DB (encrypted) -> .env fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.utils.encryption import decrypt_value

if TYPE_CHECKING:
    from src.config.settings import Settings
    from src.db.settings_repositories import PgApiKeyRepository

logger = structlog.get_logger()

_SERVICE_TO_SETTING: dict[str, str] = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "serpapi": "serpapi_api_key",
    "newsapi": "newsapi_api_key",
    "reddit_client_id": "reddit_client_id",
    "reddit_client_secret": "reddit_client_secret",
    "semantic_scholar": "semantic_scholar_api_key",
    "ghost_admin_api_key": "ghost_admin_api_key",
    "medium_api_token": "medium_api_token",
}


class ApiKeyResolver:
    """Resolve API keys: DB first (decrypt), then .env fallback."""

    def __init__(self, repo: PgApiKeyRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings

    async def resolve(self, service: str) -> str | None:
        """Return the key for *service*, or None if unavailable."""
        encrypted = await self._repo.get_encrypted_key_by_service(service)
        if encrypted:
            value = decrypt_value(encrypted)
            logger.debug("key_resolved_from_db", service=service)
            return value
        setting_field = _SERVICE_TO_SETTING.get(service)
        if setting_field:
            env_val = getattr(self._settings, setting_field, "")
            if env_val:
                return env_val
        return None

    async def resolve_all(self) -> dict[str, str]:
        """Resolve all known services, returning a settings-field update dict."""
        updates: dict[str, str] = {}
        for service, field in _SERVICE_TO_SETTING.items():
            value = await self.resolve(service)
            if value:
                updates[field] = value
        return updates
