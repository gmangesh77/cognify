from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.services.trends.google_trends_client import (
    GTRelatedQuery,
    GTTrendingSearch,
)
from tests.unit.services.conftest import MockGoogleTrendsClient

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header

SAMPLE_TRENDING: list[GTTrendingSearch] = [
    GTTrendingSearch(title="Cybersecurity Trends 2026"),
]

SAMPLE_RELATED: list[GTRelatedQuery] = [
    GTRelatedQuery(
        title="cyber attack prevention",
        value=200,
        query_type="rising",
        seed_keyword="cyber",
    ),
]


def _gt_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "domain_keywords": ["cyber"],
        "country": "united_states",
        "max_results": 30,
    }
    base.update(overrides)
    return base


@pytest.fixture
def gt_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def gt_app(gt_settings: Settings) -> FastAPI:
    app = create_app(gt_settings)
    app.state.gt_client = MockGoogleTrendsClient(
        trending=SAMPLE_TRENDING,
        related=SAMPLE_RELATED,
    )
    return app


@pytest.fixture
async def gt_client(
    gt_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gt_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestGTEndpointAuth:
    async def test_no_token_returns_401(
        self,
        gt_client: httpx.AsyncClient,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
            headers=make_auth_header("viewer", gt_settings),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
            headers=make_auth_header("editor", gt_settings),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
            headers=make_auth_header("admin", gt_settings),
        )
        assert resp.status_code == 200


class TestGTEndpointValidation:
    async def test_empty_keywords_returns_422(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(domain_keywords=[]),
            headers=make_auth_header("editor", gt_settings),
        )
        assert resp.status_code == 422


class TestGTEndpointSuccess:
    async def test_response_shape(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
            headers=make_auth_header("editor", gt_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "total_trending" in data
        assert "total_related" in data
        assert "total_after_filter" in data

    async def test_no_matches_returns_empty(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(domain_keywords=["cooking"]),
            headers=make_auth_header("editor", gt_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_after_filter"] == 0


class TestGTEndpoint503:
    async def test_api_error_returns_503(
        self,
        gt_settings: Settings,
    ) -> None:
        from src.services.trends.google_trends_client import (
            GoogleTrendsAPIError,
        )

        class FailingClient(MockGoogleTrendsClient):
            async def fetch_trending_searches(
                self,
                country: str,
            ) -> list[GTTrendingSearch]:
                raise GoogleTrendsAPIError("API down")

        app = create_app(gt_settings)
        app.state.gt_client = FailingClient()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/trends/google/fetch",
                json=_gt_request(),
                headers=make_auth_header(
                    "editor",
                    gt_settings,
                ),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "google_trends_unavailable"
