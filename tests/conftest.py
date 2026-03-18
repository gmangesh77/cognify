from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent .env file from polluting test settings."""
    monkeypatch.setenv("COGNIFY_DEBUG", "false")
    monkeypatch.delenv("COGNIFY_JWT_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("COGNIFY_JWT_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("COGNIFY_LOG_LEVEL", raising=False)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(
    app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
