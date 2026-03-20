"""Unit tests for the unified /trends/fetch endpoint."""
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.api.schemas.topics import RawTopic
from src.config.settings import Settings
from src.services.trends.protocol import TrendFetchConfig, TrendSourceError
from src.services.trends.registry import TrendSourceRegistry

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header

URL = "/api/v1/trends/fetch"
KEYWORDS = ["ai", "cyber"]


def _make_raw_topic(title: str = "Test Topic", source: str = "fake") -> RawTopic:
    return RawTopic(
        title=title,
        description="A test topic",
        source=source,
        external_url="https://example.com",
        trend_score=50.0,
        discovered_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )


class _SuccessSource:
    """Fake source that always returns one topic."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def source_name(self) -> str:
        return self._name

    async def fetch_and_normalize(self, config: TrendFetchConfig) -> list[RawTopic]:
        return [_make_raw_topic(source=self._name)]


class _FailSource:
    """Fake source that always raises TrendSourceError."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def source_name(self) -> str:
        return self._name

    async def fetch_and_normalize(self, config: TrendFetchConfig) -> list[RawTopic]:
        raise TrendSourceError(self._name, "simulated failure")


def _make_registry(*sources: object) -> TrendSourceRegistry:
    registry = TrendSourceRegistry()
    for source in sources:
        registry.register(source)  # type: ignore[arg-type]
    return registry


def _make_app(settings: Settings, registry: TrendSourceRegistry) -> FastAPI:
    """Create app with TrendReq patched and registry overridden."""
    with patch(
        "src.services.trends.google_trends_client.TrendReq",
        return_value=MagicMock(),
    ):
        app = create_app(settings)
    app.state.trend_registry = registry
    return app


@pytest.fixture
def trend_settings() -> Settings:
    return Settings(jwt_private_key=_PRIVATE_KEY, jwt_public_key=_PUBLIC_KEY)


@pytest.fixture
def trend_app(trend_settings: Settings) -> FastAPI:
    return _make_app(
        trend_settings,
        _make_registry(_SuccessSource("hackernews"), _SuccessSource("reddit")),
    )


@pytest.fixture
async def trend_client(
    trend_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=trend_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestFetchTrendsAllSourcesSuccess:
    async def test_returns_200_with_full_response(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            URL,
            json={"domain_keywords": KEYWORDS},
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "sources_queried" in data
        assert "source_results" in data
        assert len(data["sources_queried"]) == 2

    async def test_topics_combined_from_all_sources(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            URL,
            json={"domain_keywords": KEYWORDS},
            headers=make_auth_header("editor", trend_settings),
        )
        data = resp.json()
        # 2 sources x 1 topic each
        assert len(data["topics"]) == 2


class TestFetchTrendsSingleSource:
    async def test_only_requested_source_queried(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            URL,
            json={"domain_keywords": KEYWORDS, "sources": ["hackernews"]},
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sources_queried"] == ["hackernews"]
        assert "hackernews" in data["source_results"]
        assert "reddit" not in data["source_results"]


class TestFetchTrendsPartialFailure:
    async def test_partial_failure_returns_200_with_error_field(
        self,
        trend_settings: Settings,
    ) -> None:
        app = _make_app(
            trend_settings,
            _make_registry(_SuccessSource("hackernews"), _FailSource("reddit")),
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                URL,
                json={"domain_keywords": KEYWORDS},
                headers=make_auth_header("editor", trend_settings),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_results"]["reddit"]["error"] is not None
        assert data["source_results"]["hackernews"]["error"] is None


class TestFetchTrendsAllFail:
    async def test_all_sources_fail_returns_503(
        self,
        trend_settings: Settings,
    ) -> None:
        app = _make_app(
            trend_settings,
            _make_registry(_FailSource("hackernews"), _FailSource("reddit")),
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                URL,
                json={"domain_keywords": KEYWORDS},
                headers=make_auth_header("editor", trend_settings),
            )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "all_sources_unavailable"


class TestFetchTrendsUnknownSource:
    async def test_unknown_source_returns_422(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            URL,
            json={"domain_keywords": KEYWORDS, "sources": ["nonexistent"]},
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 422


class TestFetchTrendsAuth:
    async def test_no_token_returns_401(
        self,
        trend_client: httpx.AsyncClient,
    ) -> None:
        resp = await trend_client.post(
            URL,
            json={"domain_keywords": KEYWORDS},
        )
        assert resp.status_code == 401

    async def test_viewer_role_returns_403(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            URL,
            json={"domain_keywords": KEYWORDS},
            headers=make_auth_header("viewer", trend_settings),
        )
        assert resp.status_code == 403

    async def test_editor_role_returns_200(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            URL,
            json={"domain_keywords": KEYWORDS},
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200

    async def test_admin_role_returns_200(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            URL,
            json={"domain_keywords": KEYWORDS},
            headers=make_auth_header("admin", trend_settings),
        )
        assert resp.status_code == 200
