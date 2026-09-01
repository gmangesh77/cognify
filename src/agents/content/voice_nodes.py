"""Voice-match scoring + fix graph nodes (AUTHOR-011, spec §4.5).

`score_voice` is pure — scores every section against the persona's
fingerprint, no LLM. `fix_voice_deviations` runs ONE targeted rewrite per
weak section (mirrors `humanize_node`), reusing the humanizer's sentinel
block splitting. Both nodes are no-ops without a fingerprint, never fail
the run (spec §4), and are only added to the graph when the flag is on.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.content.humanizer import payload_for_llm, slot_back
from src.agents.prompts import render_prompt
from src.models.content_pipeline import SectionDraft
from src.models.persona import VoiceFingerprint, VoiceScore
from src.services.persona import SHORT_SECTION_WORDS, score_sections, score_text
from src.utils.markdown_structure import (
    humanizable_blocks,
    parse_markdown_blocks,
    reassemble,
)

if TYPE_CHECKING:
    from src.agents.content.pipeline import ContentState

logger = structlog.get_logger()

_CITATION_RE = re.compile(r"\[\d+\]")


def _coerce_drafts(raw: Sequence[object]) -> list[SectionDraft]:
    """Coerce state dicts to SectionDraft models (same shape as humanize_node)."""
    return [
        d if isinstance(d, SectionDraft) else SectionDraft.model_validate(d)
        for d in raw
    ]


def _needs_fix(draft: SectionDraft, score: int, threshold: int) -> bool:
    """Shared by the router and fix loop so they can't drift."""
    return score < threshold and draft.word_count >= SHORT_SECTION_WORDS


async def _run_score_voice(state: ContentState) -> dict[str, object]:
    fp = state.get("voice_fingerprint")
    if not fp or state.get("status") == "failed":
        return {}
    drafts = _coerce_drafts(state.get("section_drafts", []))
    by_section, overall = score_sections(drafts, fp)
    logger.info("voice_scored", overall=overall, sections=len(by_section))
    return {"voice_scores_by_section": by_section, "voice_match_score": overall}


def make_score_voice_node() -> Any:  # noqa: ANN401
    """Factory: pure per-section + overall voice-match scoring."""

    async def score_voice_node(state: ContentState) -> dict[str, object]:
        try:
            return await _run_score_voice(state)
        except Exception as exc:  # noqa: BLE001 — never let scoring fail the run
            logger.error("voice_score_failed", error=str(exc))
            return {}

    return score_voice_node


def make_voice_router(threshold: int) -> Callable[[dict[str, object]], str]:
    """`fix_voice_deviations` only if `_needs_fix` is true for some section
    — a short, weak-scoring section the fix loop skips must not still
    route through a no-op fix step. Typed on `dict[str, object]`, not
    `ContentState`: langgraph's `add_conditional_edges` resolves the
    router's annotations via `get_type_hints()` at runtime, raising
    `NameError` on `ContentState` — it only exists under `TYPE_CHECKING`
    here, and a real import would be circular with `pipeline.py`.
    """

    def _route(state: dict[str, object]) -> str:
        scores = state.get("voice_scores_by_section")
        raw_drafts = state.get("section_drafts")
        if not isinstance(scores, dict) or not isinstance(raw_drafts, list):
            return "seo_optimize"
        by_index = {str(d.section_index): d for d in _coerce_drafts(raw_drafts)}
        weak = any(
            _needs_fix(by_index[key], score, threshold)
            for key, score in scores.items()
            if key in by_index and isinstance(score, int)
        )
        return "fix_voice_deviations" if weak else "seo_optimize"

    return _route


def _deviation_block(score: VoiceScore) -> str:
    return "\n".join(f"- {d.message}" for d in score.deviations[:5])


@dataclass(frozen=True)
class _FixRun:
    """Per-run invariants shared by every section in one fix pass."""

    llm: BaseChatModel
    fp: VoiceFingerprint
    voice_block: str
    threshold: int


async def _rewrite_for_voice(
    run: _FixRun, section: SectionDraft, score: VoiceScore
) -> SectionDraft | None:
    """One LLM pass targeting `score`'s named deviations. None = no change made."""
    # Local import: services.content.__init__ imports pipeline.py, which
    # imports this module — a module-level import here would be circular.
    from src.services.content.section_rewriter import strip_fences

    blocks = parse_markdown_blocks(section.body_markdown)
    rewritable = humanizable_blocks(blocks)
    if not rewritable:
        return None
    originals = set(_CITATION_RE.findall(section.body_markdown))
    messages = [
        SystemMessage(content=render_prompt("voice.fix.system")),
        HumanMessage(
            content=render_prompt(
                "voice.fix.user",
                voice_block=run.voice_block,
                deviations=_deviation_block(score),
                section_text=payload_for_llm(rewritable),
            )
        ),
    ]
    response = await run.llm.ainvoke(messages)
    new_text = strip_fences(str(response.content).strip())
    new_body = reassemble(slot_back(blocks, rewritable, new_text))
    if originals and not originals.issubset(set(_CITATION_RE.findall(new_body))):
        logger.warning("voice_fix_citations_lost", section_index=section.section_index)
        return None
    return section.model_copy(
        update={"body_markdown": new_body, "word_count": len(new_body.split())}
    )


async def _fix_one_section(run: _FixRun, section: SectionDraft) -> SectionDraft:
    """Score `section`; rewrite once if weak; keep whichever body scores higher."""
    original_score = score_text(section.body_markdown, run.fp)
    if not _needs_fix(section, original_score.score, run.threshold):
        return section
    try:
        rewritten = await _rewrite_for_voice(run, section, original_score)
    except Exception as exc:  # noqa: BLE001 — never let one section fail the run
        logger.warning(
            "voice_fix_failed", section_index=section.section_index, error=str(exc)
        )
        return section
    if rewritten is None:
        return section
    new_score = score_text(rewritten.body_markdown, run.fp)
    return rewritten if new_score.score > original_score.score else section


async def _run_fix_voice(
    state: ContentState, llm: BaseChatModel, threshold: int
) -> dict[str, object]:
    fp = state.get("voice_fingerprint")
    if not fp or state.get("status") == "failed":
        return {}
    drafts = _coerce_drafts(state.get("section_drafts", []))
    voice_block = state.get("voice_block") or ""
    run = _FixRun(llm=llm, fp=fp, voice_block=voice_block, threshold=threshold)
    updated = [await _fix_one_section(run, section) for section in drafts]
    by_section, overall = score_sections(updated, fp)
    logger.info("voice_fix_complete", overall=overall, sections=len(by_section))
    return {
        "section_drafts": updated,
        "voice_scores_by_section": by_section,
        "voice_match_score": overall,
    }


def make_fix_voice_node(llm: BaseChatModel, threshold: int) -> Any:  # noqa: ANN401
    """Factory: one targeted rewrite per section scoring below `threshold`."""

    async def fix_voice_node(state: ContentState) -> dict[str, object]:
        try:
            return await _run_fix_voice(state, llm, threshold)
        except Exception as exc:  # noqa: BLE001 — never let the fix pass fail the run
            logger.error("voice_fix_failed", error=str(exc))
            return {}

    return fix_voice_node
