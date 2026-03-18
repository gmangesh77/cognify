"""Tests for article generation API endpoints."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.main import create_app
from src.config.settings import Settings
from src.models.research import FacetFindings, SourceDocument
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


@pytest.fixture
def test_session_id() -> str:
    return str(uuid4())


@pytest.fixture
async def articles_app(auth_settings: Settings, test_session_id: str) -> FastAPI:
    app = create_app(auth_settings)
    session_repo = InMemoryResearchSessionRepository()

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
    session = ResearchSession(
        id=UUID(test_session_id),
        topic_id=uuid4(),
        status="complete",
        started_at=datetime.now(UTC),
        findings_data=[f.model_dump() for f in findings],
        topic_title="Test Topic",
        topic_description="Desc",
        topic_domain="tech",
    )
    await session_repo.create(session)

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
