"""On-demand humanization preview (DASH-007).

Surfaces the same fix → score → rewrite pipeline used by the content
graph (`src/agents/content/humanize_node.py`) but as a one-shot
service the dashboard can call to show editors a structured-aware
diff before they accept. Reuses the structure-aware rewriter from
CONTENT-007 — non-prose blocks (headings, code, images) stay
verbatim.

Boundary invariant: this service only computes the preview; it does
NOT persist anything. The frontend accepts a result by POSTing the
new markdown through `/content/section-update`, which runs the
anchor-preservation validator and appends a version row.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.content.humanizer import fix_mechanical, rewrite_section
from src.agents.content.slop_scorer import score_section
from src.models.content_pipeline import SectionDraft, SlopScore
from src.services.content.word_diff import WordDiffOp, diff_words

logger = structlog.get_logger()

REWRITE_THRESHOLD = 70


@dataclass(frozen=True)
class HumanizePreview:
    """One humanization pass — what the editor sees before accepting."""

    original: str
    mechanical_fixed: str
    rewritten: str
    score_before: SlopScore
    score_after: SlopScore
    diff: list[WordDiffOp]
    llm_called: bool
    model: str | None


async def preview_humanization(
    *,
    section_index: int,
    title: str,
    markdown: str,
    llm: BaseChatModel,
) -> HumanizePreview:
    """Run mechanical fixes + slop scoring + optional LLM rewrite.

    Returns the original, post-mechanical, post-rewrite text along
    with slop scores and a word-level diff between original and
    rewritten. Mirrors the pipeline node's behaviour but never
    mutates state — the caller decides whether to persist.
    """
    section = SectionDraft(
        section_index=section_index,
        title=title,
        body_markdown=markdown,
        word_count=len(markdown.split()),
        citations_used=[],
    )
    fixed_text = fix_mechanical(section.body_markdown)
    fixed_section = SectionDraft(
        section_index=section_index,
        title=title,
        body_markdown=fixed_text,
        word_count=len(fixed_text.split()),
        citations_used=[],
    )
    score_before = score_section(section)
    score_after_mechanical = score_section(fixed_section)

    rewritten_section = fixed_section
    llm_called = False
    if score_after_mechanical.score < REWRITE_THRESHOLD:
        rewritten_section = await rewrite_section(
            fixed_section, score_after_mechanical, llm
        )
        # `rewrite_section` re-applies mechanical cleanups on success
        # (matches the pipeline node behaviour).
        rewritten_section = SectionDraft(
            section_index=section_index,
            title=title,
            body_markdown=fix_mechanical(rewritten_section.body_markdown),
            word_count=len(rewritten_section.body_markdown.split()),
            citations_used=[],
        )
        llm_called = True

    score_after = score_section(rewritten_section)
    diff = diff_words(section.body_markdown, rewritten_section.body_markdown)
    model_name = (
        getattr(llm, "model", None) or getattr(llm, "model_name", None)
        if llm_called
        else None
    )
    logger.info(
        "humanize_preview",
        section_index=section_index,
        score_before=score_before.score,
        score_after=score_after.score,
        llm_called=llm_called,
    )
    return HumanizePreview(
        original=section.body_markdown,
        mechanical_fixed=fixed_text,
        rewritten=rewritten_section.body_markdown,
        score_before=score_before,
        score_after=score_after,
        diff=diff,
        llm_called=llm_called,
        model=str(model_name) if model_name else None,
    )


__all__ = ["HumanizePreview", "REWRITE_THRESHOLD", "preview_humanization"]
