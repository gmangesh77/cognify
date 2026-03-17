"""LangGraph state definition for the research orchestrator."""

import operator
from typing import Annotated, TypedDict
from uuid import UUID

from src.models.research import (
    EvaluationResult,
    FacetFindings,
    FacetTask,
    ResearchPlan,
    TopicInput,
)


class ResearchState(TypedDict):
    """State flowing through the research orchestrator graph.

    Node return semantics: nodes return partial dicts with only changed keys.
    The ``findings`` field uses an additive reducer so that retry rounds
    accumulate rather than replace previous results.
    """

    topic: TopicInput
    research_plan: ResearchPlan | None
    dispatched_tasks: list[FacetTask]
    findings: Annotated[list[FacetFindings], operator.add]
    evaluation: EvaluationResult | None
    round_number: int
    session_id: UUID  # Passed as UUID, LangGraph MemorySaver preserves it
    status: str
    error: str | None
