"""Voice-match scoring + fix graph nodes (AUTHOR-011, spec §4.5).

`score_voice` is pure — it scores every section against the persona's
fingerprint and never calls an LLM. `fix_voice_deviations` runs ONE
targeted rewrite per section that scored below threshold (mirrors
`humanize_node`'s single-pass-per-section shape), reusing the humanizer's
sentinel block splitting so structure (headings, lists, code, citations)
survives untouched. Both nodes are no-ops without a persona fingerprint
and are only added to the graph when `settings.enable_voice_engine`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
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


def make_score_voice_node() -> Any:  # noqa: ANN401
    """Factory: pure per-section + overall voice-match scoring."""

    async def score_voice_node(state: ContentState) -> dict[str, object]:
        fp = state.get("voice_fingerprint")
        if not fp or state.get("status") == "failed":
            return {}
        drafts = _coerce_drafts(state.get("section_drafts", []))
        by_section, overall = score_sections(drafts, fp)
        logger.info("voice_scored", overall=overall, sections=len(by_section))
        return {"voice_scores_by_section": by_section, "voice_match_score": overall}

    return score_voice_node


def make_voice_router(threshold: int) -> Callable[[dict[str, object]], str]:
    """`fix_voice_deviations` if any section scored below `threshold`.

    Typed on plain `dict[str, object]`, not `ContentState`: langgraph's
    `add_conditional_edges` resolves the router's annotations at runtime
    via `get_type_hints()`, which raises `NameError` on `ContentState`
    here — it only exists under `TYPE_CHECKING` in this module, and
    importing it for real would be circular with `pipeline.py` (which
    imports this module for the node factories). `ContentState` is
    TypedDict-shaped, so `dict[str, object]` is a safe, compatible
    supertype for a router that only reads one known key.
    """

    def _route(state: dict[str, object]) -> str:
        scores = state.get("voice_scores_by_section")
        if isinstance(scores, dict) and any(
            score < threshold for score in scores.values()
        ):
            return "fix_voice_deviations"
        return "seo_optimize"

    return _route


def _deviation_block(score: VoiceScore) -> str:
    return "\n".join(f"- {d.message}" for d in score.deviations[:5])


async def _rewrite_for_voice(
    section: SectionDraft,
    llm: BaseChatModel,
    voice_block: str,
    score: VoiceScore,
) -> SectionDraft | None:
    """One LLM pass targeting `score`'s named deviations. None = no change made."""
    # Local import: `section_rewriter` sits behind `services.content.__init__`,
    # which imports `pipeline.py`, which imports this module — a module-level
    # import here would be circular.
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
                voice_block=voice_block,
                deviations=_deviation_block(score),
                section_text=payload_for_llm(rewritable),
            )
        ),
    ]
    response = await llm.ainvoke(messages)
    new_text = strip_fences(str(response.content).strip())
    new_body = reassemble(slot_back(blocks, rewritable, new_text))
    if originals and not originals.issubset(set(_CITATION_RE.findall(new_body))):
        logger.warning("voice_fix_citations_lost", section_index=section.section_index)
        return None
    return section.model_copy(
        update={"body_markdown": new_body, "word_count": len(new_body.split())}
    )


async def _fix_one_section(
    section: SectionDraft,
    fp: VoiceFingerprint,
    llm: BaseChatModel,
    threshold: int,
    voice_block: str,
) -> SectionDraft:
    """Score `section`; rewrite once if weak; keep whichever body scores higher."""
    original_score = score_text(section.body_markdown, fp)
    if original_score.score >= threshold or section.word_count < SHORT_SECTION_WORDS:
        return section
    try:
        rewritten = await _rewrite_for_voice(section, llm, voice_block, original_score)
    except Exception as exc:  # noqa: BLE001 — never let one section fail the run
        logger.warning(
            "voice_fix_failed", section_index=section.section_index, error=str(exc)
        )
        return section
    if rewritten is None:
        return section
    new_score = score_text(rewritten.body_markdown, fp)
    return rewritten if new_score.score > original_score.score else section


def make_fix_voice_node(llm: BaseChatModel, threshold: int) -> Any:  # noqa: ANN401
    """Factory: one targeted rewrite per section scoring below `threshold`."""

    async def fix_voice_node(state: ContentState) -> dict[str, object]:
        fp = state.get("voice_fingerprint")
        if not fp or state.get("status") == "failed":
            return {}
        drafts = _coerce_drafts(state.get("section_drafts", []))
        voice_block = state.get("voice_block") or ""
        updated = [
            await _fix_one_section(section, fp, llm, threshold, voice_block)
            for section in drafts
        ]
        by_section, overall = score_sections(updated, fp)
        logger.info("voice_fix_complete", overall=overall, sections=len(by_section))
        return {
            "section_drafts": updated,
            "voice_scores_by_section": by_section,
            "voice_match_score": overall,
        }

    return fix_voice_node
