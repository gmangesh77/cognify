"""Tests for the LLM-based research planner."""

import json
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.planner import generate_research_plan
from src.models.research import ResearchPlan, TopicInput


def _make_topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="AI Security Trends in 2026",
        description="Emerging threats and defenses in AI systems",
        domain="cybersecurity",
    )


def _plan_json(num_facets: int = 3) -> str:
    facets = [
        {
            "index": i,
            "title": f"Facet {i}",
            "description": f"Description {i}",
            "search_queries": [f"query {i}a", f"query {i}b"],
        }
        for i in range(num_facets)
    ]
    return json.dumps({"facets": facets, "reasoning": "Test reasoning"})


class TestGenerateResearchPlan:
    async def test_returns_plan_with_facets(self) -> None:
        llm = FakeListChatModel(responses=[_plan_json(3)])
        plan = await generate_research_plan(_make_topic(), llm)
        assert isinstance(plan, ResearchPlan)
        assert len(plan.facets) == 3
        assert plan.reasoning == "Test reasoning"

    async def test_each_facet_has_required_fields(self) -> None:
        llm = FakeListChatModel(responses=[_plan_json(4)])
        plan = await generate_research_plan(_make_topic(), llm)
        for facet in plan.facets:
            assert facet.title != ""
            assert facet.description != ""
            assert len(facet.search_queries) >= 1

    async def test_handles_malformed_json(self) -> None:
        llm = FakeListChatModel(responses=["not valid json", _plan_json(3)])
        plan = await generate_research_plan(_make_topic(), llm)
        # Should retry once and succeed on second response
        assert isinstance(plan, ResearchPlan)

    async def test_raises_on_repeated_malformed_json(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_research_plan(_make_topic(), llm)
