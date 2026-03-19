"""Tests for ContentService."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.errors import NotFoundError
from src.models.content_pipeline import ArticleDraft, DraftStatus
from src.models.research import ChunkResult, FacetFindings, SourceDocument
from src.models.research_db import ResearchSession
from src.services.content import (
    ContentRepositories,
    ContentService,
    InMemoryArticleDraftRepository,
)
from src.services.content_repositories import ContentDeps
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
    deps = ContentDeps(llm=llm)
    return ContentService(repos, deps), session


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


async def _make_service_with_retriever(
    session: ResearchSession | None = None,
) -> tuple[ContentService, ResearchSession]:
    session = session or _make_complete_session()
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)

    queries_json = json.dumps([{"section_index": 0, "queries": ["q0"]}])
    llm = FakeListChatModel(
        responses=[
            _outline_json(),  # outline generation
            queries_json,  # query generation
            "Draft text with [1] citation about research.",  # section draft
            "Expanded draft text with [1] citation about research findings.",  # re-draft (validation)
        ]
    )
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
    )
    retriever = AsyncMock()
    retriever.retrieve = AsyncMock(
        return_value=[
            ChunkResult(
                text="Chunk",
                source_url="https://a.com",
                source_title="A",
                score=0.9,
                chunk_index=0,
            ),
        ]
    )
    deps = ContentDeps(llm=llm, retriever=retriever)
    return ContentService(repos, deps), session


class TestDraftArticle:
    async def test_drafts_article_from_outline(self) -> None:
        svc, session = await _make_service_with_retriever()
        outline_draft = await svc.generate_outline(session.id)
        assert outline_draft.status == DraftStatus.OUTLINE_COMPLETE
        result = await svc.draft_article(outline_draft.id)
        assert result.status == DraftStatus.DRAFT_COMPLETE
        assert len(result.section_drafts) > 0
        assert result.total_word_count > 0

    async def test_rejects_unknown_draft(self) -> None:
        svc, _ = await _make_service_with_retriever()
        with pytest.raises(NotFoundError):
            await svc.draft_article(uuid4())

    async def test_rejects_draft_not_outline_complete(self) -> None:
        svc, session = await _make_service_with_retriever()
        draft = ArticleDraft(
            session_id=session.id,
            topic_id=session.topic_id,
            status=DraftStatus.OUTLINE_GENERATING,
            created_at=datetime.now(UTC),
        )
        await svc._repos.drafts.create(draft)
        with pytest.raises(ValueError, match="not ready"):
            await svc.draft_article(draft.id)

    async def test_requires_retriever(self) -> None:
        svc, session = await _make_service()  # no retriever
        outline_draft = await svc.generate_outline(session.id)
        with pytest.raises(ValueError, match="retriever required"):
            await svc.draft_article(outline_draft.id)


class TestContentDeps:
    async def test_service_uses_deps(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        assert draft.outline is not None
