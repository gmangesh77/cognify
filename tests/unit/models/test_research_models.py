"""Tests for research pipeline Pydantic models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.research import (
    EvaluationResult,
    FacetFindings,
    FacetTask,
    ResearchFacet,
    ResearchPlan,
    SourceDocument,
    TopicInput,
)


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


from src.models.research_db import AgentStep, ResearchSession


class TestResearchSession:
    def test_construct_with_defaults(self) -> None:
        session = ResearchSession(
            topic_id=uuid4(), started_at=datetime.now(UTC)
        )
        assert session.status == "planning"
        assert session.round_count == 0
        assert session.completed_at is None

    def test_model_copy_update(self) -> None:
        session = ResearchSession(
            topic_id=uuid4(), started_at=datetime.now(UTC)
        )
        updated = session.model_copy(update={"status": "complete"})
        assert updated.status == "complete"
        assert session.status == "planning"  # original unchanged


class TestAgentStep:
    def test_construct_with_defaults(self) -> None:
        step = AgentStep(
            session_id=uuid4(),
            step_name="plan_research",
            started_at=datetime.now(UTC),
        )
        assert step.status == "running"
        assert step.duration_ms is None
