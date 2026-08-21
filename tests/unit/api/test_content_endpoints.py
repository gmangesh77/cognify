"""Contract tests for the per-section content editing endpoints.

Covers:
- POST /api/v1/content/section-rewrite
- POST /api/v1/content/section-update
- POST /api/v1/content/paragraph-tone
- GET  /api/v1/content/section/{section_id}/history
- POST /api/v1/content/section/{section_id}/restore

Auth + RBAC, anchor-violation rejection, history append on persist,
restore round-trip, tone-preset expansion. LLM patched with FakeLLM,
repos faked in-memory — no DB or network.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.routers.content import content_router
from src.config.settings import Settings
from src.models.content import (
    CanonicalArticle,
    ContentType,
    Provenance,
    SEOMetadata,
)
from src.models.visual import ImagePlacement, ImageSpec
from src.services.content.section_history import SectionHistoryService
from src.services.content.section_history_contracts import make_section_id
from tests.unit.api.conftest import make_auth_header

ARTICLE_BODY = (
    "Intro prelude paragraph.\n\n"
    "## First Section\n"
    "First section body.\n\n"
    "## Second Section\n"
    "Second section body.\n"
)


# ---------------------------------------------------------------------------
# RSA keys + minimal app
# ---------------------------------------------------------------------------


def _generate_rsa_keys() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    pk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = pk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub = (
        pk.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return priv, pub


_PRIV, _PUB = _generate_rsa_keys()


@pytest.fixture
def content_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIV,
        jwt_public_key=_PUB,
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
        anthropic_api_key="test-anthropic",
    )


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class _StoredVersion:
    id: UUID
    article_id: UUID
    section_id: str
    section_index: int
    markdown: str
    source: str
    instruction: str | None
    model: str | None
    tokens_input: int | None
    tokens_output: int | None
    usd: float | None
    created_at: datetime
    created_by: str | None


class _FakeArticleRepo:
    def __init__(self, article: CanonicalArticle) -> None:
        self.article = article
        self.persisted_body: str | None = None

    async def get(self, article_id: UUID) -> CanonicalArticle | None:
        if self.article.id != article_id:
            return None
        return self.article

    async def update_body_markdown(
        self, article_id: UUID, body_markdown: str
    ) -> CanonicalArticle | None:
        if self.article.id != article_id:
            return None
        self.persisted_body = body_markdown
        self.article = self.article.model_copy(update={"body_markdown": body_markdown})
        return self.article


class _FakeVersionRepo:
    def __init__(self) -> None:
        self._stored: dict[UUID, _StoredVersion] = {}

    async def append(self, **kwargs: Any) -> _StoredVersion:
        version_id = uuid4()
        created_at = datetime.now(UTC)
        version = _StoredVersion(
            id=version_id,
            article_id=kwargs["article_id"],
            section_id=kwargs["section_id"],
            section_index=kwargs["section_index"],
            markdown=kwargs["markdown"],
            source=kwargs["source"],
            instruction=kwargs.get("instruction"),
            model=kwargs.get("model"),
            tokens_input=kwargs.get("tokens_input"),
            tokens_output=kwargs.get("tokens_output"),
            usd=kwargs.get("usd"),
            created_at=created_at,
            created_by=kwargs.get("created_by"),
        )
        self._stored[version_id] = version
        return version

    async def list_for_section(
        self, *, article_id: UUID, section_id: str, limit: int = 50
    ) -> list[_StoredVersion]:
        rows = [
            v
            for v in self._stored.values()
            if v.article_id == article_id and v.section_id == section_id
        ]
        return sorted(rows, key=lambda v: v.created_at, reverse=True)[:limit]

    async def get(self, version_id: UUID) -> _StoredVersion | None:
        return self._stored.get(version_id)


def _build_article(
    article_id: UUID,
    *,
    image_specs: list[ImageSpec] | None = None,
) -> CanonicalArticle:
    return CanonicalArticle(
        id=article_id,
        title="Quiet refactor",
        body_markdown=ARTICLE_BODY,
        summary="Small steps compound.",
        content_type=ContentType.ARTICLE,
        seo=SEOMetadata(title="Quiet refactor", description="Summary."),
        authors=["Cognify"],
        domain="engineering",
        generated_at=datetime.now(UTC),
        provenance=Provenance(
            research_session_id=uuid4(),
            primary_model="m",
            drafting_model="m",
            embedding_model="e",
            embedding_version="v1",
        ),
        image_specs=image_specs or [],
    )


@pytest.fixture
def article_id() -> UUID:
    return uuid4()


@pytest.fixture
def section_id(article_id: UUID) -> str:
    return make_section_id(article_id, 0)


@pytest.fixture
def article_repo(article_id: UUID) -> _FakeArticleRepo:
    return _FakeArticleRepo(_build_article(article_id))


@pytest.fixture
def version_repo() -> _FakeVersionRepo:
    return _FakeVersionRepo()


@pytest.fixture
def content_app(
    content_settings: Settings,
    article_repo: _FakeArticleRepo,
    version_repo: _FakeVersionRepo,
) -> FastAPI:
    from fastapi.responses import JSONResponse

    from src.api.errors import CognifyError, build_error_response
    from src.api.rate_limiter import limiter

    app = FastAPI()
    app.state.settings = content_settings
    app.state.limiter = limiter
    app.state.article_repo = article_repo
    app.state.section_version_repo = version_repo
    app.state.section_history_service = SectionHistoryService(
        article_repo, version_repo
    )

    @app.exception_handler(CognifyError)
    async def _err_handler(_: Any, exc: CognifyError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(code=exc.code, message=exc.message),
        )

    app.include_router(content_router, prefix=content_settings.api_v1_prefix)
    return app


@pytest.fixture
async def content_client(
    content_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=content_app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_content_rate_limit() -> None:
    from src.api.rate_limiter import limiter

    limiter.reset()


def _editor_headers(settings: Settings) -> dict[str, str]:
    return make_auth_header("editor", settings)


# ---------------------------------------------------------------------------
# /content/section-rewrite
# ---------------------------------------------------------------------------


class TestSectionRewriteEndpoint:
    async def test_requires_auth(
        self, content_client: httpx.AsyncClient, section_id: str
    ) -> None:
        body = {
            "section_id": section_id,
            "instruction": "Tighten.",
            "current_markdown": "Some text.",
        }
        resp = await content_client.post("/api/v1/content/section-rewrite", json=body)
        assert resp.status_code in {401, 403}

    async def test_viewer_role_rejected(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        body = {
            "section_id": section_id,
            "instruction": "Tighten.",
            "current_markdown": "Some text.",
        }
        resp = await content_client.post(
            "/api/v1/content/section-rewrite",
            json=body,
            headers=make_auth_header("viewer", content_settings),
        )
        assert resp.status_code == 403

    async def test_returns_rewritten_fragment_and_diff(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        fake_llm = FakeListChatModel(responses=["Crisper rewritten body."])
        with patch("src.api.routers.content._get_content_llm", return_value=fake_llm):
            body = {
                "section_id": section_id,
                "instruction": "Tighten.",
                "current_markdown": "Original verbose body that meanders.",
            }
            resp = await content_client.post(
                "/api/v1/content/section-rewrite",
                json=body,
                headers=_editor_headers(content_settings),
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["markdown_fragment"] == "Crisper rewritten body."
        assert data["diff"], "expected non-empty diff"
        assert data["instruction"] == "Tighten."


# ---------------------------------------------------------------------------
# /content/section-update
# ---------------------------------------------------------------------------


class TestSectionUpdateEndpoint:
    async def test_persists_manual_edit(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
        article_repo: _FakeArticleRepo,
        version_repo: _FakeVersionRepo,
    ) -> None:
        body = {
            "section_id": section_id,
            "markdown": "## First Section\nA tighter rewrite of the body.",
            "source": "manual",
        }
        resp = await content_client.post(
            "/api/v1/content/section-update",
            json=body,
            headers=_editor_headers(content_settings),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["section_id"] == section_id
        assert "version_id" in data
        # Article body got the new section
        assert article_repo.persisted_body is not None
        assert "tighter rewrite" in article_repo.persisted_body
        # Version log got an entry
        history = await version_repo.list_for_section(
            article_id=article_repo.article.id,
            section_id=section_id,
        )
        assert len(history) == 1
        assert history[0].source == "manual"

    async def test_anchor_violation_returns_422_with_diff(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        article_id: UUID,
    ) -> None:
        # Build an article that has a heading-bound image spec for section 1.
        spec = ImageSpec(
            id="img-01",
            role_style="hero",
            prompt="placeholder",
            placement=ImagePlacement(
                anchor="before_heading",
                heading_text="First Section",
                section_index=0,
            ),
        )
        article = _build_article(article_id, image_specs=[spec])
        articles = _FakeArticleRepo(article)
        versions = _FakeVersionRepo()
        svc = SectionHistoryService(articles, versions)

        from fastapi.responses import JSONResponse

        from src.api.errors import CognifyError, build_error_response
        from src.api.rate_limiter import limiter

        app = FastAPI()
        app.state.settings = content_settings
        app.state.limiter = limiter
        app.state.article_repo = articles
        app.state.section_version_repo = versions
        app.state.section_history_service = svc

        @app.exception_handler(CognifyError)
        async def _err_handler(_: Any, exc: CognifyError) -> JSONResponse:
            return JSONResponse(
                status_code=exc.status_code,
                content=build_error_response(code=exc.code, message=exc.message),
            )

        app.include_router(content_router, prefix=content_settings.api_v1_prefix)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as ac:
            body = {
                "section_id": make_section_id(article_id, 0),
                # New body drops the heading the spec is anchored to.
                "markdown": "## Renamed Heading\nReplacement body.",
                "source": "manual",
            }
            resp = await ac.post(
                "/api/v1/content/section-update",
                json=body,
                headers=_editor_headers(content_settings),
            )
        assert resp.status_code == 422, resp.text
        payload = resp.json()
        violations = payload["detail"]["violations"]
        assert len(violations) == 1
        assert violations[0]["kind"] == "heading_text"
        assert violations[0]["spec_id"] == "img-01"
        # Body NOT persisted on violation
        assert articles.persisted_body is None


# ---------------------------------------------------------------------------
# /content/paragraph-tone
# ---------------------------------------------------------------------------


class TestParagraphToneEndpoint:
    async def test_expands_preset_server_side(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        captured: dict[str, object] = {}

        class _Capture(FakeListChatModel):
            async def ainvoke(self, messages, *args, **kwargs):  # type: ignore[override]
                captured["messages"] = messages
                return await super().ainvoke(messages, *args, **kwargs)

        llm = _Capture(responses=["Shorter paragraph."])
        with patch("src.api.routers.content._get_content_llm", return_value=llm):
            body = {
                "section_id": section_id,
                "paragraph_index": 0,
                "preset": "shorter",
                "current_markdown": "An overly wordy paragraph that should compress.",
            }
            resp = await content_client.post(
                "/api/v1/content/paragraph-tone",
                json=body,
                headers=_editor_headers(content_settings),
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["markdown_fragment"] == "Shorter paragraph."
        rendered = "\n".join(str(m.content) for m in captured["messages"])  # type: ignore[union-attr]
        # Server-side expansion of the "shorter" preset must reach the prompt.
        assert "shorter" in rendered.lower() or "30%" in rendered

    async def test_unknown_preset_rejected(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        body = {
            "section_id": section_id,
            "paragraph_index": 0,
            "preset": "wildcard_preset",
            "current_markdown": "x",
        }
        resp = await content_client.post(
            "/api/v1/content/paragraph-tone",
            json=body,
            headers=_editor_headers(content_settings),
        )
        # Pydantic enum validation rejects before reaching handler.
        assert resp.status_code in {400, 422}


# ---------------------------------------------------------------------------
# /content/section/{id}/history + /restore
# ---------------------------------------------------------------------------


class TestHumanizePreviewEndpoint:
    """DASH-007 humanization preview surface."""

    async def test_returns_diff_and_scores(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        # Drive scoring deterministically so this contract test isn't
        # brittle to slop-pattern catalogue changes.
        from src.agents.content import slop_scorer
        from src.models.content_pipeline import SlopScore

        def _fake_score_text(text: str) -> SlopScore:
            score = 80 if text.startswith("Tighter") else 30
            return SlopScore(
                score=score,
                rating="LIKELY_AI" if score < 60 else "MOSTLY_HUMAN",
                violations=[],
                phrase_deductions=0,
                pattern_deductions=0,
            )

        fake_llm = FakeListChatModel(
            responses=["Tighter rewrite of the section without the slop."]
        )
        with (
            patch("src.api.routers.content._get_content_llm", return_value=fake_llm),
            patch.object(slop_scorer, "score_text", _fake_score_text),
        ):
            resp = await content_client.post(
                "/api/v1/content/humanize-preview",
                json={
                    "section_id": section_id,
                    "current_markdown": (
                        "Let me delve into this overly verbose paragraph."
                    ),
                },
                headers=_editor_headers(content_settings),
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["section_id"] == section_id
        assert data["llm_called"] is True
        assert data["diff"], "expected non-empty diff"
        assert data["score_before"]["rating"]
        assert data["score_after"]["rating"]

    async def test_requires_auth(
        self, content_client: httpx.AsyncClient, section_id: str
    ) -> None:
        resp = await content_client.post(
            "/api/v1/content/humanize-preview",
            json={"section_id": section_id, "current_markdown": "hi"},
        )
        assert resp.status_code in {401, 403}

    async def test_viewer_role_rejected(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        resp = await content_client.post(
            "/api/v1/content/humanize-preview",
            json={"section_id": section_id, "current_markdown": "hi"},
            headers=make_auth_header("viewer", content_settings),
        )
        assert resp.status_code == 403


class TestSectionHistoryAndRestore:
    async def test_history_returns_appended_versions_newest_first(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        # Two updates → two versions.
        for body_md in (
            "## First Section\nFirst rewrite.",
            "## First Section\nSecond rewrite.",
        ):
            await content_client.post(
                "/api/v1/content/section-update",
                json={
                    "section_id": section_id,
                    "markdown": body_md,
                    "source": "manual",
                },
                headers=_editor_headers(content_settings),
            )
        resp = await content_client.get(
            f"/api/v1/content/section/{section_id}/history",
            headers=_editor_headers(content_settings),
        )
        assert resp.status_code == 200, resp.text
        versions = resp.json()["versions"]
        assert len(versions) == 2
        # Newest first → second rewrite at index 0
        assert "Second rewrite" in versions[0]["markdown"]
        assert "First rewrite" in versions[1]["markdown"]

    async def test_restore_round_trip(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
        article_repo: _FakeArticleRepo,
    ) -> None:
        # v1
        v1_resp = await content_client.post(
            "/api/v1/content/section-update",
            json={
                "section_id": section_id,
                "markdown": "## First Section\nVersion one body.",
                "source": "manual",
            },
            headers=_editor_headers(content_settings),
        )
        v1_id = v1_resp.json()["version_id"]
        # v2 (overwrites v1)
        await content_client.post(
            "/api/v1/content/section-update",
            json={
                "section_id": section_id,
                "markdown": "## First Section\nVersion two body.",
                "source": "manual",
            },
            headers=_editor_headers(content_settings),
        )
        assert "Version two" in (article_repo.persisted_body or "")

        # Restore v1
        restore_resp = await content_client.post(
            f"/api/v1/content/section/{section_id}/restore",
            json={"version_id": v1_id},
            headers=_editor_headers(content_settings),
        )
        assert restore_resp.status_code == 200, restore_resp.text
        assert "Version one" in (article_repo.persisted_body or "")

    async def test_restore_unknown_version_returns_404(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        resp = await content_client.post(
            f"/api/v1/content/section/{section_id}/restore",
            json={"version_id": str(uuid4())},
            headers=_editor_headers(content_settings),
        )
        assert resp.status_code == 404

    async def test_history_requires_auth(
        self, content_client: httpx.AsyncClient, section_id: str
    ) -> None:
        resp = await content_client.get(f"/api/v1/content/section/{section_id}/history")
        assert resp.status_code in {401, 403}

    async def test_restore_viewer_role_rejected(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        resp = await content_client.post(
            f"/api/v1/content/section/{section_id}/restore",
            json={"version_id": str(uuid4())},
            headers=make_auth_header("viewer", content_settings),
        )
        assert resp.status_code == 403


class TestOutlineIndexContractEndpoint:
    """L-013 — `{article_id}:0` is the first H2, not the prelude."""

    async def test_section_update_on_index_zero_replaces_first_h2(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        article_id: UUID,
        article_repo: _FakeArticleRepo,
    ) -> None:
        resp = await content_client.post(
            "/api/v1/content/section-update",
            json={
                "section_id": make_section_id(article_id, 0),
                "markdown": "## First Section\nReplaced first body.",
                "source": "manual",
            },
            headers=_editor_headers(content_settings),
        )
        assert resp.status_code == 200, resp.text
        body = article_repo.persisted_body or ""
        assert body.startswith("Intro prelude paragraph.")
        assert "Replaced first body." in body
        assert "## Second Section\nSecond section body." in body


class TestContentLlmSource:
    """_get_content_llm prefers the pipeline deps; falls back to ChatAnthropic."""

    async def test_rewrite_uses_content_service_deps_llm(
        self,
        content_app: FastAPI,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        from src.services.content import (
            ContentDeps,
            ContentRepositories,
            ContentService,
        )
        from src.services.content_repositories import (
            InMemoryArticleDraftRepository,
            InMemoryArticleRepository,
        )

        repos = ContentRepositories(
            drafts=InMemoryArticleDraftRepository(),
            research=None,  # type: ignore[arg-type]
            articles=InMemoryArticleRepository(),
        )
        content_app.state.content_service = ContentService(
            repos, ContentDeps(llm=FakeListChatModel(responses=["Tracked reply."]))
        )
        with patch("src.api.routers.content._build_anthropic_llm") as build:
            resp = await content_client.post(
                "/api/v1/content/section-rewrite",
                json={
                    "section_id": section_id,
                    "instruction": "Tighten.",
                    "current_markdown": "Old.",
                },
                headers=_editor_headers(content_settings),
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["markdown_fragment"] == "Tracked reply."
        build.assert_not_called()

    async def test_rewrite_falls_back_to_anthropic_builder(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        fake = FakeListChatModel(responses=["Fallback reply."])
        with patch(
            "src.api.routers.content._build_anthropic_llm", return_value=fake
        ) as build:
            resp = await content_client.post(
                "/api/v1/content/section-rewrite",
                json={
                    "section_id": section_id,
                    "instruction": "Tighten.",
                    "current_markdown": "Old.",
                },
                headers=_editor_headers(content_settings),
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["markdown_fragment"] == "Fallback reply."
        build.assert_called_once()
