"""LangGraph StateGraph wiring for the research orchestrator.

Contains only the build_graph() factory — no business logic.
Node functions delegate to planner.py, evaluator.py, and the dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from typing import Protocol as TypingProtocol
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.research.evaluator import EvaluationContext, evaluate_completeness
from src.agents.research.planner import generate_research_plan
from src.agents.research.state import ResearchState
from src.models.research import (
    ChunkMetadata,
    DocumentChunk,
    EvaluationResult,
    FacetFindings,
    FacetTask,
    ResearchFacet,
    ResearchPlan,
    TopicInput,
)
from src.models.research_db import AgentStep as AgentStepModel
from src.services.task_dispatch import AgentFunction, TaskDispatcher

if TYPE_CHECKING:
    from src.services.research import AgentStepRepository

logger = structlog.get_logger()


class ChunkService(TypingProtocol):
    """Protocol for chunking text into document chunks."""

    def chunk(self, text: str, metadata: ChunkMetadata) -> list[DocumentChunk]: ...


class VectorStore(TypingProtocol):
    """Protocol for vector storage operations."""

    async def insert_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int: ...


class Embedder(TypingProtocol):
    """Protocol for text embedding."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class GraphDeps:
    """Bundles optional graph dependencies to respect 3-param limit."""

    vector_store: VectorStore | None = None
    embedder: Embedder | None = None
    chunker: ChunkService | None = None
    step_repo: AgentStepRepository | None = field(default=None)

    @property
    def has_indexing(self) -> bool:
        return all([self.vector_store, self.embedder, self.chunker])


# Keep backward-compatible alias
IndexingDeps = GraphDeps


async def _record_step(
    step_repo: AgentStepRepository | None,
    session_id: UUID,
    step_name: str,
) -> AgentStepModel | None:
    """Create a step record. Returns None if step_repo not configured."""
    if step_repo is None:
        return None
    try:
        step = AgentStepModel(
            session_id=session_id,
            step_name=step_name,
            status="running",
            started_at=datetime.now(UTC),
        )
        return await step_repo.create(step)
    except Exception as exc:
        logger.warning("step_record_failed", step_name=step_name, error=str(exc))
        return None


async def _complete_step(
    step_repo: AgentStepRepository | None,
    step: AgentStepModel | None,
    output_data: dict[str, object],
    status: str = "complete",
) -> None:
    """Update a step to complete/failed."""
    if step_repo is None or step is None:
        return
    try:
        completed_at = datetime.now(UTC)
        duration_ms = int((completed_at - step.started_at).total_seconds() * 1000)
        updated = step.model_copy(
            update={
                "status": status,
                "output_data": output_data,
                "duration_ms": duration_ms,
                "completed_at": completed_at,
            }
        )
        await step_repo.update(updated)
    except Exception as exc:
        logger.warning("step_complete_failed", step_name=step.step_name, error=str(exc))


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


async def _route_and_dispatch(
    facets: list[ResearchFacet],
    dispatcher: TaskDispatcher,
    agent_fn: AgentFunction,
    literature_agent_fn: AgentFunction | None,
) -> list[FacetFindings]:
    """Split facets by source_type, dispatch to correct agents."""
    web_facets = [f for f in facets if f.source_type in ("web", "both")]
    academic_facets = [f for f in facets if f.source_type in ("academic", "both")]

    results: list[FacetFindings] = []
    if web_facets:
        results.extend(await dispatcher.dispatch(web_facets, agent_fn))
    if academic_facets and literature_agent_fn is not None:
        results.extend(await dispatcher.dispatch(academic_facets, literature_agent_fn))
    elif academic_facets:
        results.extend(await dispatcher.dispatch(academic_facets, agent_fn))
    return results


