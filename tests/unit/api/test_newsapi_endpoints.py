from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.services.newsapi_client import NewsAPIArticle
from tests.unit.services.conftest import MockNewsAPIClient

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header


def _newsapi_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "domain_keywords": ["cyber"],
        "max_results": 30,
        "category": "technology",
        "country": "us",
    }
    base.update(overrides)
    return base


SAMPLE_ARTICLES: list[NewsAPIArticle] = [
    {
        "title": "Cybersecurity Trends 2026",
        "description": "Analysis of cybersecurity trends.",
        "url": "https://example.com/cyber",
        "urlToImage": "https://example.com/img.jpg",
        "publishedAt": "2026-03-15T10:00:00Z",
        "source": {"id": "test", "name": "Test Source"},
        "author": "Jane Doe",
        "content": "Full content about cybersecurity.",
    },
]


@pytest.fixture
def newsapi_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def newsapi_app(newsapi_settings: Settings) -> FastAPI:
    app = create_app(newsapi_settings)
    app.state.newsapi_client = MockNewsAPIClient(
        articles=SAMPLE_ARTICLES,
    )
    return app


@pytest.fixture
async def newsapi_client(
    newsapi_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=newsapi_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestNewsAPIEndpointAuth:
    async def test_no_token_returns_401(
        self,
        newsapi_client: httpx.AsyncClient,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
            headers=make_auth_header(
                "viewer", newsapi_settings,
            ),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
            headers=make_auth_header(
                "editor", newsapi_settings,
            ),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
            headers=make_auth_header(
                "admin", newsapi_settings,
            ),
        )
        assert resp.status_code == 200


class TestNewsAPIEndpointValidation:
    async def test_empty_keywords_returns_422(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(domain_keywords=[]),
            headers=make_auth_header(
                "editor", newsapi_settings,
            ),
        )
        assert resp.status_code == 422


class TestNewsAPIEndpointSuccess:
    async def test_response_shape(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
            headers=make_auth_header(
                "editor", newsapi_settings,
            ),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "total_fetched" in data
        assert "total_after_filter" in data
        assert data["total_fetched"] == 1

    async def test_no_matches_returns_empty(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(
                domain_keywords=["cooking"],
            ),
            headers=make_auth_header(
                "editor", newsapi_settings,
            ),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_after_filter"] == 0


class TestNewsAPIEndpoint503:
    async def test_api_error_returns_503(
        self,
        newsapi_settings: Settings,
    ) -> None:
        from src.services.newsapi_client import NewsAPIError

        class FailingClient(MockNewsAPIClient):
            async def fetch_top_headlines(
                self,
                category: str,
                country: str,
                page_size: int,
            ) -> list[NewsAPIArticle]:
                raise NewsAPIError("API down")

        app = create_app(newsapi_settings)
        app.state.newsapi_client = FailingClient()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/trends/newsapi/fetch",
                json=_newsapi_request(),
                headers=make_auth_header(
                    "editor",
                    newsapi_settings,
                ),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "newsapi_unavailable"
