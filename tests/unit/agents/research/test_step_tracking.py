"""Tests for agent step tracking during orchestrator execution."""

from datetime import UTC, datetime
from uuid import uuid4

from src.models.research import (
    FacetFindings,
    SourceDocument,
    TopicInput,
)
from src.services.research import InMemoryAgentStepRepository


class FakeStepTrackingLLM:
    """Minimal LLM double that returns pre-canned research responses."""

    async def ainvoke(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        from unittest.mock import MagicMock

        resp = MagicMock()
        resp.content = (
            '{"facets": ['
            '{"index": 0, "title": "Facet A", "description": "desc", '
            '"search_queries": ["q1"]}, '
            '{"index": 1, "title": "Facet B", "description": "desc", '
            '"search_queries": ["q2"]}'
            '], "reasoning": "test"}'
        )
        return resp


class FakeDispatcher:
    """Returns pre-canned findings."""

    async def dispatch(self, facets, agent_fn):  # type: ignore[no-untyped-def]
        now = datetime.now(UTC)
        return [
            FacetFindings(
                facet_index=f.index,
                sources=[
                    SourceDocument(
                        url=f"https://example.com/{f.index}",
                        title=f"Source {f.index}",
                        snippet="Test snippet",
                        retrieved_at=now,
                    )
                ],
                claims=[f"Claim for facet {f.index}"],
                summary=f"Summary for facet {f.index}",
            )
            for f in facets
        ]


class FakeEvalLLM:
    """LLM that returns plan on first call, complete evaluation on second."""

    def __init__(self) -> None:
        self.call_count = 0

    async def ainvoke(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        from unittest.mock import MagicMock

        self.call_count += 1
        if self.call_count == 1:
            resp = MagicMock()
            resp.content = (
                '{"facets": ['
                '{"index": 0, "title": "Facet A", '
                '"description": "desc", "search_queries": ["q1"]}'
                '], "reasoning": "test"}'
            )
            return resp
        resp = MagicMock()
        resp.content = '{"is_complete": true, "weak_facets": [], "reasoning": "good"}'
        return resp


class TestStepTracking:
    async def test_baseline_empty_step_repo(self) -> None:
        step_repo = InMemoryAgentStepRepository()
        session_id = uuid4()
        steps = await step_repo.list_by_session(session_id)
        assert len(steps) == 0


class TestStepTrackingIntegration:
    async def test_full_graph_records_all_steps(self) -> None:
        """Run the full graph with fakes and verify steps are recorded."""
        from src.agents.research.orchestrator import GraphDeps, build_graph
        from src.agents.research.runner import LangGraphResearchOrchestrator

        step_repo = InMemoryAgentStepRepository()
        session_id = uuid4()

        llm = FakeEvalLLM()
        dispatcher = FakeDispatcher()

        async def fake_agent(facet):  # type: ignore[no-untyped-def]
            return FacetFindings(
                facet_index=facet.index,
                sources=[
                    SourceDocument(
                        url="https://x.com",
                        title="T",
                        snippet="S",
                        retrieved_at=datetime.now(UTC),
                    )
                ],
                claims=["claim"],
                summary="summary",
            )

        graph = build_graph(
            llm=llm,
            dispatcher=dispatcher,
            agent_fn=fake_agent,
            deps=GraphDeps(step_repo=step_repo),
        )
        orchestrator = LangGraphResearchOrchestrator(graph, step_repo=step_repo)

        topic = TopicInput(id=uuid4(), title="Test", description="Desc", domain="tech")
        await orchestrator.run(session_id, topic)

        steps = await step_repo.list_by_session(session_id)
        step_names = [s.step_name for s in steps]

        # Should have: plan_research, research_facet_0, index_findings,
        # evaluate_completeness, finalize
        assert "plan_research" in step_names
        assert "index_findings" in step_names
        assert "evaluate_completeness" in step_names
        assert "finalize" in step_names
        assert any(name.startswith("research_facet_") for name in step_names)

        # All steps should be complete
        for step in steps:
            assert step.status == "complete", (
                f"{step.step_name} has status {step.status}"
            )
            assert step.duration_ms is not None
            assert step.duration_ms >= 0

    async def test_step_tracking_optional(self) -> None:
        """Graph works without step_repo (backward compatibility)."""
        from src.agents.research.orchestrator import build_graph
        from src.agents.research.runner import LangGraphResearchOrchestrator

        llm = FakeEvalLLM()
        dispatcher = FakeDispatcher()

        async def fake_agent(facet):  # type: ignore[no-untyped-def]
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="",
            )

        graph = build_graph(llm=llm, dispatcher=dispatcher, agent_fn=fake_agent)
        orchestrator = LangGraphResearchOrchestrator(graph)
        topic = TopicInput(id=uuid4(), title="Test", description="Desc", domain="tech")
        result = await orchestrator.run(uuid4(), topic)
        assert result["status"] == "complete"
