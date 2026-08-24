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

SEO_JSON = (
    '{"title": "Regenerated SEO title sized for search results ok", '
    '"description": "A regenerated SEO description that lands within the '
    "recommended range of one hundred fifty to one hundred sixty characters "
    'for search engines today.", '
    '"keywords": ["alpha", "beta", "gamma", "delta", "epsilon"]}'
)

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

    async def test_explicit_null_clears_subtitle(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.patch(
            _url(),
            json={"subtitle": None},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 200
        assert resp.json()["subtitle"] is None

    async def test_no_auth_header_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.patch(_url(), json={"title": "x"})
        assert resp.status_code == 401


async def _make_app(auth_settings: Settings, llm: object | None) -> FastAPI:
    app = create_app(auth_settings)
    articles = InMemoryArticleRepository()
    await articles.create(_build_article(ARTICLE_ID))
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=None,  # type: ignore[arg-type]
        articles=articles,
    )
    app.state.content_service = ContentService(
        repos,
        ContentDeps(llm=llm),  # type: ignore[arg-type]
    )
    return app


class TestSeoRegenerate:
    @staticmethod
    def _regen_url(article_id: UUID | str = ARTICLE_ID) -> str:
        return f"/api/v1/articles/{article_id}/seo/regenerate"

    async def _client_for(self, app: FastAPI) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    async def test_returns_requested_field_without_persisting(
        self, auth_settings: Settings
    ) -> None:
        app = await _make_app(auth_settings, FakeListChatModel(responses=[SEO_JSON]))
        async with await self._client_for(app) as client:
            resp = await client.post(
                self._regen_url(),
                json={"field": "seo_title"},
                headers=make_auth_header("editor", auth_settings),
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["field"] == "seo_title"
            assert body["value"].startswith("Regenerated SEO title")
            # not persisted — GET still shows the original seo title
            follow = await client.get(
                _url(), headers=make_auth_header("viewer", auth_settings)
            )
            assert follow.json()["seo"]["title"] == "Quiet refactor"

    async def test_tracked_llm_records_seo_regenerate_call(
        self, auth_settings: Settings
    ) -> None:
        from datetime import UTC, datetime

        from src.models.content_pipeline import ArticleDraft
        from src.utils.llm_call_repo import InMemoryLlmCallRepository
        from src.utils.tracked_llm import TrackedChatModel

        llm_repo = InMemoryLlmCallRepository()
        tracked = TrackedChatModel(
            inner=FakeListChatModel(responses=[SEO_JSON]), repo=llm_repo
        )
        app = await _make_app(auth_settings, tracked)
        session_id = uuid4()
        await app.state.content_service.repos.drafts.create(
            ArticleDraft(
                session_id=session_id,
                topic_id=uuid4(),
                article_id=ARTICLE_ID,
                created_at=datetime.now(UTC),
            )
        )
        async with await self._client_for(app) as client:
            resp = await client.post(
                self._regen_url(),
                json={"field": "seo_description"},
                headers=make_auth_header("editor", auth_settings),
            )
            assert resp.status_code == 200
        calls = await llm_repo.list_by_session(session_id)
        assert len(calls) == 1
        assert calls[0].call_name == "seo_regenerate"

    async def test_no_llm_returns_503(self, auth_settings: Settings) -> None:
        app = await _make_app(auth_settings, None)
        async with await self._client_for(app) as client:
            resp = await client.post(
                self._regen_url(),
                json={"field": "seo_title"},
                headers=make_auth_header("editor", auth_settings),
            )
            assert resp.status_code == 503

    async def test_unknown_article_404(self, auth_settings: Settings) -> None:
        app = await _make_app(auth_settings, FakeListChatModel(responses=[SEO_JSON]))
        async with await self._client_for(app) as client:
            resp = await client.post(
                self._regen_url(uuid4()),
                json={"field": "seo_title"},
                headers=make_auth_header("editor", auth_settings),
            )
            assert resp.status_code == 404

    async def test_viewer_gets_403(self, auth_settings: Settings) -> None:
        app = await _make_app(auth_settings, FakeListChatModel(responses=[SEO_JSON]))
        async with await self._client_for(app) as client:
            resp = await client.post(
                self._regen_url(),
                json={"field": "seo_title"},
                headers=make_auth_header("viewer", auth_settings),
            )
            assert resp.status_code == 403

    async def test_eleventh_call_within_a_minute_is_429(
        self, auth_settings: Settings
    ) -> None:
        # Pins the decorator order — a mis-ordered @limiter.limit is
        # silently dead (caught in review).
        app = await _make_app(
            auth_settings, FakeListChatModel(responses=[SEO_JSON] * 11)
        )
        async with await self._client_for(app) as client:
            headers = make_auth_header("editor", auth_settings)
            for _ in range(10):
                ok = await client.post(
                    self._regen_url(), json={"field": "seo_title"}, headers=headers
                )
                assert ok.status_code == 200
            resp = await client.post(
                self._regen_url(), json={"field": "seo_title"}, headers=headers
            )
            assert resp.status_code == 429
