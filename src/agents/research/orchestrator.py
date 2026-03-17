"""LangGraph StateGraph wiring for the research orchestrator.

Contains only the build_graph() factory — no business logic.
Node functions delegate to planner.py, evaluator.py, and the dispatcher.
"""

from datetime import UTC, datetime

import structlog
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.research.evaluator import EvaluationContext, evaluate_completeness
from src.agents.research.planner import generate_research_plan
from src.agents.research.state import ResearchState
from src.models.research import (
    EvaluationResult,
    FacetFindings,
    FacetTask,
    ResearchPlan,
    TopicInput,
)
from src.services.task_dispatch import AgentFunction, TaskDispatcher

logger = structlog.get_logger()


def _validate_topic(state: ResearchState) -> TopicInput:
    raw = state["topic"]
    return raw if isinstance(raw, TopicInput) else TopicInput.model_validate(raw)


def _validate_plan(state: ResearchState) -> ResearchPlan:
    raw = state["research_plan"]
    return raw if isinstance(raw, ResearchPlan) else ResearchPlan.model_validate(raw)


def _validate_evaluation(state: ResearchState) -> EvaluationResult | None:
    raw = state.get("evaluation")
    if raw is None:
        return None
    if isinstance(raw, EvaluationResult):
        return raw
    return EvaluationResult.model_validate(raw)


def _validate_findings(state: ResearchState) -> list[FacetFindings]:
    return [
        f if isinstance(f, FacetFindings) else FacetFindings.model_validate(f)
        for f in state["findings"]
    ]


def build_graph(
    llm: BaseChatModel,
    dispatcher: TaskDispatcher,
    agent_fn: AgentFunction,
) -> CompiledStateGraph:
    """Build and compile the research orchestrator graph."""
    graph = StateGraph(ResearchState)

    async def plan_research(state: ResearchState) -> dict:  # type: ignore[type-arg]
        topic = _validate_topic(state)
        plan = await generate_research_plan(topic, llm)
        return {"research_plan": plan, "status": "planning"}

    async def dispatch_agents(state: ResearchState) -> dict:  # type: ignore[type-arg]
        plan = _validate_plan(state)
        evaluation = _validate_evaluation(state)
        if evaluation and evaluation.weak_facets:
            weak = set(evaluation.weak_facets)
            facets = [f for f in plan.facets if f.index in weak]
        else:
            facets = list(plan.facets)

        results = await dispatcher.dispatch(facets, agent_fn)

        now = datetime.now(UTC)
        tasks = [
            FacetTask(
                facet_index=f.index,
                status="completed",
                started_at=now,
                completed_at=now,
            )
            for f in facets
        ]
        return {
            "findings": results,
            "dispatched_tasks": tasks,
            "round_number": state["round_number"] + 1,
            "status": "researching",
        }

    async def evaluate(state: ResearchState) -> dict:  # type: ignore[type-arg]
        topic = _validate_topic(state)
        findings = _validate_findings(state)
        ctx = EvaluationContext(
            topic=topic, findings=findings, round_number=state["round_number"]
        )
        result = await evaluate_completeness(ctx, llm)
        return {"evaluation": result, "status": "evaluating"}

    def should_retry(state: ResearchState) -> str:
        evaluation = _validate_evaluation(state)
        if evaluation and not evaluation.is_complete and state["round_number"] < 2:
            return "retry"
        return "finalize"

    async def finalize(state: ResearchState) -> dict:  # type: ignore[type-arg]
        return {"status": "complete"}

    graph.add_node("plan_research", plan_research)
    graph.add_node("dispatch_agents", dispatch_agents)
    graph.add_node("evaluate_completeness", evaluate)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("plan_research")
    graph.add_edge("plan_research", "dispatch_agents")
    graph.add_edge("dispatch_agents", "evaluate_completeness")
    graph.add_conditional_edges(
        "evaluate_completeness",
        should_retry,
        {"retry": "dispatch_agents", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()
