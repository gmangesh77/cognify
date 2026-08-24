from collections.abc import AsyncGenerator
from datetime import UTC, datetime

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
    async def test_health_returns_200(self, health_client: httpx.AsyncClient) -> None:
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
        expected_keys = {"database", "redis", "milvus", "celery"}
        assert set(checks.keys()) == expected_keys
        for value in checks.values():
            assert value == "unavailable"

    async def test_health_timestamp_valid_iso(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        ts = response.json()["timestamp"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo == UTC

    async def test_health_status_healthy(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        assert response.json()["status"] == "healthy"


class _Inspect:
    def ping(self) -> dict[str, object]:
        return {"celery@worker": {"ok": "pong"}}


class _Control:
    def inspect(self, timeout: float) -> _Inspect:
        return _Inspect()


class _FakeCeleryApp:
    control = _Control()


class TestDispatchModeChecks:
    """INFRA-007 — redis/celery checks light up only in celery mode."""

    @pytest.fixture(autouse=True)
    def _fake_celery(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Never build a real Celery app in unit tests: its kombu broker
        # connections hang the event-loop teardown for ~80s.
        monkeypatch.setattr(
            "src.tasks.celery_app.make_celery", lambda settings: _FakeCeleryApp()
        )

    @pytest.fixture
    def celery_app_fixture(self) -> FastAPI:
        settings = Settings(_env_file=None, task_dispatch="celery")
        app = FastAPI()
        app.state.settings = settings
        app.include_router(health_router, prefix=settings.api_v1_prefix)
        return app

    @pytest.fixture
    async def celery_client(
        self, celery_app_fixture: FastAPI
    ) -> AsyncGenerator[httpx.AsyncClient, None]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=celery_app_fixture),
            base_url="http://test",
        ) as ac:
            yield ac

    async def test_redis_ok_when_ping_succeeds(
        self, celery_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _FakeRedis:
            async def ping(self) -> bool:
                return True

            async def aclose(self) -> None:
                return None

        monkeypatch.setattr(
            "redis.asyncio.from_url", lambda url: _FakeRedis()
        )
        response = await celery_client.get("/api/v1/health")
        assert response.json()["checks"]["redis"] == "ok"

    async def test_redis_unavailable_when_ping_fails(
        self, celery_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _DeadRedis:
            async def ping(self) -> bool:
                raise ConnectionError("no redis")

            async def aclose(self) -> None:
                return None

        monkeypatch.setattr(
            "redis.asyncio.from_url", lambda url: _DeadRedis()
        )
        response = await celery_client.get("/api/v1/health")
        assert response.json()["checks"]["redis"] == "unavailable"

    async def test_celery_ok_when_worker_responds(
        self, celery_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _FakeRedis:
            async def ping(self) -> bool:
                return True

            async def aclose(self) -> None:
                return None

        monkeypatch.setattr("redis.asyncio.from_url", lambda url: _FakeRedis())
        response = await celery_client.get("/api/v1/health")
        assert response.json()["checks"]["celery"] == "ok"

    async def test_inprocess_mode_leaves_checks_unavailable(
        self, health_client: httpx.AsyncClient
    ) -> None:
        response = await health_client.get("/api/v1/health")
        checks = response.json()["checks"]
        assert checks["redis"] == "unavailable"
        assert checks["celery"] == "unavailable"


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
