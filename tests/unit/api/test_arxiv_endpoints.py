from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.services.trends.arxiv_client import ArxivPaper
from tests.unit.services.conftest import MockArxivClient

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header


def _arxiv_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "domain_keywords": ["cyber"],
        "categories": ["cs.CR"],
        "max_results": 30,
    }
    base.update(overrides)
    return base


SAMPLE_PAPERS: list[ArxivPaper] = [
    {
        "arxiv_id": "2603.12345v1",
        "title": "Cybersecurity Trends in 2026",
        "abstract": "A study on cybersecurity trends.",
        "authors": ["Alice Smith"],
        "published": "2026-03-15T12:00:00Z",
        "updated": "2026-03-15T12:00:00Z",
        "pdf_url": "http://arxiv.org/pdf/2603.12345v1",
        "abs_url": "http://arxiv.org/abs/2603.12345v1",
        "primary_category": "cs.CR",
        "categories": ["cs.CR", "cs.AI"],
    },
]


@pytest.fixture
def arxiv_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def arxiv_app(arxiv_settings: Settings) -> FastAPI:
    app = create_app(arxiv_settings)
    app.state.arxiv_client = MockArxivClient(
        papers=SAMPLE_PAPERS,
    )
    return app


@pytest.fixture
async def arxiv_client(
    arxiv_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=arxiv_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestArxivEndpointAuth:
    async def test_no_token_returns_401(
        self,
        arxiv_client: httpx.AsyncClient,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
            headers=make_auth_header(
                "viewer",
                arxiv_settings,
            ),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
            headers=make_auth_header(
                "editor",
                arxiv_settings,
            ),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
            headers=make_auth_header(
                "admin",
                arxiv_settings,
            ),
        )
        assert resp.status_code == 200


class TestArxivEndpointValidation:
    async def test_empty_keywords_returns_422(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(domain_keywords=[]),
            headers=make_auth_header(
                "editor",
                arxiv_settings,
            ),
        )
        assert resp.status_code == 422


class TestArxivEndpointSuccess:
    async def test_response_shape(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
            headers=make_auth_header(
                "editor",
                arxiv_settings,
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
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(
                domain_keywords=["cooking"],
            ),
            headers=make_auth_header(
                "editor",
                arxiv_settings,
            ),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_after_filter"] == 0


class TestArxivEndpoint503:
    async def test_api_error_returns_503(
        self,
        arxiv_settings: Settings,
    ) -> None:
        from src.services.trends.arxiv_client import ArxivAPIError

        class FailingClient(MockArxivClient):
            async def fetch_papers(
                self,
                categories: list[str],
                max_results: int,
                sort_by: str,
            ) -> list[ArxivPaper]:
                raise ArxivAPIError("API down")

        app = create_app(arxiv_settings)
        app.state.arxiv_client = FailingClient()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/trends/arxiv/fetch",
                json=_arxiv_request(),
                headers=make_auth_header(
                    "editor",
                    arxiv_settings,
                ),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "arxiv_unavailable"
