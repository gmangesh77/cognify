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
from src.models.content_pipeline import DraftStatus
from src.models.research import ChunkResult, FacetFindings, SourceDocument
from src.models.research_db import ResearchSession
from src.services.content import (
    ContentRepositories,
    ContentService,
    InMemoryArticleDraftRepository,
)
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

    llm = FakeListChatModel(responses=[_outline_json()])
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
    )
    app.state.content_service = ContentService(repos, llm)
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

    # Responses: outline, queries, draft, re-draft (validation)
    llm = FakeListChatModel(
        responses=[
            _outline_json(),
            _queries_json(),
            _draft_text(),
            _draft_text(),
        ],
    )
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
    )
    retriever = _make_fake_retriever()
    app.state.content_service = ContentService(repos, llm, retriever)
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
        assert len(data["sections"]) == 1

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
    async def test_returns_201(
        self,
        drafting_client: httpx.AsyncClient,
        auth_settings: Settings,
        draft_id_with_outline: str,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await drafting_client.post(
            f"/api/v1/articles/drafts/{draft_id_with_outline}/sections",
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["section_drafts"]) > 0
        assert data["total_word_count"] > 0
        assert data["status"] == "draft_complete"

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
