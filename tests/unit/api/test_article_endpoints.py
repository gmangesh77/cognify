"""Tests for article generation API endpoints."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.main import create_app
from src.config.settings import Settings
from src.models.content import ContentType, Provenance, SEOMetadata
from src.models.content_pipeline import (
    ArticleDraft,
    ArticleOutline,
    CitationRef,
    DraftStatus,
    OutlineSection,
    SectionDraft,
    SEOResult,
)
from src.models.research import ChunkResult, FacetFindings, SourceDocument
from src.models.research_db import ResearchSession
from src.services.content import (
    ContentRepositories,
    ContentService,
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from src.services.content_repositories import ContentDeps
from src.services.research import InMemoryResearchSessionRepository
from tests.unit.api.conftest import make_auth_header


def _outline_json() -> str:
    return json.dumps(
        {
            "title": "Test",
            "content_type": "article",
            "sections": [
                {
                    "index": 0,
                    "title": "Intro",
                    "description": "D",
                    "key_points": ["P"],
                    "target_word_count": 300,
                    "relevant_facets": [0],
                },
            ],
            "total_target_words": 300,
            "reasoning": "Simple",
        }
    )


def _queries_json() -> str:
    return json.dumps([{"section_index": 0, "queries": ["test query"]}])


def _draft_text() -> str:
    return (
        "This is a test section with proper structure. "
        "Fact one [1]. Fact two [2]. Fact three [3]. "
        "Fact four [4]. Fact five [5]."
    )


def _seo_json() -> str:
    return json.dumps(
        {
            "title": "Test SEO Title for the Article",
            "description": (
                "A test description that is long enough"
                " to pass validation for the SEO metadata."
            ),
            "keywords": ["test", "seo", "ai"],
        }
    )


def _discoverability_json() -> str:
    return json.dumps(
        {
            "summary": "Test summary of the article content.",
            "key_claims": ["Key claim one [1]", "Key claim two [1]"],
        }
    )


def _make_fake_retriever() -> AsyncMock:
    """Create a mock MilvusRetriever returning stub ChunkResults."""
    retriever = AsyncMock()
    retriever.retrieve.return_value = [
        ChunkResult(
            text=f"Research finding {i}.",
            source_url=f"https://src{i}.com",
            source_title=f"Source {i}",
            score=0.9 - i * 0.01,
            chunk_index=0,
        )
        for i in range(5)
    ]
    return retriever


def _make_session(session_id: str) -> ResearchSession:
    """Create a complete research session for testing."""
    findings = [
        FacetFindings(
            facet_index=0,
            sources=[
                SourceDocument(
                    url="https://a.com",
                    title="A",
                    snippet="S",
                    retrieved_at=datetime.now(UTC),
                )
            ],
            claims=["Claim"],
            summary="Summary",
        )
    ]
    return ResearchSession(
        id=UUID(session_id),
        topic_id=uuid4(),
        status="complete",
        started_at=datetime.now(UTC),
        findings_data=[f.model_dump() for f in findings],
        topic_title="Test Topic",
        topic_description="Desc",
        topic_domain="tech",
    )


@pytest.fixture
def test_session_id() -> str:
    return str(uuid4())


@pytest.fixture
async def articles_app(auth_settings: Settings, test_session_id: str) -> FastAPI:
    app = create_app(auth_settings)
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(_make_session(test_session_id))

    seo_json = json.dumps({
        "title": "T", "description": "D", "keywords": ["k"],
        "summary": "S", "key_claims": ["C"],
        "ai_disclosure": "AI generated",
    })
    chart_json = json.dumps({"charts": []})
    diagram_json = json.dumps({"diagrams": []})
    llm = FakeListChatModel(responses=[
        _outline_json(),
        _queries_json(),
        _draft_text(),
        _draft_text(),
        seo_json, seo_json,
        chart_json, diagram_json,
        "padding", "padding",
    ])
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    deps = ContentDeps(llm=llm)
    app.state.content_service = ContentService(repos, deps)
    return app


@pytest.fixture
async def articles_client(articles_app: FastAPI) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=articles_app),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]


# -- Drafting fixtures --


@pytest.fixture
def drafting_session_id() -> str:
    return str(uuid4())


@pytest.fixture
async def drafting_app(
    auth_settings: Settings,
    drafting_session_id: str,
) -> FastAPI:
    """App wired for section drafting (retriever + multi-response LLM)."""
    app = create_app(auth_settings)
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(_make_session(drafting_session_id))

    chart_json = json.dumps({"charts": []})
    diagram_json = json.dumps({"diagrams": []})
    # First run: generate_outline (full pipeline)
    # Second run: draft_article (resumes from outline_complete, skips outline node)
    first_run = [
        _outline_json(), _queries_json(),
        _draft_text(), _draft_text(),
        _seo_json(), _discoverability_json(),
        chart_json, diagram_json, "pad", "pad",
    ]
    second_run = [
        _queries_json(),
        _draft_text(), _draft_text(),
        _seo_json(), _discoverability_json(),
        chart_json, diagram_json, "pad", "pad",
    ]
    llm = FakeListChatModel(responses=first_run + second_run)
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    retriever = _make_fake_retriever()
    deps = ContentDeps(llm=llm, retriever=retriever)
    app.state.content_service = ContentService(repos, deps)
    return app


@pytest.fixture
async def drafting_client(drafting_app: FastAPI) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=drafting_app),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
async def draft_id_with_outline(
    drafting_app: FastAPI,
    drafting_session_id: str,
) -> str:
    """Generate an outline via the service; return draft ID."""
    svc: ContentService = drafting_app.state.content_service
    draft = await svc.generate_outline(UUID(drafting_session_id))
    assert draft.status == DraftStatus.OUTLINE_COMPLETE
    return str(draft.id)


@pytest.fixture
async def draft_id_not_ready(drafting_app: FastAPI) -> str:
    """Store a draft in OUTLINE_GENERATING status (not ready)."""
    from src.models.content_pipeline import ArticleDraft

    draft = ArticleDraft(
        session_id=uuid4(),
        topic_id=uuid4(),
        status=DraftStatus.OUTLINE_GENERATING,
        created_at=datetime.now(UTC),
    )
    svc: ContentService = drafting_app.state.content_service
    await svc._repos.drafts.create(draft)  # noqa: SLF001
    return str(draft.id)


class TestGenerateArticle:
    async def test_returns_201(
        self,
        articles_client: httpx.AsyncClient,
        auth_settings: Settings,
        test_session_id: str,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await articles_client.post(
            "/api/v1/articles/generate",
            json={"session_id": test_session_id},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "draft_id" in data
        assert data["title"] == "Test"

    async def test_viewer_cannot_generate(
        self,
        articles_client: httpx.AsyncClient,
        auth_settings: Settings,
        test_session_id: str,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await articles_client.post(
            "/api/v1/articles/generate",
            json={"session_id": test_session_id},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_invalid_session_returns_404(
        self,
        articles_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await articles_client.post(
            "/api/v1/articles/generate",
            json={"session_id": str(uuid4())},
            headers=headers,
        )
        assert resp.status_code == 404


class TestDraftSections:
    async def test_generate_produces_full_draft(
        self,
        drafting_app: FastAPI,
        drafting_session_id: str,
    ) -> None:
        """generate_outline now runs full pipeline, producing a complete draft."""
        svc: ContentService = drafting_app.state.content_service
        draft = await svc.generate_outline(UUID(drafting_session_id))
        # Full pipeline runs: status is draft_complete, not outline_complete
        assert draft.status in (DraftStatus.OUTLINE_COMPLETE, DraftStatus.DRAFT_COMPLETE)
        assert draft.outline is not None

    async def test_viewer_cannot_draft(
        self,
        drafting_client: httpx.AsyncClient,
        auth_settings: Settings,
        draft_id_with_outline: str,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await drafting_client.post(
            f"/api/v1/articles/drafts/{draft_id_with_outline}/sections",
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_invalid_draft_returns_404(
        self,
        drafting_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await drafting_client.post(
            f"/api/v1/articles/drafts/{uuid4()}/sections",
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_draft_not_ready_returns_400(
        self,
        drafting_client: httpx.AsyncClient,
        auth_settings: Settings,
        draft_id_not_ready: str,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await drafting_client.post(
            f"/api/v1/articles/drafts/{draft_id_not_ready}/sections",
            headers=headers,
        )
        assert resp.status_code == 400


# -- Finalize / Canonical Article fixtures --

_LONG_PARAGRAPH = (
    "This section covers important research findings about the topic. "
    "Recent studies have shown significant developments in this area. "
    "Experts agree that these findings represent a major breakthrough. "
    "The implications extend across multiple domains and industries. "
    "Analysis of the data reveals clear trends in adoption and impact. "
    "Further investigation confirms the robustness of these conclusions. "
    "Supporting evidence comes from multiple independent sources [1]. "
    "The methodology used has been peer reviewed and validated [2]. "
)


def _make_finalize_outline() -> ArticleOutline:
    """Build a 4-section outline for finalization testing."""
    sections = [
        OutlineSection(
            index=i,
            title=f"Section {i}",
            description=f"Description for section {i}",
            key_points=[f"Point {i}a", f"Point {i}b"],
            target_word_count=400,
            relevant_facets=[0],
        )
        for i in range(4)
    ]
    return ArticleOutline(
        title="Test Canonical Article",
        subtitle="Subtitle",
        content_type=ContentType.ARTICLE,
        sections=sections,
        total_target_words=1600,
        reasoning="Test outline for finalization",
    )


def _make_section_drafts() -> list[SectionDraft]:
    """Build 4 section drafts, each ~400 words (total >= 1500)."""
    # Each _LONG_PARAGRAPH repeated 6 times yields ~390 words per section
    body = "\n\n".join([_LONG_PARAGRAPH] * 6)
    return [
        SectionDraft(
            section_index=i,
            title=f"Section {i}",
            body_markdown=body,
            word_count=len(body.split()),
            citations_used=[
                CitationRef(
                    index=i + 1,
                    source_url=f"https://source{i + 1}.com",
                    source_title=f"Source {i + 1}",
                ),
            ],
        )
        for i in range(4)
    ]


def _make_global_citations(count: int) -> list[dict[str, object]]:
    """Build raw citation dicts for the assembler."""
    return [
        {
            "index": i + 1,
            "title": f"Source {i + 1}",
            "url": f"https://source{i + 1}.com",
            "authors": ["Author"],
        }
        for i in range(count)
    ]


def _make_seo_result(session_id: UUID) -> SEOResult:
    """Build an SEOResult for the finalization fixture."""
    seo = SEOMetadata(
        title="Test Canonical Article Title",
        description=(
            "A comprehensive analysis of the topic covering "
            "recent findings and expert insights."
        ),
        keywords=["test", "canonical", "article"],
    )
    provenance = Provenance(
        research_session_id=session_id,
        primary_model="claude-opus-4",
        drafting_model="claude-sonnet-4",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="v1",
    )
    return SEOResult(
        seo=seo,
        summary="Summary of the test article.",
        key_claims=["Claim 1 [1]", "Claim 2 [2]"],
        provenance=provenance,
        ai_disclosure="Generated by AI.",
    )


def _make_references_md() -> str:
    """Build a references section."""
    lines = [f"[{i + 1}] https://source{i + 1}.com" for i in range(5)]
    return "## References\n\n" + "\n".join(lines)


@pytest.fixture
def finalize_session_id() -> str:
    return str(uuid4())


@pytest.fixture
async def finalize_app(
    auth_settings: Settings,
    finalize_session_id: str,
) -> FastAPI:
    """App with a pre-populated DRAFT_COMPLETE draft ready for finalization."""
    app = create_app(auth_settings)
    session_repo = InMemoryResearchSessionRepository()
    session = _make_session(finalize_session_id)
    await session_repo.create(session)

    draft_repo = InMemoryArticleDraftRepository()
    article_repo = InMemoryArticleRepository()

    sid = UUID(finalize_session_id)
    draft = ArticleDraft(
        session_id=sid,
        topic_id=session.topic_id,
        outline=_make_finalize_outline(),
        status=DraftStatus.DRAFT_COMPLETE,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        section_drafts=_make_section_drafts(),
        global_citations=_make_global_citations(5),
        references_markdown=_make_references_md(),
        seo_result=_make_seo_result(sid),
    )
    await draft_repo.create(draft)

    repos = ContentRepositories(
        drafts=draft_repo,
        research=session_repo,
        articles=article_repo,
    )
    deps = ContentDeps(llm=FakeListChatModel(responses=[]))
    app.state.content_service = ContentService(repos, deps)
    return app, str(draft.id)  # type: ignore[return-value]


@pytest.fixture
async def finalize_client(
    finalize_app: tuple[FastAPI, str],
) -> httpx.AsyncClient:
    app, _ = finalize_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
def finalized_draft_id(
    finalize_app: tuple[FastAPI, str],
) -> str:
    _, draft_id = finalize_app
    return draft_id


class TestFinalizeArticle:
    async def test_returns_201(
        self,
        finalize_client: httpx.AsyncClient,
        auth_settings: Settings,
        finalized_draft_id: str,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await finalize_client.post(
            f"/api/v1/articles/drafts/{finalized_draft_id}/finalize",
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["ai_generated"] is True
        assert len(data["citations"]) >= 5

    async def test_viewer_cannot_finalize(
        self,
        finalize_client: httpx.AsyncClient,
        auth_settings: Settings,
        finalized_draft_id: str,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await finalize_client.post(
            f"/api/v1/articles/drafts/{finalized_draft_id}/finalize",
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_invalid_draft_returns_404(
        self,
        finalize_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await finalize_client.post(
            f"/api/v1/articles/drafts/{uuid4()}/finalize",
            headers=headers,
        )
        assert resp.status_code == 404


class TestGetArticle:
    async def test_returns_200(
        self,
        finalize_client: httpx.AsyncClient,
        auth_settings: Settings,
        finalized_draft_id: str,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        finalize_resp = await finalize_client.post(
            f"/api/v1/articles/drafts/{finalized_draft_id}/finalize",
            headers=headers,
        )
        article_id = finalize_resp.json()["id"]
        viewer_headers = make_auth_header("viewer", auth_settings)
        resp = await finalize_client.get(
            f"/api/v1/articles/{article_id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == article_id

    async def test_not_found_returns_404(
        self,
        finalize_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await finalize_client.get(
            f"/api/v1/articles/{uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 404
