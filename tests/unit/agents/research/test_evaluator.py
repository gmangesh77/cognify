"""Tests for the LLM-based completeness evaluator."""

import json
from datetime import UTC, datetime

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.evaluator import EvaluationContext, evaluate_completeness
from src.models.research import (
    EvaluationResult,
    FacetFindings,
    SourceDocument,
    TopicInput,
)
from uuid import uuid4


def _make_topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="Test Topic",
        description="Test",
        domain="tech",
    )


def _make_findings(facet_index: int, num_sources: int = 2) -> FacetFindings:
    sources = [
        SourceDocument(
            url=f"https://example.com/{facet_index}/{i}",
            title=f"Source {i}",
            snippet="Content",
            retrieved_at=datetime.now(UTC),
        )
        for i in range(num_sources)
    ]
    return FacetFindings(
        facet_index=facet_index,
        sources=sources,
        claims=["claim"],
        summary="summary",
    )


def _eval_json(is_complete: bool, weak_facets: list[int] | None = None) -> str:
    return json.dumps(
        {
            "is_complete": is_complete,
            "weak_facets": weak_facets or [],
            "reasoning": "Test reasoning",
        }
    )


class TestEvaluateCompleteness:
    async def test_returns_complete(self) -> None:
        llm = FakeListChatModel(responses=[_eval_json(True)])
        findings = [_make_findings(0), _make_findings(1)]
        ctx = EvaluationContext(topic=_make_topic(), findings=findings, round_number=1)
        result = await evaluate_completeness(ctx, llm=llm)
        assert isinstance(result, EvaluationResult)
        assert result.is_complete is True

    async def test_identifies_weak_facets(self) -> None:
        llm = FakeListChatModel(responses=[_eval_json(False, [1])])
        findings = [_make_findings(0), _make_findings(1)]
        ctx = EvaluationContext(topic=_make_topic(), findings=findings, round_number=1)
        result = await evaluate_completeness(ctx, llm=llm)
        assert result.is_complete is False
        assert 1 in result.weak_facets

    async def test_guardrail_forces_complete_at_max_rounds(self) -> None:
        # LLM says incomplete, but round 2 guardrail forces complete
        llm = FakeListChatModel(responses=[_eval_json(False, [0, 1])])
        findings = [_make_findings(0), _make_findings(1)]
        ctx = EvaluationContext(topic=_make_topic(), findings=findings, round_number=2)
        result = await evaluate_completeness(ctx, llm=llm)
        assert result.is_complete is True

    async def test_guardrail_zero_sources_always_weak(self) -> None:
        # Facet 1 has zero sources — should be marked weak
        llm = FakeListChatModel(responses=[_eval_json(True)])
        findings = [
            _make_findings(0, num_sources=2),
            FacetFindings(facet_index=1, sources=[], claims=[], summary=""),
        ]
        ctx = EvaluationContext(topic=_make_topic(), findings=findings, round_number=1)
        result = await evaluate_completeness(ctx, llm=llm)
        # Even though LLM says complete, zero-source guardrail overrides
        assert result.is_complete is False
        assert 1 in result.weak_facets
