"""Humanize node factory for the content pipeline graph.

Applies mechanical fixes to all sections, then scores each.
Sections scoring below threshold get an LLM rewrite attempt.
Non-fatal — never sets status to failed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.content.humanizer import fix_mechanical, rewrite_section
from src.agents.content.slop_scorer import score_section
from src.models.content_pipeline import SectionDraft

if TYPE_CHECKING:
    from src.agents.content.pipeline import ContentState

logger = structlog.get_logger()

_REWRITE_THRESHOLD = 70


def _coerce_drafts(raw: list[object]) -> list[SectionDraft]:
    """Coerce state dicts to SectionDraft models."""
    return [
        d if isinstance(d, SectionDraft) else SectionDraft.model_validate(d)
        for d in raw
    ]


def _apply_mechanical(section: SectionDraft) -> SectionDraft:
    """Apply mechanical fixes and return a new SectionDraft."""
    fixed = fix_mechanical(section.body_markdown)
    return SectionDraft(
        section_index=section.section_index,
        title=section.title,
        body_markdown=fixed,
        word_count=len(fixed.split()),
        citations_used=section.citations_used,
    )


async def _humanize_one(
    section: SectionDraft, llm: BaseChatModel
) -> SectionDraft:
    """Fix, score, and optionally rewrite one section."""
    fixed = _apply_mechanical(section)
    slop = score_section(fixed)
    logger.info(
        "humanize_scored",
        section=fixed.section_index,
        score=slop.score,
        rating=slop.rating,
    )
    if slop.score >= _REWRITE_THRESHOLD:
        return fixed
    rewritten = await rewrite_section(fixed, slop, llm)
    return _apply_mechanical(rewritten)


async def _run_humanize(
    state: ContentState, llm: BaseChatModel
) -> dict[str, object]:
    """Core humanize logic — guard, iterate, summarise."""
    if state.get("status") == "failed":
        return {"section_drafts": state.get("section_drafts", [])}

    drafts = _coerce_drafts(state.get("section_drafts", []))
    updated: list[SectionDraft] = []
    rewritten_count = 0

    for section in drafts:
        result = await _humanize_one(section, llm)
        if result.body_markdown != section.body_markdown:
            rewritten_count += 1
        updated.append(result)

    logger.info(
        "humanize_complete",
        total=len(updated),
        rewritten=rewritten_count,
    )
    return {"section_drafts": updated}


def make_humanize_node(llm: BaseChatModel) -> Any:  # noqa: ANN401
    """Factory: returns async node function for humanize step."""

    async def humanize_node(state: ContentState) -> dict[str, object]:
        try:
            return await _run_humanize(state, llm)
        except Exception as exc:
            logger.error("humanize_failed", error=str(exc))
            return {"section_drafts": state.get("section_drafts", [])}

    return humanize_node
