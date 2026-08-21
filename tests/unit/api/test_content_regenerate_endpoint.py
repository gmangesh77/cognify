"""Contract tests for POST /api/v1/content/section-regenerate (AUTHOR-004).

Fixtures mirror production (L-013 + the provenance trap): the ArticleDraft is
stamped with `article_id` and its `session_id` is deliberately different from
`article.provenance.research_session_id` (which holds the TOPIC id in real
articles). Anything keyed on provenance would 409 here.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from slowapi.errors import RateLimitExceeded

from src.api.errors import CognifyError, build_error_response
from src.api.rate_limiter import limiter
from src.api.routers.content import content_router
from src.api.routers.content_regenerate import content_regenerate_router
from src.config.settings import Settings
from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft, ArticleOutline, OutlineSection
from src.models.content_pipeline import ContentType as OutlineContentType
from src.models.research_db import ResearchSession
from src.models.visual import ImagePlacement, ImageSpec
from src.services.content import ContentDeps, ContentRepositories, ContentService
from src.services.content.section_history import SectionHistoryService
from src.services.content_repositories import (
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from tests.unit.api.conftest import make_auth_header
from tests.unit.api.test_content_endpoints import (
    _PRIV,
    _PUB,
    _build_article,
    _FakeArticleRepo,
    _FakeVersionRepo,
)

URL = "/api/v1/content/section-regenerate"
UPDATE_URL = "/api/v1/content/section-update"
FIGURE = (
    '<figure class="cog-figure" data-spec-id="spec-a">'
    '<img src="x.png" alt="a" /></figure>'
)
BODY = (
    "## First Section\n"
    "First section body.\n\n"
    f"{FIGURE}\n\n"
    "## Second Section\n"
    "Second section body.\n\n"
    "## References\n"
    "1. Source\n"
)


def _spec(spec_id: str, heading: str, section_index: int) -> ImageSpec:
    return ImageSpec(
        id=spec_id,
        role_style="concept",
        prompt="p",
        placement=ImagePlacement(
            anchor="before_heading", heading_text=heading, section_index=section_index
        ),
    )


def _outline_section(index: int, title: str) -> OutlineSection:
    return OutlineSection(
        index=index,
        title=title,
        description="d",
        key_points=["k"],
        target_word_count=250,
        relevant_facets=[0],
    )


class _FakeResearch:
    def __init__(self, session: ResearchSession) -> None:
        self._session = session

    async def get(self, session_id: UUID) -> ResearchSession | None:
        return self._session if self._session.id == session_id else None


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIV,
        jwt_public_key=_PUB,
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
        anthropic_api_key="test-anthropic",
    )


@pytest.fixture
def article() -> CanonicalArticle:
    # Specs on BOTH outline sections k=0 and k+1=1 (L-013 round-trip requirement).
    base = _build_article(
        uuid4(),
        image_specs=[
            _spec("spec-a", "First Section", 0),
            _spec("spec-b", "Second Section", 1),
        ],
    )
    return base.model_copy(update={"body_markdown": BODY})


@pytest.fixture
def version_repo() -> _FakeVersionRepo:
    return _FakeVersionRepo()


@pytest.fixture
def session_id() -> UUID:
    """The REAL research-session id — never equal to provenance (topic id)."""
    return uuid4()


async def _drafts_for(
    article: CanonicalArticle, session_id: UUID
) -> InMemoryArticleDraftRepository:
    assert session_id != article.provenance.research_session_id
    drafts = InMemoryArticleDraftRepository()
    await drafts.create(
        ArticleDraft(
            session_id=session_id,
            topic_id=article.provenance.research_session_id,
            article_id=article.id,  # what store_article stamps at finalisation
            created_at=datetime.now(UTC),
            outline=ArticleOutline(
                title="T",
                content_type=OutlineContentType.ARTICLE,
                total_target_words=500,
                reasoning="r",
                sections=[
                    _outline_section(0, "First Section"),
                    _outline_section(1, "Second Section"),
                ],
            ),
        )
    )
    return drafts


def _install_handlers(app: FastAPI) -> None:
    @app.exception_handler(CognifyError)
    async def _err_handler(_: Any, exc: CognifyError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(code=exc.code, message=exc.message),
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=build_error_response(
                code="rate_limited", message="Rate limit exceeded"
            ),
        )


@pytest.fixture
async def app(
    settings: Settings,
    article: CanonicalArticle,
    version_repo: _FakeVersionRepo,
    session_id: UUID,
) -> FastAPI:
    article_repo = _FakeArticleRepo(article)
    session = ResearchSession(
        id=session_id,
        topic_id=article.provenance.research_session_id,
        target_audience="CTOs",
        started_at=datetime.now(UTC),
    )
    repos = ContentRepositories(
        drafts=await _drafts_for(article, session_id),
        research=_FakeResearch(session),
        articles=InMemoryArticleRepository(),
    )
    app = FastAPI()
    app.state.settings = settings
    app.state.limiter = limiter
    app.state.article_repo = article_repo
    app.state.section_version_repo = version_repo
    app.state.section_history_service = SectionHistoryService(
        article_repo, version_repo
    )
    app.state.content_repos = repos
    app.state.content_service = ContentService(
        repos,
        ContentDeps(
            llm=FakeListChatModel(responses=["Regenerated prose [1]."] * 12),
            settings=settings,
        ),
    )
    _install_handlers(app)
    app.include_router(content_router, prefix=settings.api_v1_prefix)
    app.include_router(content_regenerate_router, prefix=settings.api_v1_prefix)
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


def _body(article: CanonicalArticle, **extra: Any) -> dict[str, Any]:
    return {"article_id": str(article.id), "section_index": 0, **extra}


def _update_body(section_id: str, markdown: str, source: str) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "markdown": markdown,
        "source": source,
        "instruction": None,
    }


class TestAuth:
    async def test_requires_auth(
        self, client: httpx.AsyncClient, article: CanonicalArticle
    ) -> None:
        res = await client.post(URL, json=_body(article))
        assert res.status_code == 401

    async def test_viewer_forbidden(
        self, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings
    ) -> None:
        res = await client.post(
            URL, json=_body(article), headers=make_auth_header("viewer", settings)
        )
        assert res.status_code == 403


class TestRegenerate:
    async def test_returns_diff_word_count_and_preserves_anchor(
        self,
        client: httpx.AsyncClient,
        article: CanonicalArticle,
        settings: Settings,
        version_repo: _FakeVersionRepo,
    ) -> None:
        res = await client.post(
            URL,
            json=_body(article, instruction="tighter"),
            headers=make_auth_header("editor", settings),
        )
        assert res.status_code == 200, res.text
        payload = res.json()
        assert payload["section_id"] == f"{article.id}:0"  # outline space
        assert payload["section_index"] == 0
        assert payload["markdown"].startswith("## First Section")
        assert 'data-spec-id="spec-a"' in payload["markdown"]
        assert "[1]" not in payload["markdown"]
        assert any(op["kind"] != "equal" for op in payload["diff"])
        assert payload["instruction"] == "tighter"
        assert payload["word_count"] == 3  # "Regenerated prose [1]."
        # FakeListChatModel carries no usage metadata.
        assert payload["tokens_input"] is None
        assert payload["tokens_output"] is None
        rows = list(version_repo._stored.values())
        assert len(rows) == 1
        assert rows[0].source == "regenerate"
        assert rows[0].created_by == "user-1"
        assert rows[0].section_index == 0
        assert payload["version_id"] == str(rows[0].id)

    async def test_round_trip_regenerate_then_accept_with_specs_on_k_and_k_plus_1(
        self,
        client: httpx.AsyncClient,
        article: CanonicalArticle,
        settings: Settings,
        version_repo: _FakeVersionRepo,
        app: FastAPI,
    ) -> None:
        headers = make_auth_header("editor", settings)
        first = await client.post(URL, json=_body(article), headers=headers)
        assert first.status_code == 200, first.text
        cand = first.json()
        accept = await client.post(
            UPDATE_URL,
            json=_update_body(cand["section_id"], cand["markdown"], "regenerate"),
            headers=headers,
        )
        assert accept.status_code == 200, accept.text
        body = app.state.article_repo.persisted_body
        assert "Regenerated prose" in body
        assert "## Second Section\nSecond section body." in body
        sources = [v.source for v in version_repo._stored.values()]
        assert sources == ["regenerate", "regenerate"]  # candidate + applied
        # Both rows address the same outline-space section; nothing was keyed
        # on provenance (draft.session_id != provenance in this fixture).
        assert {v.section_index for v in version_repo._stored.values()} == {0}

    async def test_dropping_section_k_heading_is_422_on_both_calls(
        self,
        app: FastAPI,
        client: httpx.AsyncClient,
        article: CanonicalArticle,
        settings: Settings,
    ) -> None:
        # Spec k points at a heading the article no longer has: regenerate
        # can't satisfy it, and a manual accept that renames the heading can't
        # either. Same payload from both routes.
        broken = article.model_copy(
            update={
                "image_specs": [
                    _spec("spec-h", "Gone Heading", 0),
                    _spec("spec-b", "Second Section", 1),
                ]
            }
        )
        app.state.article_repo.article = broken
        headers = make_auth_header("editor", settings)
        regen = await client.post(URL, json=_body(article), headers=headers)
        update = await client.post(
            UPDATE_URL,
            json=_update_body(
                f"{article.id}:0",
                f"## Renamed Heading\nReplacement.\n\n{FIGURE}",
                "manual",
            ),
            headers=headers,
        )
        assert regen.status_code == 422, regen.text
        assert update.status_code == 422, update.text
        assert regen.json()["detail"] == update.json()["detail"]  # same shape
        detail = regen.json()["detail"]
        assert detail["error"] == "anchor_violation"
        assert [v["kind"] for v in detail["violations"]] == ["heading_text"]
        assert detail["violations"][0]["spec_id"] == "spec-h"

    async def test_accept_that_drops_carried_figure_is_422_spec_id(
        self,
        client: httpx.AsyncClient,
        article: CanonicalArticle,
        settings: Settings,
        version_repo: _FakeVersionRepo,
    ) -> None:
        # Regenerate itself carries the figure; only an edited accept can drop it.
        headers = make_auth_header("editor", settings)
        first = await client.post(URL, json=_body(article), headers=headers)
        assert first.status_code == 200, first.text
        cand = first.json()
        stripped = cand["markdown"].replace(FIGURE, "").rstrip() + "\n"
        assert "data-spec-id" not in stripped
        accept = await client.post(
            UPDATE_URL,
            json=_update_body(cand["section_id"], stripped, "regenerate"),
            headers=headers,
        )
        assert accept.status_code == 422, accept.text
        detail = accept.json()["detail"]
        assert detail["error"] == "anchor_violation"
        assert [v["kind"] for v in detail["violations"]] == ["spec_id"]
        assert detail["violations"][0]["spec_id"] == "spec-a"
        # Only the candidate row exists — the rejected accept appended nothing.
        assert [v.source for v in version_repo._stored.values()] == ["regenerate"]

    async def test_unknown_article_404(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        res = await client.post(
            URL,
            json={"article_id": str(uuid4()), "section_index": 0},
            headers=make_auth_header("editor", settings),
        )
        assert res.status_code == 404

    async def test_references_and_out_of_range_section_404(
        self, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings
    ) -> None:
        headers = make_auth_header("editor", settings)
        refs = await client.post(
            URL, json=_body(article, section_index=2), headers=headers
        )
        far = await client.post(
            URL, json=_body(article, section_index=9), headers=headers
        )
        assert refs.status_code == 404
        assert far.status_code == 404

    async def test_missing_outline_409(
        self,
        app: FastAPI,
        client: httpx.AsyncClient,
        article: CanonicalArticle,
        settings: Settings,
    ) -> None:
        app.state.content_repos = ContentRepositories(
            drafts=InMemoryArticleDraftRepository(),
            research=app.state.content_repos.research,
            articles=InMemoryArticleRepository(),
        )
        res = await client.post(
            URL, json=_body(article), headers=make_auth_header("editor", settings)
        )
        assert res.status_code == 409

    async def test_draft_keyed_only_by_provenance_is_409(
        self,
        app: FastAPI,
        client: httpx.AsyncClient,
        article: CanonicalArticle,
        settings: Settings,
    ) -> None:
        # A draft whose session_id == provenance but with no article_id stamp
        # is NOT usable context — guards against reverting to
        # find_latest_by_session(provenance).
        drafts = InMemoryArticleDraftRepository()
        await drafts.create(
            ArticleDraft(
                session_id=article.provenance.research_session_id,
                topic_id=uuid4(),
                created_at=datetime.now(UTC),
            )
        )
        app.state.content_repos = ContentRepositories(
            drafts=drafts,
            research=app.state.content_repos.research,
            articles=InMemoryArticleRepository(),
        )
        res = await client.post(
            URL, json=_body(article), headers=make_auth_header("editor", settings)
        )
        assert res.status_code == 409

    async def test_missing_llm_503(
        self,
        app: FastAPI,
        client: httpx.AsyncClient,
        article: CanonicalArticle,
        settings: Settings,
    ) -> None:
        app.state.content_service = ContentService(
            app.state.content_repos, ContentDeps(settings=settings)
        )
        res = await client.post(
            URL, json=_body(article), headers=make_auth_header("editor", settings)
        )
        assert res.status_code == 503

    async def test_missing_content_service_503(
        self,
        app: FastAPI,
        client: httpx.AsyncClient,
        article: CanonicalArticle,
        settings: Settings,
    ) -> None:
        del app.state.content_service
        res = await client.post(
            URL, json=_body(article), headers=make_auth_header("editor", settings)
        )
        assert res.status_code == 503

    async def test_rate_limited_after_ten(
        self, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings
    ) -> None:
        headers = make_auth_header("editor", settings)
        codes = [
            (await client.post(URL, json=_body(article), headers=headers)).status_code
            for _ in range(11)
        ]
        assert codes[:10] == [200] * 10
        assert codes[10] == 429
