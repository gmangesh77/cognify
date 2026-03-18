"""Content pipeline LangGraph StateGraph.

Orchestrates article generation stages. CONTENT-001 adds the
generate_outline node. Future tickets add draft, SEO, and compile nodes.
"""

from typing import TypedDict
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.content.outline_generator import generate_outline
from src.models.content_pipeline import ArticleOutline
from src.models.research import (
    FacetFindings,
    ResearchPlan,
    TopicInput,
)

logger = structlog.get_logger()


class ContentState(TypedDict):
    """State flowing through the content pipeline graph."""

    topic: TopicInput
    research_plan: ResearchPlan | None
    findings: list[FacetFindings]
    session_id: UUID
    outline: ArticleOutline | None
    status: str
    error: str | None


def build_content_graph(llm: BaseChatModel) -> CompiledStateGraph:
    """Build and compile the content pipeline graph."""
    graph = StateGraph(ContentState)

    async def outline_node(state: ContentState) -> dict:  # type: ignore[type-arg]
        topic = state["topic"]
        if not isinstance(topic, TopicInput):
            topic = TopicInput.model_validate(topic)
        findings = [
            f if isinstance(f, FacetFindings) else FacetFindings.model_validate(f)
            for f in state["findings"]
        ]
        try:
            outline = await generate_outline(topic, findings, llm)
            logger.info(
                "outline_generation_complete",
                section_count=len(outline.sections),
                total_words=outline.total_target_words,
            )
            return {"outline": outline, "status": "outline_complete"}
        except Exception as exc:
            logger.error("outline_generation_failed", error=str(exc))
            return {"status": "failed", "error": str(exc)}

    graph.add_node("generate_outline", outline_node)
    graph.set_entry_point("generate_outline")
    graph.add_edge("generate_outline", END)

    return graph.compile()
