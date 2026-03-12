from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.routers.health import health_router
from src.config.settings import Settings


@pytest.fixture
def health_app() -> FastAPI:
    settings = Settings()
    app = FastAPI()
    app.state.settings = settings
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    return app


@pytest.fixture
async def health_client(
    health_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=health_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestHealthEndpoint:
    async def test_health_returns_200(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_health_response_shape(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "checks" in data

    async def test_health_version_matches_settings(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        data = response.json()
        assert data["version"] == "0.1.0"

    async def test_health_checks_all_unavailable(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        checks = response.json()["checks"]
        expected_keys = {"database", "redis", "weaviate", "celery"}
        assert set(checks.keys()) == expected_keys
        for value in checks.values():
            assert value == "unavailable"

    async def test_health_timestamp_valid_iso(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        ts = response.json()["timestamp"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo == timezone.utc

    async def test_health_status_healthy(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        assert response.json()["status"] == "healthy"


class TestReadinessEndpoint:
    async def test_readiness_returns_503_when_unavailable(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health/ready")
        assert response.status_code == 503

    async def test_readiness_response_has_same_shape(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health/ready")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "checks" in data

    async def test_readiness_status_unavailable(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health/ready")
        assert response.json()["status"] == "unavailable"
