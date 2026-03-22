"""Integration tests for PostgreSQL repository implementations.

Tests all 5 PG repositories against a real PostgreSQL database.
Requires PostgreSQL running on localhost:5432 (user: cognify, password: cognify, db: cognify).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.db import tables  # noqa: F401 — registers all table models on Base.metadata
from src.db.base import Base
from src.db.engine import create_async_engine, get_session_factory
from src.db.repositories import (
    PgAgentStepRepository,
    PgArticleDraftRepository,
    PgArticleRepository,
    PgResearchSessionRepository,
    PgTopicRepository,
)
from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
    StructuredDataLD,
)
from src.models.content_pipeline import ArticleDraft, DraftStatus
from src.models.research import TopicInput
from src.models.research_db import AgentStep, ResearchSession

_DB_URL = "postgresql+asyncpg://cognify:cognify@localhost:5432/cognify"


@pytest_asyncio.fixture
async def session_factory() -> async_sessionmaker[AsyncSession]:  # type: ignore[misc]
    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = get_session_factory(engine)
    yield sf  # type: ignore[misc]
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helper seed functions
# ---------------------------------------------------------------------------


async def _seed_topic(sf: async_sessionmaker[AsyncSession]) -> TopicInput:
    """Create a topic row and return the TopicInput for FK references."""
    repo = PgTopicRepository(sf)
    topic = TopicInput(
        id=uuid4(),
        title=f"Test Topic {uuid4().hex[:8]}",
        description="A test topic for integration testing",
        domain="cybersecurity",
    )
    await repo._seed_async(topic)
    return topic


async def _seed_session(
    sf: async_sessionmaker[AsyncSession],
    topic_id: object,
) -> ResearchSession:
    """Create a research session row and return the ResearchSession model."""
    from uuid import UUID

    repo = PgResearchSessionRepository(sf)
    session = ResearchSession(
        id=uuid4(),
        topic_id=UUID(str(topic_id)),
        status="planning",
        topic_title="Test Session Topic",
        topic_description="Session for integration testing",
        topic_domain="cybersecurity",
        started_at=datetime.now(UTC),
    )
    return await repo.create(session)


# ---------------------------------------------------------------------------
# TestPgTopicRepository
# ---------------------------------------------------------------------------


class TestPgTopicRepository:
    async def test_seed_and_get(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repo = PgTopicRepository(session_factory)
        topic = await _seed_topic(session_factory)

        result = await repo.get(topic.id)

        assert result is not None
        assert result.id == topic.id
        assert result.title == topic.title
        assert result.domain == topic.domain

    async def test_exists_returns_true_for_seeded(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repo = PgTopicRepository(session_factory)
        topic = await _seed_topic(session_factory)

        assert await repo.exists(topic.id) is True

    async def test_exists_returns_false_for_missing(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repo = PgTopicRepository(session_factory)
        assert await repo.exists(uuid4()) is False

    async def test_get_returns_none_for_missing(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repo = PgTopicRepository(session_factory)
        assert await repo.get(uuid4()) is None

    async def test_seed_idempotent(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Calling _seed_async twice with the same topic must not raise."""
        repo = PgTopicRepository(session_factory)
        topic = await _seed_topic(session_factory)
        # second call should be a no-op
        await repo._seed_async(topic)
        result = await repo.get(topic.id)
        assert result is not None
        assert result.id == topic.id


# ---------------------------------------------------------------------------
# TestPgResearchSessionRepository
# ---------------------------------------------------------------------------


