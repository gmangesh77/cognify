"""Tests for ContentService."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.errors import NotFoundError
from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft, DraftStatus
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


def _four_section_outline_json() -> str:
    sections = [
        {
            "index": i,
            "title": f"Section {i}",
            "description": f"Description {i}",
            "key_points": [f"Point {i}"],
            "target_word_count": 400,
            "relevant_facets": [0],
        }
        for i in range(4)
    ]
    return json.dumps(
        {
            "title": "Test Article",
            "content_type": "article",
            "sections": sections,
            "total_target_words": 1600,
            "reasoning": "Comprehensive coverage",
        }
    )


def _four_section_queries_json() -> str:
    return json.dumps(
        [{"section_index": i, "queries": [f"query{i}"]} for i in range(4)]
    )


def _long_draft_text() -> str:
    """Build ~400 words of prose with [1]-[5] citation markers."""
    base = (
        "Research shows important findings in this area [1]. "
        "Multiple studies confirm these results with high confidence [2]. "
        "Experts at leading institutions have validated the approach [3]. "
        "Recent experiments demonstrate significant improvements [4]. "
        "Independent teams replicated outcomes successfully [5]. "
        "Analysis reveals consistent patterns across all datasets. "
        "Several factors contribute to the observed effects. "
        "Controlled trials produced measurable differences. "
        "Statistical methods confirmed the significance of results. "
        "Peer review validated the methodology and conclusions. "
    )
    # ~70 words per repetition; 6 reps gives ~420 words
    return " ".join([base] * 6)


def _seo_json() -> str:
    return json.dumps(
        {
            "title": "Test SEO Title for the Article",
            "description": (
                "A test description that is long enough to pass "
                "validation for the SEO metadata."
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


def _make_retriever_mock() -> AsyncMock:
    retriever = AsyncMock()
    retriever.retrieve = AsyncMock(
        return_value=[
            ChunkResult(
                text=f"Chunk {i} with detailed research content.",
                source_url=f"https://src{i}.com",
                source_title=f"Source {i}",
                score=0.9 - i * 0.01,
                chunk_index=0,
            )
            for i in range(5)
        ]
    )
    return retriever


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
        articles=InMemoryArticleRepository(),
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
    draft_text = "Draft text [1] citation [2] about [3] research [4] findings [5]."
    llm = FakeListChatModel(
        responses=[
            _outline_json(),  # outline generation
            queries_json,  # query generation
            draft_text,  # section draft
            draft_text,  # re-draft (validation)
            _seo_json(),  # SEO metadata
            _discoverability_json(),  # AI discoverability
        ]
    )
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    retriever = _make_retriever_mock()
    deps = ContentDeps(llm=llm, retriever=retriever)
    return ContentService(repos, deps), session


async def _make_full_pipeline_service(
    session: ResearchSession | None = None,
) -> tuple[ContentService, ResearchSession]:
    """Build a service with 4-section outline for finalize tests.

    Produces enough words (>= 1500) and citations (>= 5) for the
    article assembler validation to pass.
    """
    session = session or _make_complete_session()
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)

    draft_text = _long_draft_text()
    llm = FakeListChatModel(
        responses=[
            _four_section_outline_json(),  # 1: outline generation
            _four_section_queries_json(),  # 2: query generation
            draft_text,  # 3: section 0 draft
            draft_text,  # 4: section 1 draft
            draft_text,  # 5: section 2 draft
            draft_text,  # 6: section 3 draft
            _seo_json(),  # 7: SEO metadata
            _discoverability_json(),  # 8: AI discoverability
        ]
    )
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    retriever = _make_retriever_mock()
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


class TestDraftArticleWithSEO:
    async def test_draft_article_includes_seo_result(self) -> None:
        svc, session = await _make_service_with_retriever()
        outline_draft = await svc.generate_outline(session.id)
        result = await svc.draft_article(outline_draft.id)
        assert result.seo_result is not None
        assert result.seo_result.summary != ""
        assert len(result.seo_result.key_claims) >= 1


class TestFinalizeArticle:
    async def test_happy_path(self) -> None:
        svc, session = await _make_full_pipeline_service()
        outline_draft = await svc.generate_outline(session.id)
        drafted = await svc.draft_article(outline_draft.id)
        result = await svc.finalize_article(drafted.id)
        assert isinstance(result, CanonicalArticle)
        assert result.domain == "tech"
        # Draft should be updated to COMPLETE
        updated_draft = await svc.get_draft(drafted.id)
        assert updated_draft.status == DraftStatus.COMPLETE
        assert updated_draft.article_id == result.id

    async def test_rejects_unknown_draft(self) -> None:
        svc, _ = await _make_full_pipeline_service()
        with pytest.raises(NotFoundError):
            await svc.finalize_article(uuid4())

    async def test_rejects_non_draft_complete(self) -> None:
        svc, session = await _make_full_pipeline_service()
        outline_draft = await svc.generate_outline(session.id)
        with pytest.raises(ValueError, match="not ready"):
            await svc.finalize_article(outline_draft.id)

    async def test_rejects_no_seo_result(self) -> None:
        svc, session = await _make_full_pipeline_service()
        outline_draft = await svc.generate_outline(session.id)
        drafted = await svc.draft_article(outline_draft.id)
        cleared = drafted.model_copy(update={"seo_result": None})
        await svc._repos.drafts.update(cleared)
        with pytest.raises(ValueError, match="SEO"):
            await svc.finalize_article(drafted.id)


class TestGetArticle:
    async def test_returns_article(self) -> None:
        svc, session = await _make_full_pipeline_service()
        outline_draft = await svc.generate_outline(session.id)
        drafted = await svc.draft_article(outline_draft.id)
        article = await svc.finalize_article(drafted.id)
        retrieved = await svc.get_article(article.id)
        assert retrieved.id == article.id

    async def test_not_found(self) -> None:
        svc, _ = await _make_full_pipeline_service()
        with pytest.raises(NotFoundError):
            await svc.get_article(uuid4())


class TestContentDeps:
    async def test_service_uses_deps(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        assert draft.outline is not None
