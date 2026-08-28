"""AUTHOR-009 — humanization as a stream of per-pass events.

Same fix → score → rewrite building blocks as `humanize_preview.py`, but
iterated (up to `max_llm_passes` LLM passes) and yielded one event per
pass so the dashboard can show iteration visibility. Preview-only: never
persists; the client stages the resolved text through `section-update`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.content.humanizer import fix_mechanical, rewrite_section
from src.agents.content.slop_scorer import score_section
from src.models.content_pipeline import SectionDraft, SlopScore
from src.services.content.humanize_preview import REWRITE_THRESHOLD
from src.services.content.section_rewriter import model_label
from src.services.content.sentence_segments import segment_sentences
from src.services.content.word_diff import diff_words

logger = structlog.get_logger()

EventType = Literal["pass", "done", "error"]


@dataclass(frozen=True)
class HumanizeEvent:
    type: EventType
    data: dict[str, object]

    def to_sse(self) -> str:
        return f"event: {self.type}\ndata: {json.dumps(self.data)}\n\n"


def _draft(index: int, title: str, text: str) -> SectionDraft:
    return SectionDraft(
        section_index=index,
        title=title,
        body_markdown=text,
        word_count=len(text.split()),
        citations_used=[],
    )


def _pass_event(
    index: int,
    name: str,
    scores: tuple[SlopScore, SlopScore],
    *,
    changed: bool,
    model: str | None,
) -> HumanizeEvent:
    before, after = scores
    return HumanizeEvent(
        "pass",
        {
            "index": index,
            "name": name,
            "score_before": before.score,
            "score_after": after.score,
            "rating": after.rating,
            "changed": changed,
            "model": model,
        },
    )


async def _llm_pass(
    draft: SectionDraft, score: SlopScore, llm: BaseChatModel
) -> SectionDraft:
    rewritten = await rewrite_section(draft, score, llm)
    return _draft(
        draft.section_index, draft.title, fix_mechanical(rewritten.body_markdown)
    )


def _done_payload(
    original: str, final: str, scores: tuple[SlopScore, SlopScore]
) -> dict[str, object]:
    return {
        "original": original,
        "rewritten": final,
        "diff": [op.to_dict() for op in diff_words(original, final)],
        "segments": [s.to_dict() for s in segment_sentences(original, final)],
        "score_before": scores[0].score,
        "score_after": scores[1].score,
    }


@dataclass
class _Loop:
    """Mutable iteration state for `stream_humanization`."""

    current: SectionDraft
    score: SlopScore
    passes: int = 1
    llm_calls: int = 0
    model: str | None = None


async def _run_llm_passes(
    loop: _Loop, llm: BaseChatModel, max_llm_passes: int
) -> AsyncIterator[HumanizeEvent]:
    while loop.score.score < REWRITE_THRESHOLD and loop.llm_calls < max_llm_passes:
        nxt = await _llm_pass(loop.current, loop.score, llm)
        loop.llm_calls += 1
        loop.model = model_label(llm)
        changed = nxt.body_markdown != loop.current.body_markdown
        score_next = score_section(nxt)
        yield _pass_event(
            loop.passes,
            "llm",
            (loop.score, score_next),
            changed=changed,
            model=loop.model,
        )
        loop.passes += 1
        loop.current, loop.score = nxt, score_next
        if not changed:
            break


async def stream_humanization(
    *,
    section_index: int,
    title: str,
    markdown: str,
    llm: BaseChatModel,
    max_llm_passes: int,
) -> AsyncIterator[HumanizeEvent]:
    """Yield one `pass` per humanization pass, then `done` (or `error`)."""
    original = _draft(section_index, title, markdown)
    score_orig = score_section(original)
    loop = _Loop(
        current=_draft(section_index, title, fix_mechanical(markdown)), score=score_orig
    )
    loop.score = score_section(loop.current)
    yield _pass_event(
        0,
        "mechanical",
        (score_orig, loop.score),
        changed=loop.current.body_markdown != markdown,
        model=None,
    )
    try:
        async for event in _run_llm_passes(loop, llm, max_llm_passes):
            yield event
    except Exception as exc:  # noqa: BLE001 — surface to the client, never crash the stream
        logger.warning(
            "humanize_stream_failed", section_index=section_index, error=str(exc)
        )
        yield HumanizeEvent("error", {"message": str(exc)})
        return
    logger.info(
        "humanize_stream_done",
        section_index=section_index,
        passes=loop.passes,
        llm_calls=loop.llm_calls,
        score_after=loop.score.score,
    )
    payload = _done_payload(
        markdown, loop.current.body_markdown, (score_orig, loop.score)
    )
    payload.update(
        {"passes": loop.passes, "llm_called": loop.llm_calls > 0, "model": loop.model}
    )
    yield HumanizeEvent("done", payload)


__all__ = ["HumanizeEvent", "stream_humanization"]
