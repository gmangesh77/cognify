from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.services.hackernews_client import HNStoryResponse
from tests.unit.services.conftest import MockHackerNewsClient

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header


def _hn_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "domain_keywords": ["cyber"],
        "max_results": 30,
        "min_points": 10,
    }
    base.update(overrides)
    return base


SAMPLE_STORIES: list[HNStoryResponse] = [
    {
        "objectID": "1",
        "title": "Cybersecurity Trends 2026",
        "url": "https://example.com/cyber",
        "points": 150,
        "num_comments": 42,
        "story_text": "Analysis of trends.",
        "created_at_i": 1710000000,
    },
]


@pytest.fixture
def trend_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def trend_app(trend_settings: Settings) -> FastAPI:
    app = create_app(trend_settings)
    app.state.hn_client = MockHackerNewsClient(
        stories=SAMPLE_STORIES,
    )
    return app


@pytest.fixture
async def trend_client(
    trend_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=trend_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestTrendEndpointAuth:
    async def test_no_token_returns_401(
        self,
        trend_client: httpx.AsyncClient,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
            headers=make_auth_header("viewer", trend_settings),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
            headers=make_auth_header("admin", trend_settings),
        )
        assert resp.status_code == 200


class TestTrendEndpointValidation:
    async def test_empty_keywords_returns_422(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(domain_keywords=[]),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 422


class TestTrendEndpointSuccess:
    async def test_response_shape(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "total_fetched" in data
        assert "total_after_filter" in data
        assert data["total_fetched"] == 1

    async def test_no_matches_returns_empty(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(domain_keywords=["cooking"]),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_after_filter"] == 0


class TestTrendEndpoint503:
    async def test_api_error_returns_503(
        self,
        trend_settings: Settings,
    ) -> None:
        from src.services.hackernews_client import HackerNewsAPIError

        class FailingClient(MockHackerNewsClient):
            async def fetch_stories(
                self,
                query: str,
                min_points: int,
                num_results: int,
            ) -> list[HNStoryResponse]:
                raise HackerNewsAPIError("API down")

        app = create_app(trend_settings)
        app.state.hn_client = FailingClient()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/trends/hackernews/fetch",
                json=_hn_request(),
                headers=make_auth_header(
                    "editor",
                    trend_settings,
                ),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "hackernews_unavailable"
