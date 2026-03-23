"""Content pipeline LangGraph StateGraph.

Orchestrates article generation stages: outline, query generation,
section drafting with RAG, and validation. Conditional edge gates
drafting on retriever availability.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict
from uuid import UUID

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.content.humanize_node import make_humanize_node
from src.agents.content.illustration_generator import OpenAIDalleGenerator
from src.agents.content.nodes import (
    make_chart_node,
    make_citations_node,
    make_diagram_node,
    make_draft_node,
    make_illustration_node,
    make_outline_node,
    make_queries_node,
    make_validate_node,
)
from src.agents.content.seo_node import make_seo_node
from src.config.settings import Settings
from src.models.content import ImageAsset
from src.models.content_pipeline import (
    ArticleOutline,
    SectionDraft,
    SectionQueries,
    SEOResult,
)
from src.models.research import FacetFindings, ResearchPlan, TopicInput
from src.services.milvus_retriever import MilvusRetriever


class ContentState(TypedDict):
    """State flowing through the content pipeline graph."""

    topic: TopicInput
    research_plan: ResearchPlan | None
    findings: list[FacetFindings]
    session_id: UUID
    outline: ArticleOutline | None
    status: str
    error: str | None
    section_queries: NotRequired[list[SectionQueries]]
    section_drafts: NotRequired[list[SectionDraft]]
    total_word_count: NotRequired[int]
    global_citations: NotRequired[list[dict[str, object]]]
    references_markdown: NotRequired[str]
    seo_result: NotRequired[SEOResult]
    visuals: NotRequired[list[ImageAsset]]


def build_content_graph(
    llm: BaseChatModel,
    retriever: MilvusRetriever | None = None,
    settings: Settings | None = None,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    """Build and compile the content pipeline graph."""
    graph = StateGraph(ContentState)
    graph.add_node("generate_outline", make_outline_node(llm))
    graph.set_entry_point("generate_outline")

    if retriever is None:
        graph.add_edge("generate_outline", END)
        return graph.compile()

    graph.add_node("generate_queries", make_queries_node(llm))
    graph.add_node("draft_sections", make_draft_node(llm, retriever))
    graph.add_node("validate_article", make_validate_node(llm, retriever))
    graph.add_node("manage_citations", make_citations_node())
    graph.add_node("humanize", make_humanize_node(llm))
    graph.add_node("seo_optimize", make_seo_node(llm, settings))
    chart_dir = settings.chart_output_dir if settings else "generated_assets/charts"
    graph.add_node("generate_charts", make_chart_node(llm, chart_dir))
    diagram_dir = settings.diagram_output_dir if settings else "generated_assets/diagrams"
    graph.add_node("generate_diagrams", make_diagram_node(llm, diagram_dir))

    graph.add_conditional_edges(
        "generate_outline",
        _should_draft,
        {"generate_queries": "generate_queries", END: END},
    )
    graph.add_conditional_edges(
        "generate_queries",
        _check_not_failed,
        {"draft_sections": "draft_sections", END: END},
    )
    graph.add_edge("draft_sections", "validate_article")
    graph.add_edge("validate_article", "manage_citations")
    graph.add_edge("manage_citations", "humanize")
    graph.add_edge("humanize", "seo_optimize")
    graph.add_edge("seo_optimize", "generate_charts")
    # Illustration node — only if OpenAI key is configured
    if settings and settings.openai_api_key:
        generator = OpenAIDalleGenerator(
            api_key=settings.openai_api_key,
            model=settings.dalle_model,
            timeout=settings.illustration_timeout,
        )
        graph.add_node(
            "generate_illustrations",
            make_illustration_node(llm, generator, settings.illustration_output_dir),
        )
        graph.add_edge("generate_charts", "generate_illustrations")
        graph.add_edge("generate_illustrations", "generate_diagrams")
    else:
        graph.add_edge("generate_charts", "generate_diagrams")

    graph.add_edge("generate_diagrams", END)

    return graph.compile()


def _should_draft(state: ContentState) -> str:
    """Route to drafting if outline succeeded, else stop."""
    if state.get("outline") is not None and state.get("status") != "failed":
        return "generate_queries"
    return END


def _check_not_failed(state: ContentState) -> str:
    """Continue to drafting unless a prior node failed."""
    if state.get("status") == "failed":
        return END
    return "draft_sections"
