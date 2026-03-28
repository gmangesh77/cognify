"""Tests for research pipeline Pydantic models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.research import (
    ChunkMetadata,
    ChunkResult,
    DocumentChunk,
    EvaluationResult,
    FacetFindings,
    FacetTask,
    KnowledgeBaseStats,
    ResearchFacet,
    ResearchPlan,
    SourceDocument,
    TopicInput,
)
from src.models.research_db import AgentStep, ResearchSession


class TestTopicInput:
    def test_construct_valid(self) -> None:
        topic = TopicInput(
            id=uuid4(),
            title="AI Security Trends",
            description="Emerging threats",
            domain="cybersecurity",
        )
        assert topic.title == "AI Security Trends"

    def test_frozen(self) -> None:
        topic = TopicInput(
            id=uuid4(),
            title="Test",
            description="Desc",
            domain="tech",
        )
        with pytest.raises(ValidationError):
            topic.title = "Changed"  # type: ignore[misc]


class TestResearchFacet:
    def test_construct_valid(self) -> None:
        facet = ResearchFacet(
            index=0,
            title="Recent incidents",
            description="Major security breaches in 2026",
            search_queries=["2026 security breaches", "recent cyber attacks"],
        )
        assert facet.index == 0
        assert len(facet.search_queries) == 2

    def test_empty_queries(self) -> None:
        facet = ResearchFacet(
            index=0,
            title="Test",
            description="Desc",
            search_queries=[],
        )
        assert facet.search_queries == []


class TestResearchPlan:
    def test_construct_with_facets(self) -> None:
        facets = [
            ResearchFacet(
                index=i,
                title=f"Facet {i}",
                description=f"Description {i}",
                search_queries=[f"query {i}"],
            )
            for i in range(3)
        ]
        plan = ResearchPlan(facets=facets, reasoning="Test reasoning")
        assert len(plan.facets) == 3
        assert plan.reasoning == "Test reasoning"


class TestSourceDocument:
    def test_construct_valid(self) -> None:
        doc = SourceDocument(
            url="https://example.com/article",
            title="Test Article",
            snippet="Relevant content...",
            retrieved_at=datetime.now(UTC),
        )
        assert doc.url == "https://example.com/article"


class TestFacetFindings:
    def test_construct_with_sources(self) -> None:
        findings = FacetFindings(
            facet_index=0,
            sources=[
                SourceDocument(
                    url="https://example.com/1",
                    title="Source 1",
                    snippet="Content",
                    retrieved_at=datetime.now(UTC),
                ),
            ],
            claims=["Claim 1"],
            summary="Summary of findings",
        )
        assert len(findings.sources) == 1
        assert findings.facet_index == 0

    def test_empty_sources(self) -> None:
        findings = FacetFindings(
            facet_index=0,
            sources=[],
            claims=[],
            summary="No findings",
        )
        assert findings.sources == []


class TestFacetTask:
    def test_construct_pending(self) -> None:
        task = FacetTask(facet_index=0, status="pending")
        assert task.started_at is None
        assert task.completed_at is None

    def test_frozen(self) -> None:
        task = FacetTask(facet_index=0, status="pending")
        with pytest.raises(ValidationError):
            task.status = "running"  # type: ignore[misc]


class TestEvaluationResult:
    def test_complete(self) -> None:
        result = EvaluationResult(
            is_complete=True,
            weak_facets=[],
            reasoning="All facets covered",
        )
        assert result.is_complete is True
        assert result.weak_facets == []

    def test_incomplete_with_weak_facets(self) -> None:
        result = EvaluationResult(
            is_complete=False,
            weak_facets=[1, 3],
            reasoning="Facets 1 and 3 lack sources",
        )
        assert result.weak_facets == [1, 3]


class TestSerialization:
    def test_topic_input_roundtrip(self) -> None:
        topic = TopicInput(
            id=uuid4(),
            title="Test",
            description="Desc",
            domain="tech",
        )
        data = topic.model_dump()
        restored = TopicInput.model_validate(data)
        assert restored == topic

    def test_research_plan_roundtrip(self) -> None:
        plan = ResearchPlan(
            facets=[
                ResearchFacet(
                    index=0,
                    title="F",
                    description="D",
                    search_queries=["q"],
                ),
            ],
            reasoning="R",
        )
        data = plan.model_dump()
        restored = ResearchPlan.model_validate(data)
        assert restored == plan


class TestResearchSession:
    def test_construct_with_defaults(self) -> None:
        session = ResearchSession(topic_id=uuid4(), started_at=datetime.now(UTC))
        assert session.status == "planning"
        assert session.round_count == 0
        assert session.completed_at is None

    def test_model_copy_update(self) -> None:
        session = ResearchSession(topic_id=uuid4(), started_at=datetime.now(UTC))
        updated = session.model_copy(update={"status": "complete"})
        assert updated.status == "complete"
        assert session.status == "planning"  # original unchanged

    def test_indexed_count_defaults_to_zero(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from src.models.research_db import ResearchSession

        session = ResearchSession(
            topic_id=uuid4(),
            started_at=datetime.now(UTC),
        )
        assert session.indexed_count == 0


class TestAgentStep:
    def test_construct_with_defaults(self) -> None:
        step = AgentStep(
            session_id=uuid4(),
            step_name="plan_research",
            started_at=datetime.now(UTC),
        )
        assert step.status == "running"
        assert step.duration_ms is None


class TestChunkMetadata:
    def test_construct(self) -> None:
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Test",
            topic_id="topic-1",
            session_id="session-1",
        )
        assert meta.source_url == "https://example.com"

    def test_frozen(self) -> None:
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Test",
            topic_id="t",
            session_id="s",
        )
        with pytest.raises(ValidationError):
            meta.source_url = "changed"  # type: ignore[misc]


class TestDocumentChunk:
    def test_construct(self) -> None:
        chunk = DocumentChunk(
            text="Some chunk text",
            source_url="https://example.com",
            source_title="Test",
            topic_id="topic-1",
            session_id="session-1",
            chunk_index=0,
        )
        assert chunk.chunk_index == 0
        assert chunk.text == "Some chunk text"


class TestChunkResult:
    def test_construct(self) -> None:
        result = ChunkResult(
            text="Retrieved chunk",
            source_url="https://example.com",
            source_title="Test",
            score=0.95,
            chunk_index=0,
        )
        assert result.score == 0.95


class TestKnowledgeBaseStats:
    def test_construct_with_topic(self) -> None:
        stats = KnowledgeBaseStats(
            total_chunks=100,
            total_documents=25,
            collection_name="research_chunks",
            topic_id="topic-1",
        )
        assert stats.total_chunks == 100
        assert stats.topic_id == "topic-1"

    def test_construct_without_topic(self) -> None:
        stats = KnowledgeBaseStats(
            total_chunks=100,
            total_documents=25,
            collection_name="research_chunks",
        )
        assert stats.topic_id is None


class TestSourceDocumentMetadata:
    """Tests for published_at and author fields on SourceDocument."""

    def test_defaults_to_none(self) -> None:
        doc = SourceDocument(
            url="https://example.com",
            title="Test",
            snippet="Content",
            retrieved_at=datetime.now(UTC),
        )
        assert doc.published_at is None
        assert doc.author is None

    def test_populated(self) -> None:
        pub = datetime(2026, 3, 15, tzinfo=UTC)
        doc = SourceDocument(
            url="https://example.com",
            title="Test",
            snippet="Content",
            retrieved_at=datetime.now(UTC),
            published_at=pub,
            author="Jane Doe",
        )
        assert doc.published_at == pub
        assert doc.author == "Jane Doe"


class TestChunkMetadataNewFields:
    """Tests for published_at and author fields on ChunkMetadata."""

    def test_defaults_to_none(self) -> None:
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Test",
            topic_id="t",
            session_id="s",
        )
        assert meta.published_at is None
        assert meta.author is None

    def test_populated(self) -> None:
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Test",
            topic_id="t",
            session_id="s",
            published_at="2026-03-15T00:00:00+00:00",
            author="Jane Doe",
        )
        assert meta.published_at == "2026-03-15T00:00:00+00:00"
        assert meta.author == "Jane Doe"


class TestDocumentChunkNewFields:
    """Tests for published_at and author fields on DocumentChunk."""

    def test_defaults_to_none(self) -> None:
        chunk = DocumentChunk(
            text="Some text",
            source_url="https://example.com",
            source_title="Test",
            topic_id="t",
            session_id="s",
            chunk_index=0,
        )
        assert chunk.published_at is None
        assert chunk.author is None

    def test_populated(self) -> None:
        chunk = DocumentChunk(
            text="Some text",
            source_url="https://example.com",
            source_title="Test",
            topic_id="t",
            session_id="s",
            chunk_index=0,
            published_at="2026-03-15T00:00:00+00:00",
            author="Jane Doe",
        )
        assert chunk.published_at == "2026-03-15T00:00:00+00:00"
        assert chunk.author == "Jane Doe"


class TestChunkResultNewFields:
    """Tests for published_at and author fields on ChunkResult."""

    def test_defaults_to_none(self) -> None:
        result = ChunkResult(
            text="Retrieved chunk",
            source_url="https://example.com",
            source_title="Test",
            score=0.95,
            chunk_index=0,
        )
        assert result.published_at is None
        assert result.author is None

    def test_populated(self) -> None:
        pub = datetime(2026, 3, 15, tzinfo=UTC)
        result = ChunkResult(
            text="Retrieved chunk",
            source_url="https://example.com",
            source_title="Test",
            score=0.95,
            chunk_index=0,
            published_at=pub,
            author="Jane Doe",
        )
        assert result.published_at == pub
        assert result.author == "Jane Doe"
