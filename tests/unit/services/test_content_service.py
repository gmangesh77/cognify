"""Tests for ContentService."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.errors import NotFoundError
from src.models.content_pipeline import ArticleDraft, DraftStatus
from src.models.research import FacetFindings, SourceDocument
from src.models.research_db import ResearchSession
from src.services.content import (
    ContentRepositories,
    ContentService,
    InMemoryArticleDraftRepository,
)
from src.services.research import InMemoryResearchSessionRepository


def _outline_json() -> str:
    return json.dumps(
        {
            "title": "Test Article",
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


def _make_complete_session() -> ResearchSession:
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
        topic_id=uuid4(),
        status="complete",
        started_at=datetime.now(UTC),
        findings_data=[f.model_dump() for f in findings],
        topic_title="Test Topic",
        topic_description="Test desc",
        topic_domain="tech",
    )


async def _make_service(
    session: ResearchSession | None = None,
) -> tuple[ContentService, ResearchSession]:
    session = session or _make_complete_session()
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)
    llm = FakeListChatModel(responses=[_outline_json()])
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
    )
    return ContentService(repos, llm), session


class TestGenerateOutline:
    async def test_returns_draft_with_outline(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        assert isinstance(draft, ArticleDraft)
        assert draft.outline is not None
        assert draft.status == DraftStatus.OUTLINE_COMPLETE
        assert draft.session_id == session.id

    async def test_rejects_unknown_session(self) -> None:
        svc, _ = await _make_service()
        with pytest.raises(NotFoundError):
            await svc.generate_outline(uuid4())

    async def test_rejects_incomplete_session(self) -> None:
        session = ResearchSession(
            topic_id=uuid4(),
            status="planning",
            started_at=datetime.now(UTC),
        )
        svc, _ = await _make_service(session)
        with pytest.raises(ValueError, match="not complete"):
            await svc.generate_outline(session.id)


class TestGetDraft:
    async def test_returns_draft(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        retrieved = await svc.get_draft(draft.id)
        assert retrieved.id == draft.id

    async def test_not_found(self) -> None:
        svc, _ = await _make_service()
        with pytest.raises(NotFoundError):
            await svc.get_draft(uuid4())
