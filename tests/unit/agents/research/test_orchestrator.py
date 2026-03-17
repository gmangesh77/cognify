"""Tests for the LangGraph research orchestrator.

Uses FakeLLM for deterministic plan/evaluate responses and
stub agents for dispatch. Tests graph topology and state transitions.
"""

import json
from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.orchestrator import build_graph
from src.agents.research.runner import LangGraphResearchOrchestrator
from src.agents.research.stub import stub_research_agent
from src.models.research import TopicInput
from src.services.task_dispatch import AsyncIODispatcher


def _make_topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="AI Security Trends",
        description="Emerging threats",
        domain="cybersecurity",
    )


def _plan_json(num_facets: int = 3) -> str:
    facets = [
        {
            "index": i,
            "title": f"Facet {i}",
            "description": f"Desc {i}",
            "search_queries": [f"q{i}"],
        }
        for i in range(num_facets)
    ]
    return json.dumps({"facets": facets, "reasoning": "Plan reasoning"})


def _eval_json(is_complete: bool, weak: list[int] | None = None) -> str:
    return json.dumps(
        {
            "is_complete": is_complete,
            "weak_facets": weak or [],
            "reasoning": "Eval reasoning",
        }
    )


class TestOrchestrator:
    def _initial_state(self) -> dict:
        return {
            "topic": _make_topic(),
            "research_plan": None,
            "dispatched_tasks": [],
            "findings": [],
            "evaluation": None,
            "round_number": 0,
            "session_id": uuid4(),
            "status": "initial",
            "error": None,
        }

    async def test_happy_path_completes(self) -> None:
        """Topic -> plan -> dispatch -> evaluate (complete) -> finalize."""
        llm = FakeListChatModel(responses=[_plan_json(3), _eval_json(True)])
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent)
        result = await graph.ainvoke(self._initial_state())
        assert result["status"] == "complete"
        assert len(result["findings"]) == 3
        assert result["round_number"] == 1

    async def test_retry_path(self) -> None:
        """Evaluate incomplete -> retry weak facets -> complete."""
        llm = FakeListChatModel(
            responses=[
                _plan_json(3),
                _eval_json(False, [1]),  # Round 1: facet 1 weak
                _eval_json(True),  # Round 2: complete
            ]
        )
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent)
        result = await graph.ainvoke(self._initial_state())
        assert result["status"] == "complete"
        # Round 1: 3 facets + Round 2: 1 weak facet retried = 4
        assert len(result["findings"]) == 4
        assert result["round_number"] == 2

    async def test_max_rounds_stops_at_two(self) -> None:
        """Guardrail: stops at round 2 even if LLM says incomplete."""
        llm = FakeListChatModel(
            responses=[
                _plan_json(3),
                _eval_json(False, [0, 1, 2]),  # Round 1: all weak
                _eval_json(False, [0, 1, 2]),  # Round 2: guardrail forces complete
            ]
        )
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent)
        result = await graph.ainvoke(self._initial_state())
        assert result["status"] == "complete"
        assert result["round_number"] == 2


class TestRunner:
    async def test_runner_delegates_to_graph(self) -> None:
        """Runner wraps graph and returns final state."""
        llm = FakeListChatModel(responses=[_plan_json(3), _eval_json(True)])
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent)
        runner = LangGraphResearchOrchestrator(graph)
        session_id = uuid4()
        result = await runner.run(session_id, _make_topic())
        assert result["status"] == "complete"
        assert len(result["findings"]) == 3
