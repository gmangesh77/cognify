"""Contract tests for PATCH /articles/{id} and POST /articles/{id}/seo/regenerate.

AUTHOR-006 — metadata editing with SEO length warnings (never errors) and
single-field SEO regenerate through the tracked pipeline LLM.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.main import create_app
from src.config.settings import Settings
from src.services.content import ContentService
from src.services.content_repositories import (
    ContentDeps,
    ContentRepositories,
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from tests.unit.api.conftest import make_auth_header
from tests.unit.api.test_content_endpoints import _build_article

ARTICLE_ID = uuid4()

IN_RANGE_TITLE = "A perfectly sized SEO title for the search results"  # 50 chars
IN_RANGE_DESC = (
    "This SEO description is written carefully to land inside the "
    "recommended range of one hundred fifty to one hundred sixty "
    "characters, which search engines like."
)  # 159 chars


@pytest.fixture
async def app(auth_settings: Settings) -> FastAPI:
    app = create_app(auth_settings)
    articles = InMemoryArticleRepository()
    await articles.create(_build_article(ARTICLE_ID))
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=None,  # type: ignore[arg-type]
        articles=articles,
    )
    deps = ContentDeps(llm=FakeListChatModel(responses=[]))
    app.state.content_service = ContentService(repos, deps)
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _url(article_id: UUID | str = ARTICLE_ID) -> str:
    return f"/api/v1/articles/{article_id}"


class TestPatchArticleMetadata:
    async def test_editor_updates_title_and_seo_with_warning(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.patch(
            _url(),
            json={"title": "New title", "seo_title": "Short"},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "New title"
        assert body["seo"]["title"] == "Short"
        assert any(w["field"] == "seo_title" for w in body["warnings"])
        # persisted — visible on the canonical GET
        follow = await client.get(
            _url(), headers=make_auth_header("viewer", auth_settings)
        )
        assert follow.status_code == 200
        assert follow.json()["title"] == "New title"

    async def test_in_range_seo_yields_no_warnings(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        assert 50 <= len(IN_RANGE_TITLE) <= 60
        assert 150 <= len(IN_RANGE_DESC) <= 160
        resp = await client.patch(
            _url(),
            json={"seo_title": IN_RANGE_TITLE, "seo_description": IN_RANGE_DESC},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 200
        assert resp.json()["warnings"] == []

    async def test_keywords_replace_list(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.patch(
            _url(),
            json={"keywords": ["alpha", "beta"]},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 200
        assert resp.json()["seo"]["keywords"] == ["alpha", "beta"]

    async def test_viewer_gets_403(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.patch(
            _url(),
            json={"title": "x"},
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 403

    async def test_unknown_article_404(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.patch(
            _url(uuid4()),
            json={"title": "x"},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 404

    async def test_empty_patch_422(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.patch(
            _url(), json={}, headers=make_auth_header("editor", auth_settings)
        )
        assert resp.status_code == 422

    async def test_over_cap_seo_title_422(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.patch(
            _url(),
            json={"seo_title": "x" * 71},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 422
