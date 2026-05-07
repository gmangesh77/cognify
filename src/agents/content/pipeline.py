"""Content pipeline LangGraph StateGraph.

Orchestrates article generation stages: outline, query generation,
section drafting with RAG, and validation. Conditional edge gates
drafting on retriever availability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NotRequired, TypedDict
from uuid import UUID

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.content.humanize_node import make_humanize_node
from src.agents.content.illustration_generator import OpenAIDalleGenerator
from src.agents.content.image_planner_node import make_image_planner_node
from src.agents.content.image_render_node import make_image_render_node
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
from src.models.visual import ImageSpec
from src.services.milvus_retriever import MilvusRetriever
from src.services.visuals import init_registry as init_visual_registry
from src.services.visuals.object_storage import select_object_storage

if TYPE_CHECKING:
    from src.services.research import AgentStepRepository
    from src.utils.llm_call_repo import LlmCallRepository


@dataclass(frozen=True)
class ContentGraphDeps:
    """Optional step-tracking deps for the content pipeline."""

    step_repo: AgentStepRepository | None = field(default=None)
    session_id: UUID | None = field(default=None)
    llm_call_repo: LlmCallRepository | None = field(default=None)


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
    target_audience: NotRequired[str | None]
    content_tone: NotRequired[str | None]
    preferred_angle: NotRequired[str | None]
    keywords: NotRequired[list[str] | None]
    # VISUAL-005 / Phase 2 — image planner output and per-article style hints.
    image_specs: NotRequired[list[ImageSpec]]
    page_art_direction: NotRequired[str | None]
    audience_persona: NotRequired[str | None]


def _wrap_node(
    name: str,
    node_fn: object,
    deps: ContentGraphDeps | None,
) -> object:
    """Wrap a node function with step recording if deps are configured."""
    if deps is None or deps.step_repo is None:
        return node_fn

    async def wrapped(state: ContentState) -> dict:  # type: ignore[type-arg]
        from src.agents.research.orchestrator import _complete_step, _record_step

        sid = deps.session_id or state.get("session_id")
        step = await _record_step(deps.step_repo, sid, f"content_{name}")
        try:
            result = await node_fn(state)  # type: ignore[misc]
            output = _extract_output(name, result)
            await _complete_step(deps.step_repo, step, output)
            return result
        except Exception as exc:
            await _complete_step(
                deps.step_repo, step, {"error": str(exc)}, status="failed"
            )
            raise

    return wrapped


def _extract_output(name: str, result: dict) -> dict:  # type: ignore[type-arg]
    """Extract a meaningful summary from a node result dict."""
    if "outline" in result and result["outline"]:
        outline = result["outline"]
        count = len(outline.sections) if hasattr(outline, "sections") else 0
        title = getattr(outline, "title", "")
        return {"sections": count, "title": title}
    if "section_drafts" in result:
        drafts = result["section_drafts"]
        return {"sections_drafted": len(drafts)}
    if "total_word_count" in result:
        return {"word_count": result["total_word_count"]}
    if "global_citations" in result:
        cites = result.get("global_citations") or []
        return {"citation_count": len(cites)}
    if "seo_result" in result and result.get("seo_result"):
        seo = result["seo_result"]
        title = getattr(seo, "seo", {})
        if hasattr(title, "title"):
            return {"seo_title": title.title, "seo_generated": True}
        return {"seo_generated": True}
    if "image_specs" in result:
        specs = result.get("image_specs") or []
        return {"image_specs_count": len(specs)}
    if "visuals" in result:
        visuals = result.get("visuals") or []
        return {"visuals_count": len(visuals)}
    return {"done": True}


def build_content_graph(
    llm: BaseChatModel,
    retriever: MilvusRetriever | None = None,
    settings: Settings | None = None,
    deps: ContentGraphDeps | None = None,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    """Build and compile the content pipeline graph."""
    graph = StateGraph(ContentState)
    graph.add_node(
        "generate_outline", _wrap_node("outline", make_outline_node(llm), deps)
    )
    graph.set_entry_point("generate_outline")

    graph.add_node(
        "generate_queries", _wrap_node("queries", make_queries_node(llm), deps)
    )
    graph.add_node(
        "draft_sections", _wrap_node("draft", make_draft_node(llm, retriever), deps)
    )
    graph.add_node(
        "validate_article",
        _wrap_node("validate", make_validate_node(llm, retriever), deps),
    )
    graph.add_node(
        "manage_citations", _wrap_node("citations", make_citations_node(), deps)
    )
    graph.add_node("humanize", _wrap_node("humanize", make_humanize_node(llm), deps))
    graph.add_node(
        "seo_optimize", _wrap_node("seo", make_seo_node(llm, settings), deps)
    )
    image_planner_enabled = bool(settings and settings.enable_image_planner)
    if image_planner_enabled:
        assert settings is not None  # noqa: S101 — guarded above
        max_per_section = settings.image_planner_max_images_per_section
        graph.add_node(
            "image_planner",
            _wrap_node(
                "image_planner",
                make_image_planner_node(
                    llm,
                    enabled=True,
                    max_images_per_section=max_per_section,
                ),
                deps,
            ),
        )
        registry = init_visual_registry(settings)
        storage = select_object_storage(settings)
        graph.add_node(
            "image_render",
            _wrap_node(
                "image_render",
                make_image_render_node(
                    registry=registry,
                    storage=storage,
                    default_provider=settings.default_image_provider,
                    concurrency=settings.image_render_concurrency,
                ),
                deps,
            ),
        )

    chart_dir = settings.chart_output_dir if settings else "generated_assets/charts"
    graph.add_node(
        "generate_charts", _wrap_node("charts", make_chart_node(llm, chart_dir), deps)
    )
    diagram_dir = (
        settings.diagram_output_dir if settings else "generated_assets/diagrams"
    )
    graph.add_node(
        "generate_diagrams",
        _wrap_node("diagrams", make_diagram_node(llm, diagram_dir), deps),
    )

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
    if image_planner_enabled:
        graph.add_edge("seo_optimize", "image_planner")
        graph.add_edge("image_planner", "image_render")
        graph.add_edge("image_render", "generate_charts")
    else:
        graph.add_edge("seo_optimize", "generate_charts")
    # Legacy DALL-E illustration node — runs only when the new planner is OFF
    # and an OpenAI key is configured. Phase 5 flips enable_image_planner=True
    # and this branch becomes dormant; deletion is a future cleanup ticket.
    if settings and settings.openai_api_key and not image_planner_enabled:
        generator = OpenAIDalleGenerator(
            api_key=settings.openai_api_key,
            model=settings.dalle_model,
            timeout=settings.illustration_timeout,
        )
        graph.add_node(
            "generate_illustrations",
            _wrap_node(
                "illustrations",
                make_illustration_node(
                    llm, generator, settings.illustration_output_dir
                ),
                deps,
            ),
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
