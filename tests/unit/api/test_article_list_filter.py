"""GET /articles status filter (AUTHOR-007).

NOTE the list endpoint reads `app.state.article_repo` directly (not the
content service) — the fixture must set it explicitly.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.models.content import ArticleStatus
from src.services.content_repositories import InMemoryArticleRepository
from tests.unit.api.conftest import make_auth_header
from tests.unit.api.test_content_endpoints import _build_article

DRAFT_ID = uuid4()
APPROVED_ID = uuid4()
PUBLISHED_ID = uuid4()


@pytest.fixture
async def app(auth_settings: Settings) -> FastAPI:
    app = create_app(auth_settings)
    repo = InMemoryArticleRepository()
    await repo.create(_build_article(DRAFT_ID))
    await repo.create(
        _build_article(APPROVED_ID).model_copy(
            update={"status": ArticleStatus.APPROVED}
        )
    )
    await repo.create(
        _build_article(PUBLISHED_ID).model_copy(
            update={"status": ArticleStatus.PUBLISHED}
        )
    )
    app.state.article_repo = repo
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestArticleListStatusFilter:
    async def test_unfiltered_returns_all_with_status_field(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.get(
            "/api/v1/articles", headers=make_auth_header("viewer", auth_settings)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        statuses = {a["id"]: a["status"] for a in body["items"]}
        assert statuses[str(DRAFT_ID)] == "draft"
        assert statuses[str(APPROVED_ID)] == "approved"

    async def test_filter_narrows_items_and_total(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.get(
            "/api/v1/articles",
            params={"status": "approved"},
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert [a["id"] for a in body["items"]] == [str(APPROVED_ID)]

    async def test_invalid_status_value_422(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.get(
            "/api/v1/articles",
            params={"status": "complete"},
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 422
