"""ResearchOrchestrator protocol and LangGraph implementation.

The runner wraps the compiled graph and manages session lifecycle.
The service layer depends on the protocol, not the concrete class.
"""

from typing import Protocol
from uuid import UUID

from langgraph.graph.state import CompiledStateGraph

from src.agents.research.state import ResearchState
from src.models.research import TopicInput


class ResearchOrchestrator(Protocol):
    """Protocol for running research orchestration."""

    async def run(self, session_id: UUID, topic: TopicInput) -> ResearchState: ...


class LangGraphResearchOrchestrator:
    """Runs the compiled LangGraph research graph."""

    def __init__(self, compiled_graph: CompiledStateGraph) -> None:
        self._graph = compiled_graph

    async def run(self, session_id: UUID, topic: TopicInput) -> ResearchState:
        initial_state: ResearchState = {
            "topic": topic,
            "research_plan": None,
            "dispatched_tasks": [],
            "findings": [],
            "evaluation": None,
            "round_number": 0,
            "session_id": session_id,
            "status": "initial",
            "error": None,
        }
        result = await self._graph.ainvoke(initial_state)
        return result  # type: ignore[return-value]
