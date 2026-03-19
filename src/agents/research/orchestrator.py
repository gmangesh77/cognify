"""LangGraph StateGraph wiring for the research orchestrator.

Contains only the build_graph() factory — no business logic.
Node functions delegate to planner.py, evaluator.py, and the dispatcher.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol as TypingProtocol

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
    ResearchPlan,
    TopicInput,
)
from src.services.task_dispatch import AgentFunction, TaskDispatcher

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
class IndexingDeps:
    """Bundles indexing dependencies to respect 3-param limit."""

    vector_store: VectorStore
    embedder: Embedder
    chunker: ChunkService


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
    indexing_deps: IndexingDeps | None = None,
) -> CompiledStateGraph:  # type: ignore[type-arg]
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

    async def index_findings(state: ResearchState) -> dict:  # type: ignore[type-arg]
        if indexing_deps is None:
            logger.info("index_findings_skipped", reason="services not configured")
            return {}
        try:
            new_count = await _index_new_findings(state, indexing_deps)
            indexed = state.get("indexed_count", 0)
            return {"indexed_count": indexed + new_count}
        except Exception as exc:
            logger.error("index_findings_failed", error=str(exc))
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


async def _index_new_findings(state: ResearchState, deps: IndexingDeps) -> int:
    """Index only un-indexed findings into Milvus.

    Returns count of NEW findings processed.
    """
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
