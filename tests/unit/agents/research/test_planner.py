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


def _plan_json_with_source_types() -> str:
    return json.dumps({
        "facets": [
            {
                "index": 0, "title": "Recent incidents",
                "description": "Current events",
                "search_queries": ["recent incidents 2026"], "source_type": "web",
            },
            {
                "index": 1, "title": "Detection methods",
                "description": "ML approaches",
                "search_queries": ["detection ML"], "source_type": "academic",
            },
            {
                "index": 2, "title": "Mitigation strategies",
                "description": "Both practical and research",
                "search_queries": ["mitigation strategies"], "source_type": "both",
            },
        ],
        "reasoning": "Mixed plan",
    })


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


class TestPlannerSourceType:
    async def test_plan_includes_source_type(self) -> None:
        llm = FakeListChatModel(responses=[_plan_json_with_source_types()])
        plan = await generate_research_plan(_make_topic(), llm)
        assert plan.facets[0].source_type == "web"
        assert plan.facets[1].source_type == "academic"
        assert plan.facets[2].source_type == "both"

    async def test_default_source_type_is_web(self) -> None:
        llm = FakeListChatModel(responses=[_plan_json(3)])
        plan = await generate_research_plan(_make_topic(), llm)
        for facet in plan.facets:
            assert facet.source_type == "web"
