"""Node factory functions for the content pipeline graph.

Each factory closes over shared dependencies (LLM, retriever) and
returns an async node function compatible with LangGraph StateGraph.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.content.chart_generator import propose_charts, render_chart
from src.agents.content.illustration_generator import (
    ImageGenerator,
    generate_illustration_prompt,
)
from src.agents.content.outline_generator import generate_outline
from src.agents.content.query_generator import generate_section_queries
from src.agents.content.section_drafter import DraftingContext, draft_section
from src.agents.content.validate import replace_section, validate_drafts
from src.models.content import ImageAsset
from src.models.content_pipeline import (
    ArticleOutline,
    SectionDraft,
    SectionQueries,
)
from src.models.research import FacetFindings, TopicInput
from src.services.milvus_retriever import MilvusRetriever

if TYPE_CHECKING:
    from src.agents.content.pipeline import ContentState

logger = structlog.get_logger()


def make_outline_node(llm: BaseChatModel) -> Any:  # noqa: ANN401
    """Factory for the outline generation node."""

    async def outline_node(state: ContentState) -> dict[str, object]:
        if state.get("outline") is not None:
            logger.info("outline_already_present_skipping")
            return {"status": "outline_complete"}
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

    return outline_node


def make_queries_node(llm: BaseChatModel) -> Any:  # noqa: ANN401
    """Factory for the query generation node."""

    async def queries_node(state: ContentState) -> dict[str, object]:
        outline = _coerce_outline(state)
        try:
            queries = await generate_section_queries(outline, llm)
            logger.info("section_queries_node_complete", count=len(queries))
            return {"section_queries": queries}
        except Exception as exc:
            logger.error("query_generation_failed", error=str(exc))
            return {"status": "failed", "error": str(exc)}

    return queries_node


def make_draft_node(llm: BaseChatModel, retriever: MilvusRetriever) -> Any:  # noqa: ANN401
    """Factory for the section drafting node."""

    async def draft_node(state: ContentState) -> dict[str, object]:
        topic = _coerce_topic(state)
        outline = _coerce_outline(state)
        queries_list = state.get("section_queries", [])
        drafts: list[SectionDraft] = []
        for section in outline.sections:
            sq = _find_queries(queries_list, section.index)
            ctx = DraftingContext(
                retriever=retriever,
                topic_id=str(topic.id),
                llm=llm,
                prior_drafts=list(drafts),
            )
            draft = await draft_section(section, sq, ctx)
            drafts.append(draft)
        logger.info("draft_sections_complete", count=len(drafts))
        return {"section_drafts": drafts, "status": "draft_complete"}

    return draft_node


def make_validate_node(llm: BaseChatModel, retriever: MilvusRetriever) -> Any:  # noqa: ANN401
    """Factory for the article validation node."""

    async def validate_node(state: ContentState) -> dict[str, object]:
        drafts = list(state.get("section_drafts", []))
        result = validate_drafts(drafts)
        if result.needs_expansion and result.shortest_index is not None:
            drafts = await _redraft_shortest(
                state,
                drafts,
                result.shortest_index,
                llm,
                retriever,
            )
            result = validate_drafts(drafts)
        total = sum(d.word_count for d in drafts)
        logger.info("validate_article_complete", total_words=total)
        return {
            "section_drafts": drafts,
            "total_word_count": total,
            "status": "draft_complete",
        }

    return validate_node


def make_citations_node() -> Any:  # noqa: ANN401
    """Factory for the citation management node."""
    from src.agents.content.citation_manager import manage_citations

    return manage_citations


def make_chart_node(llm: BaseChatModel, output_dir: str) -> Any:  # noqa: ANN401
    """Factory for the chart generation node."""

    async def chart_node(state: ContentState) -> dict[str, object]:
        section_drafts = state.get("section_drafts", [])
        session_id: UUID = state["session_id"]
        if not section_drafts:
            return {"visuals": []}
        specs = await propose_charts(section_drafts, llm)
        visuals = []
        for spec in specs:
            asset = await asyncio.to_thread(render_chart, spec, output_dir, session_id)
            if asset is not None:
                visuals.append(asset)
        logger.info("chart_generation_complete", chart_count=len(visuals))
        return {"visuals": visuals}

    return chart_node


def make_illustration_node(
    llm: BaseChatModel,
    generator: ImageGenerator,
    output_dir: str,
) -> Any:  # noqa: ANN401
    """Factory for the AI illustration generation node."""

    async def illustration_node(state: ContentState) -> dict[str, object]:
        existing = list(state.get("visuals", []))
        topic = _coerce_topic(state)
        seo = state.get("seo_result")
        summary = seo.summary if seo and hasattr(seo, "summary") else ""
        session_id: UUID = state["session_id"]

        prompt = await generate_illustration_prompt(topic, summary, llm)
        if not prompt:
            return {"visuals": existing}

        try:
            image_bytes = await generator.generate(prompt, (1024, 1024))
        except Exception as exc:
            logger.warning("illustration_generator_error", error=str(exc))
            return {"visuals": existing}

        if not image_bytes:
            return {"visuals": existing}

        path = await asyncio.to_thread(
            _save_illustration, image_bytes, output_dir, session_id
        )
        asset = ImageAsset(
            url=str(path),
            caption=topic.title,
            alt_text=prompt[:200],
            metadata={"generator": "dall-e-3", "type": "hero"},
        )
        logger.info("illustration_generation_complete", path=str(path))
        return {"visuals": existing + [asset]}

    return illustration_node


def _save_illustration(
    image_bytes: bytes, output_dir: str, session_id: UUID
) -> Path:
    """Save illustration bytes to disk. Runs in thread."""
    out_path = Path(output_dir) / str(session_id)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / "hero.png"
    file_path.write_bytes(image_bytes)
    return file_path


def _coerce_topic(state: ContentState) -> TopicInput:
    """Extract and coerce topic from state."""
    topic = state["topic"]
    if not isinstance(topic, TopicInput):
        return TopicInput.model_validate(topic)
    return topic


def _coerce_outline(state: ContentState) -> ArticleOutline:
    """Extract and coerce outline from state."""
    outline = state["outline"]
    if not isinstance(outline, ArticleOutline):
        return ArticleOutline.model_validate(outline)
    return outline


async def _redraft_shortest(
    state: ContentState,
    drafts: list[SectionDraft],
    idx: int,
    llm: BaseChatModel,
    retriever: MilvusRetriever,
) -> list[SectionDraft]:
    """Re-draft the shortest section with an expanded word target."""
    topic = _coerce_topic(state)
    outline = _coerce_outline(state)
    section = next(s for s in outline.sections if s.index == idx)
    expanded = section.model_copy(
        update={"target_word_count": section.target_word_count * 2},
    )
    sq = _find_queries(state.get("section_queries", []), idx)
    ctx = DraftingContext(
        retriever=retriever,
        topic_id=str(topic.id),
        llm=llm,
        prior_drafts=[d for d in drafts if d.section_index != idx],
    )
    new_draft = await draft_section(expanded, sq, ctx)
    logger.info("section_redraft_triggered", section_index=idx)
    return replace_section(drafts, new_draft)


def _find_queries(
    queries_list: list[SectionQueries] | list[dict],  # type: ignore[type-arg]
    section_index: int,
) -> SectionQueries:
    """Find queries for a section, coercing dicts if needed."""
    for item in queries_list:
        sq = (
            item
            if isinstance(item, SectionQueries)
            else SectionQueries.model_validate(item)
        )
        if sq.section_index == section_index:
            return sq
    return SectionQueries(section_index=section_index, queries=[])