def build_graph(
    llm: BaseChatModel,
    dispatcher: TaskDispatcher,
    agent_fn: AgentFunction,
    literature_agent_fn: AgentFunction | None = None,
    deps: GraphDeps | None = None,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    """Build and compile the research orchestrator graph."""
    step_repo = deps.step_repo if deps else None
    has_indexing = deps.has_indexing if deps else False

    graph = StateGraph(ResearchState)

    async def plan_research(state: ResearchState) -> dict:  # type: ignore[type-arg]
        step = await _record_step(step_repo, state["session_id"], "plan_research")
        try:
            topic = _validate_topic(state)
            plan = await generate_research_plan(topic, llm)
            await _complete_step(
                step_repo,
                step,
                {
                    "facet_count": len(plan.facets),
                    "facet_titles": [f.title for f in plan.facets],
                },
            )
            return {"research_plan": plan, "status": "planning"}
        except Exception as exc:
            await _complete_step(step_repo, step, {"error": str(exc)}, status="failed")
            raise

    async def dispatch_agents(state: ResearchState) -> dict:  # type: ignore[type-arg]
        plan = _validate_plan(state)
        evaluation = _validate_evaluation(state)
        if evaluation and evaluation.weak_facets:
            weak = set(evaluation.weak_facets)
            facets = [f for f in plan.facets if f.index in weak]
        else:
            facets = list(plan.facets)

        round_num = state["round_number"] + 1

        # Record all facet steps as "running" BEFORE batch dispatch
        facet_steps: list[AgentStepModel | None] = []
        for facet in facets:
            step_name = f"research_facet_{facet.index}"
            if round_num > 1:
                step_name = f"research_facet_{facet.index}_round_{round_num}"
            step = await _record_step(step_repo, state["session_id"], step_name)
            facet_steps.append(step)

        # Use route_and_dispatch for web/academic facet routing
        results = await _route_and_dispatch(
            facets, dispatcher, agent_fn, literature_agent_fn
        )

        # Complete each facet step — match results by facet_index
        # (results may differ in count from facets due to routing)
        results_by_index: dict[int, list[FacetFindings]] = {}
        for r in results:
            results_by_index.setdefault(r.facet_index, []).append(r)
        for step, facet in zip(facet_steps, facets, strict=True):
            facet_results = results_by_index.get(facet.index, [])
            total_sources = sum(len(r.sources) for r in facet_results)
            total_claims = sum(len(r.claims) for r in facet_results)
            await _complete_step(
                step_repo,
                step,
                {
                    "sources_found": total_sources,
                    "claims_extracted": total_claims,
                    "facet_title": facet.title,
                },
            )

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
            "round_number": round_num,
            "status": "researching",
        }

    async def evaluate(state: ResearchState) -> dict:  # type: ignore[type-arg]
        step = await _record_step(
            step_repo, state["session_id"], "evaluate_completeness"
        )
        try:
            topic = _validate_topic(state)
            findings = _validate_findings(state)
            ctx = EvaluationContext(
                topic=topic, findings=findings, round_number=state["round_number"]
            )
            result = await evaluate_completeness(ctx, llm)
            await _complete_step(
                step_repo,
                step,
                {
                    "is_complete": result.is_complete,
                    "weak_facets": result.weak_facets,
                    "reasoning": result.reasoning,
                },
            )
            return {"evaluation": result, "status": "evaluating"}
        except Exception as exc:
            await _complete_step(step_repo, step, {"error": str(exc)}, status="failed")
            raise

    def should_retry(state: ResearchState) -> str:
        evaluation = _validate_evaluation(state)
        if evaluation and not evaluation.is_complete and state["round_number"] < 2:
            return "retry"
        return "finalize"

    async def finalize(state: ResearchState) -> dict:  # type: ignore[type-arg]
        findings = _validate_findings(state)
        total_sources = sum(len(f.sources) for f in findings)
        step = await _record_step(step_repo, state["session_id"], "finalize")
        await _complete_step(
            step_repo,
            step,
            {
                "total_sources": total_sources,
            },
        )
        return {"status": "complete"}

    async def index_findings(state: ResearchState) -> dict:  # type: ignore[type-arg]
        step = await _record_step(step_repo, state["session_id"], "index_findings")
        try:
            if not has_indexing or deps is None:
                logger.info("index_findings_skipped", reason="services not configured")
                await _complete_step(step_repo, step, {"embeddings_created": 0})
                return {}
            new_count = await _index_new_findings(state, deps)
            indexed = state.get("indexed_count", 0)
            await _complete_step(step_repo, step, {"embeddings_created": new_count})
            return {"indexed_count": indexed + new_count}
        except Exception as exc:
            logger.error("index_findings_failed", error=str(exc))
            await _complete_step(step_repo, step, {"error": str(exc)}, status="failed")
            return {}

    graph.add_node("plan_research", plan_research)
    graph.add_node("dispatch_agents", dispatch_agents)
    graph.add_node("index_findings", index_findings)
    graph.add_node("evaluate_completeness", evaluate)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("plan_research")
    graph.add_edge("plan_research", "dispatch_agents")
    graph.add_edge("dispatch_agents", "index_findings")
    graph.add_edge("index_findings", "evaluate_completeness")
    graph.add_conditional_edges(
        "evaluate_completeness",
        should_retry,
        {"retry": "dispatch_agents", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()


async def _index_new_findings(state: ResearchState, deps: GraphDeps) -> int:
    """Index only un-indexed findings into Milvus.

    Returns count of NEW findings processed.
    """
    if not deps.has_indexing:
        return 0
    assert deps.vector_store is not None
    assert deps.embedder is not None
    assert deps.chunker is not None
    findings = _validate_findings(state)
    indexed_count = state.get("indexed_count", 0)
    new_findings = findings[indexed_count:]
    if not new_findings:
        return 0
    all_chunks = _chunk_findings(new_findings, state, deps.chunker)
    if not all_chunks:
        return 0
    texts = [c.text for c in all_chunks]
    embeddings = deps.embedder.embed(texts)
    await deps.vector_store.insert_chunks(all_chunks, embeddings)
    logger.info("findings_indexed", chunk_count=len(all_chunks))
    return len(new_findings)


def _chunk_findings(
    findings: list[FacetFindings],
    state: ResearchState,
    chunker: ChunkService,
) -> list[DocumentChunk]:
    """Chunk all source snippets from findings."""
    topic = _validate_topic(state)
    session_id = str(state["session_id"])
    all_chunks: list[DocumentChunk] = []
    for finding in findings:
        for source in finding.sources:
            metadata = ChunkMetadata(
                source_url=source.url,
                source_title=source.title,
                topic_id=str(topic.id),
                session_id=session_id,
                published_at=(
                    source.published_at.isoformat() if source.published_at else None
                ),
                author=source.author,
            )
            all_chunks.extend(chunker.chunk(source.snippet, metadata))
    return all_chunks