class TestPgResearchSessionRepository:
    async def test_create_and_get(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgResearchSessionRepository(session_factory)

        result = await repo.get(session.id)

        assert result is not None
        assert result.id == session.id
        assert result.topic_id == topic.id
        assert result.status == "planning"

    async def test_update_status(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgResearchSessionRepository(session_factory)

        updated = session.model_copy(
            update={
                "status": "complete",
                "findings_count": 5,
                "indexed_count": 20,
                "duration_seconds": 42.5,
                "completed_at": datetime.now(UTC),
            }
        )
        result = await repo.update(updated)

        assert result.status == "complete"
        assert result.findings_count == 5
        assert result.indexed_count == 20
        assert result.duration_seconds == pytest.approx(42.5)

    async def test_list_with_status_filter(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        repo = PgResearchSessionRepository(session_factory)

        # Create two sessions with known status
        s1 = await _seed_session(session_factory, topic.id)
        s2 = await _seed_session(session_factory, topic.id)

        # Update s2 to a unique status for isolation
        unique_status = f"test_{uuid4().hex[:8]}"
        await repo.update(s2.model_copy(update={"status": unique_status}))

        sessions, total = await repo.list(status=unique_status, page=1, size=10)
        ids = [s.id for s in sessions]

        assert s2.id in ids
        assert s1.id not in ids
        assert total >= 1

    async def test_list_without_filter(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repo = PgResearchSessionRepository(session_factory)
        sessions, total = await repo.list(status=None, page=1, size=5)
        assert isinstance(sessions, list)
        assert total >= len(sessions)

    async def test_get_returns_none_for_missing(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repo = PgResearchSessionRepository(session_factory)
        assert await repo.get(uuid4()) is None

    async def test_update_agent_plan_jsonb(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgResearchSessionRepository(session_factory)

        plan = {"facets": ["security", "vulnerabilities"], "depth": 3}
        updated = session.model_copy(update={"agent_plan": plan})
        result = await repo.update(updated)

        assert result.agent_plan == plan


# ---------------------------------------------------------------------------
# TestPgAgentStepRepository
# ---------------------------------------------------------------------------


class TestPgAgentStepRepository:
    async def test_create_and_list_by_session(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgAgentStepRepository(session_factory)

        step = AgentStep(
            id=uuid4(),
            session_id=session.id,
            step_name="plan_research",
            status="complete",
            input_data={"topic": "AI security"},
            output_data={"facets": ["vuln", "patches"]},
            duration_ms=1234,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        created = await repo.create(step)

        assert created.id == step.id
        assert created.step_name == "plan_research"
        assert created.status == "complete"
        assert created.duration_ms == 1234

        steps = await repo.list_by_session(session.id)
        step_ids = [s.id for s in steps]
        assert step.id in step_ids

    async def test_list_by_session_returns_empty_for_unknown(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repo = PgAgentStepRepository(session_factory)
        steps = await repo.list_by_session(uuid4())
        assert steps == []

    async def test_multiple_steps_same_session(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgAgentStepRepository(session_factory)

        step_names = ["plan_research", "web_search", "index_findings"]
        for name in step_names:
            await repo.create(
                AgentStep(
                    id=uuid4(),
                    session_id=session.id,
                    step_name=name,
                    status="complete",
                    started_at=datetime.now(UTC),
                )
            )

        steps = await repo.list_by_session(session.id)
        returned_names = {s.step_name for s in steps}
        assert set(step_names).issubset(returned_names)

    async def test_input_output_jsonb_roundtrip(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgAgentStepRepository(session_factory)

        input_data = {"query": "CVE-2024", "depth": 2, "flags": [True, False]}
        output_data = {"results": [{"url": "http://example.com", "score": 0.9}]}

        step = AgentStep(
            id=uuid4(),
            session_id=session.id,
            step_name="web_search",
            status="complete",
            input_data=input_data,
            output_data=output_data,
            started_at=datetime.now(UTC),
        )
        created = await repo.create(step)

        assert created.input_data == input_data
        assert created.output_data == output_data


# ---------------------------------------------------------------------------
# TestPgArticleDraftRepository
# ---------------------------------------------------------------------------


class TestPgArticleDraftRepository:
    async def test_create_and_get(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleDraftRepository(session_factory)

        draft = ArticleDraft(
            id=uuid4(),
            session_id=session.id,
            topic_id=topic.id,
            status=DraftStatus.OUTLINE_GENERATING,
            created_at=datetime.now(UTC),
        )
        created = await repo.create(draft)

        assert created.id == draft.id
        assert created.status == DraftStatus.OUTLINE_GENERATING
        assert created.session_id == session.id
        assert created.topic_id == topic.id

        result = await repo.get(draft.id)
        assert result is not None
        assert result.id == draft.id

    async def test_update_status(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleDraftRepository(session_factory)

        draft = ArticleDraft(
            id=uuid4(),
            session_id=session.id,
            topic_id=topic.id,
            status=DraftStatus.OUTLINE_GENERATING,
            created_at=datetime.now(UTC),
        )
        await repo.create(draft)

        updated = draft.model_copy(update={"status": DraftStatus.DRAFT_COMPLETE})
        result = await repo.update(updated)

        assert result.status == DraftStatus.DRAFT_COMPLETE

    async def test_global_citations_jsonb_roundtrip(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleDraftRepository(session_factory)

        draft = ArticleDraft(
            id=uuid4(),
            session_id=session.id,
            topic_id=topic.id,
            status=DraftStatus.OUTLINE_GENERATING,
            created_at=datetime.now(UTC),
        )
        await repo.create(draft)

        global_citations = [
            {
                "index": 1,
                "source_url": "https://example.com/article1",
                "source_title": "CVE Database Entry",
                "author": "NIST",
                "published_at": "2024-01-15T00:00:00",
            },
            {
                "index": 2,
                "source_url": "https://example.com/article2",
                "source_title": "Security Advisory",
                "author": None,
                "published_at": None,
            },
        ]
        updated = draft.model_copy(
            update={
                "status": DraftStatus.DRAFT_COMPLETE,
                "global_citations": global_citations,
                "total_word_count": 1800,
            }
        )
        result = await repo.update(updated)

        assert result.global_citations == global_citations
        assert result.total_word_count == 1800

    async def test_get_returns_none_for_missing(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repo = PgArticleDraftRepository(session_factory)
        assert await repo.get(uuid4()) is None


# ---------------------------------------------------------------------------
# TestPgArticleRepository
# ---------------------------------------------------------------------------


def _make_canonical_article(session_id: object) -> CanonicalArticle:
    """Build a fully-populated CanonicalArticle for testing."""
    from uuid import UUID

    seo = SEOMetadata(
        title="AI Security Threats in 2024",
        description="A comprehensive analysis of emerging AI security threats.",
        keywords=["AI security", "cybersecurity", "2024 threats"],
        canonical_url="https://cognify.app/articles/ai-security-2024",
        structured_data=StructuredDataLD(
            headline="AI Security Threats in 2024",
            description="A comprehensive analysis of emerging AI security threats.",
            keywords=["AI security", "cybersecurity"],
            **{
                "datePublished": "2024-03-01T00:00:00Z",
                "dateModified": "2024-03-01T00:00:00Z",
            },
        ),
    )
    citations = [
        Citation(
            index=i,
            title=f"Source {i}",
            url=f"https://example.com/source-{i}",
            authors=["Author A", "Author B"],
            published_at=datetime(2024, 1, i, tzinfo=UTC),
        )
        for i in range(1, 6)
    ]
    visuals = [
        ImageAsset(
            id=uuid4(),
            url="https://cdn.cognify.app/charts/threats-bar.png",
            caption="Threat distribution by category",
            alt_text="Bar chart showing threat categories",
            metadata={"width": 1024, "height": 768, "format": "png"},
        )
    ]
    provenance = Provenance(
        research_session_id=UUID(str(session_id)),
        primary_model="claude-opus-4-5",
        drafting_model="claude-sonnet-4-5",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="1.0.0",
    )
    return CanonicalArticle(
        id=uuid4(),
        title="AI Security Threats in 2024",
        subtitle="A deep dive into emerging attack vectors",
        body_markdown="## Introduction\n\nThis article covers AI security threats [1].\n\n## Key Findings\n\nThreats are increasing [2].\n",
        summary="An analysis of AI security threats in 2024 covering key attack vectors.",
        key_claims=[
            "AI-based attacks increased 40% in 2024",
            "LLM prompt injection is a top 5 threat",
            "Supply chain attacks target AI model weights",
        ],
        content_type=ContentType.ANALYSIS,
        seo=seo,
        citations=citations,
        visuals=visuals,
        authors=["Cognify AI", "Editorial Team"],
        domain="cybersecurity",
        generated_at=datetime.now(UTC),
        provenance=provenance,
        ai_generated=True,
    )


class TestPgArticleRepository:
    async def test_create_and_get(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleRepository(session_factory)

        article = _make_canonical_article(session.id)
        created = await repo.create(article)

        assert created.id == article.id
        assert created.title == article.title
        assert created.subtitle == article.subtitle
        assert created.domain == article.domain
        assert created.ai_generated is True
        assert created.content_type == ContentType.ANALYSIS

        result = await repo.get(article.id)
        assert result is not None
        assert result.id == article.id

    async def test_seo_jsonb_roundtrip(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleRepository(session_factory)

        article = _make_canonical_article(session.id)
        await repo.create(article)

        result = await repo.get(article.id)
        assert result is not None
        assert result.seo.title == article.seo.title
        assert result.seo.description == article.seo.description
        assert result.seo.keywords == article.seo.keywords
        assert result.seo.canonical_url == article.seo.canonical_url

    async def test_citations_jsonb_roundtrip(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleRepository(session_factory)

        article = _make_canonical_article(session.id)
        await repo.create(article)

        result = await repo.get(article.id)
        assert result is not None
        assert len(result.citations) == 5
        for original, fetched in zip(article.citations, result.citations, strict=True):
            assert fetched.index == original.index
            assert fetched.title == original.title
            assert fetched.url == original.url
            assert fetched.authors == original.authors

    async def test_visuals_jsonb_roundtrip(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleRepository(session_factory)

        article = _make_canonical_article(session.id)
        await repo.create(article)

        result = await repo.get(article.id)
        assert result is not None
        assert len(result.visuals) == 1
        v = result.visuals[0]
        assert v.url == article.visuals[0].url
        assert v.caption == article.visuals[0].caption
        assert v.alt_text == article.visuals[0].alt_text

    async def test_provenance_jsonb_roundtrip(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleRepository(session_factory)

        article = _make_canonical_article(session.id)
        await repo.create(article)

        result = await repo.get(article.id)
        assert result is not None
        p = result.provenance
        assert p.primary_model == article.provenance.primary_model
        assert p.drafting_model == article.provenance.drafting_model
        assert p.embedding_model == article.provenance.embedding_model
        assert p.research_session_id == article.provenance.research_session_id

    async def test_key_claims_roundtrip(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleRepository(session_factory)

        article = _make_canonical_article(session.id)
        await repo.create(article)

        result = await repo.get(article.id)
        assert result is not None
        assert list(result.key_claims) == list(article.key_claims)

    async def test_authors_roundtrip(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleRepository(session_factory)

        article = _make_canonical_article(session.id)
        await repo.create(article)

        result = await repo.get(article.id)
        assert result is not None
        assert list(result.authors) == list(article.authors)

    async def test_get_returns_none_for_missing(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repo = PgArticleRepository(session_factory)
        assert await repo.get(uuid4()) is None
