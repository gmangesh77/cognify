# AUTHOR-009 — Humanize per-pass streaming + sentence-level accept/reject

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The "Humanize prose" panel streams one event per humanization pass (score after each), iterates up to 2 LLM passes while the slop score is under 70, and lets the editor accept/reject each changed sentence before staging the result.

**Architecture:** A new async generator service (`humanize_stream.py`) runs mechanical → LLM pass(es) and yields typed events; a new POST-SSE route streams them with the AUTHOR-001 frame format. A pure sentence segmenter (`sentence_segments.py`) turns original/final text into ordered segments covering the whole section, so the client rebuilds markdown deterministically from per-segment decisions and persists through the existing `/content/section-update` validator. The frontend gets POST support in the shared SSE consumer, a `useHumanizeStream` hook, and a split panel (tiles + change list). The existing JSON `/humanize-preview` endpoint, `preview_humanization`, and the pipeline's single-pass humanize node are untouched.

**Tech Stack:** Python 3.12 / FastAPI `StreamingResponse` / pydantic / difflib / pytest + `FakeListChatModel`; Next.js 15 / React 19 / Vitest + Testing Library.

**Spec:** `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §9 Phase B (AUTHOR-009 row + acceptance "Humanize preview streams ≥2 events and per-sentence accept/reject round-trips through `section-update` with anchors intact"); `docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md` §6 #9. Design decisions (2026-08-28, with the user): iterate up to **2** LLM passes; changed sentences start **accepted** (reject to opt out).

## Global Constraints

- All functions < 20 lines, files < 200 lines, max 3 params (CLAUDE.md). `frontend/src/file-size-budget.test.ts` enforces the frontend budget for `src/app` + `src/components`.
- TDD: failing test first. Backend `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/ -q`; frontend `cd frontend && npx vitest run`.
- Every new setting is `COGNIFY_*` in `src/config/settings.py`: `humanize_preview_max_passes: int = 2`.
- L-002: LLM output goes through the existing `rewrite_section` (no JSON parsing here). Rewrite threshold stays `REWRITE_THRESHOLD = 70` (imported from `humanize_preview.py`, not duplicated).
- Route decorator OUTERMOST, `@limiter.limit` inside (AUTHOR-006 lesson). New route: editor+, `20/minute`.
- SSE frames use the same `event: <type>\ndata: <json>\n\n` shape as `SessionEvent.to_sse()`; headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`.
- No new colour/font tokens; tiles reuse the existing badge classes (`bg-error-light/60 text-error`, `bg-success-light/60 text-success`, `bg-warning-light text-warning`).
- One PR off `develop`, never stacked. No Azure Boards items for Epic 11.
- Conventional commits: `feat(content): …`, `feat(frontend): …`, `test: …`, `docs: …`.

## File map

| Area | Create | Modify |
|---|---|---|
| Segmenter | `src/services/content/sentence_segments.py`, `tests/unit/services/content/test_sentence_segments.py` | — |
| Stream service | `src/services/content/humanize_stream.py`, `tests/unit/services/content/test_humanize_stream.py` | `src/config/settings.py` |
| Endpoint | `src/api/routers/content_humanize_stream.py`, `tests/unit/api/test_content_humanize_stream_endpoint.py` | `src/api/main.py` (import + `include_router`) |
| SSE consumer | — | `frontend/src/lib/sse/consume-sse.ts`, `frontend/src/lib/sse/consume-sse.test.ts` (create if absent) |
| Segment resolver | `frontend/src/lib/content/resolve-segments.ts`, `frontend/src/lib/content/resolve-segments.test.ts` | `frontend/src/types/content.ts` |
| Hook | `frontend/src/hooks/use-humanize-stream.ts`, `frontend/src/hooks/use-humanize-stream.test.tsx` | `frontend/src/lib/api/content.ts` (`humanizeStreamUrl`) |
| Panel | `frontend/src/components/article/HumanizePassTiles.tsx`, `frontend/src/components/article/HumanizeChangeList.tsx` | `frontend/src/components/article/HumanizationDiffPanel.tsx`, `frontend/src/components/article/HumanizationDiffPanel.test.tsx` |
| Docs | — | `project-management/PROGRESS.md`, `project-management/BACKLOG.md`, `CLAUDE.md`, this plan |

---

### Task 1: Sentence segmenter (pure)

**Files:**
- Create: `src/services/content/sentence_segments.py`
- Test: `tests/unit/services/content/test_sentence_segments.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class Segment:
      id: str            # "s0", "s1", … (position in the list)
      kind: Literal["equal", "change"]
      before: str        # exact original text of this span ("" for pure insert)
      after: str         # exact final text of this span ("" for pure delete)
      ops: list[WordDiffOp]  # word diff of before→after; [] for equal
      def to_dict(self) -> dict[str, object]
  def tokenize_sentences(text: str) -> list[str]
  def segment_sentences(before: str, after: str) -> list[Segment]
  def resolve_segments(segments: list[Segment], rejected: set[str]) -> str
  ```
- Invariants: `"".join(s.before for s in segs) == before`; `"".join(s.after for s in segs) == after`; `resolve_segments(segs, set()) == after`; `resolve_segments(segs, {all change ids}) == before`.

- [x] **Step 1: Write the failing tests**

```python
"""AUTHOR-009 — sentence-level segments between original and humanized text."""

from src.services.content.sentence_segments import (
    Segment,
    resolve_segments,
    segment_sentences,
    tokenize_sentences,
)


def _ids(segs: list[Segment], kind: str) -> set[str]:
    return {s.id for s in segs if s.kind == kind}


class TestTokenizeSentences:
    def test_splits_on_terminal_punctuation_and_keeps_whitespace(self) -> None:
        toks = tokenize_sentences("One. Two!  Three?")
        assert "".join(toks) == "One. Two!  Three?"
        assert [t for t in toks if t.strip()] == ["One.", "Two!", "Three?"]

    def test_newlines_are_their_own_tokens(self) -> None:
        toks = tokenize_sentences("## Heading\n\nBody one. Body two.")
        assert "".join(toks) == "## Heading\n\nBody one. Body two."
        assert "## Heading" in toks
        assert "\n\n" in toks


class TestSegmentSentences:
    def test_identical_text_is_one_equal_segment(self) -> None:
        segs = segment_sentences("A. B.", "A. B.")
        assert [s.kind for s in segs] == ["equal"]
        assert segs[0].before == "A. B." and segs[0].after == "A. B."

    def test_changed_sentence_becomes_a_change_segment(self) -> None:
        before = "Keep this. Delve into the topic. Keep that."
        after = "Keep this. Explore the topic. Keep that."
        segs = segment_sentences(before, after)
        changes = [s for s in segs if s.kind == "change"]
        assert len(changes) == 1
        assert changes[0].before == "Delve into the topic."
        assert changes[0].after == "Explore the topic."
        assert changes[0].ops, "change segments carry a word diff"
        assert "".join(s.before for s in segs) == before
        assert "".join(s.after for s in segs) == after

    def test_headings_and_markers_stay_in_equal_segments(self) -> None:
        before = '## Title\n\n<span data-spec-id="x"></span>\n\nDelve deeply. Fine.'
        after = '## Title\n\n<span data-spec-id="x"></span>\n\nDig in. Fine.'
        segs = segment_sentences(before, after)
        equal_text = "".join(s.before for s in segs if s.kind == "equal")
        assert "## Title" in equal_text
        assert 'data-spec-id="x"' in equal_text

    def test_insert_and_delete_segments(self) -> None:
        segs = segment_sentences("A. B.", "A. New. B.")
        inserted = [s for s in segs if s.kind == "change" and s.before == ""]
        assert inserted and inserted[0].after.strip() == "New."
        segs2 = segment_sentences("A. Gone. B.", "A. B.")
        deleted = [s for s in segs2 if s.kind == "change" and s.after == ""]
        assert deleted and deleted[0].before.strip() == "Gone."

    def test_ids_are_positional_and_unique(self) -> None:
        segs = segment_sentences("A. B. C.", "A. X. C.")
        assert [s.id for s in segs] == [f"s{i}" for i in range(len(segs))]

    def test_to_dict_is_json_shaped(self) -> None:
        seg = segment_sentences("A.", "B.")[0]
        d = seg.to_dict()
        assert set(d) == {"id", "kind", "before", "after", "ops"}
        assert isinstance(d["ops"], list) and all(isinstance(o, dict) for o in d["ops"])


class TestResolveSegments:
    def test_no_rejections_yields_final_text(self) -> None:
        before, after = "A. Old. C.", "A. New. C."
        segs = segment_sentences(before, after)
        assert resolve_segments(segs, set()) == after

    def test_rejecting_every_change_yields_original(self) -> None:
        before, after = "A. Old. C. Older.", "A. New. C. Newer."
        segs = segment_sentences(before, after)
        assert resolve_segments(segs, _ids(segs, "change")) == before

    def test_partial_rejection_mixes(self) -> None:
        before, after = "A. Old. C. Older.", "A. New. C. Newer."
        segs = segment_sentences(before, after)
        first_change = sorted(_ids(segs, "change"))[0]
        out = resolve_segments(segs, {first_change})
        assert "Old." in out and "Newer." in out
```

- [x] **Step 2: Run to verify they fail**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/content/test_sentence_segments.py -q`
Expected: collection error — `src.services.content.sentence_segments` does not exist.

- [x] **Step 3: Implement** — `src/services/content/sentence_segments.py`:

```python
"""AUTHOR-009 — sentence-level segments between original and humanized text.

`segment_sentences` tokenises both texts into sentence / whitespace /
newline tokens and aligns them with `difflib`. Every character of both
inputs lands in exactly one segment, so the client (or `resolve_segments`)
can rebuild the markdown from per-segment accept/reject decisions without
a second API call. Newlines are their own tokens, so headings, code
fences, list items and `data-spec-id` markers never merge into a prose
sentence and — being unchanged by the humanizer — always come back as
`equal` segments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from src.services.content.word_diff import WordDiffOp, diff_words

SegmentKind = Literal["equal", "change"]

# A sentence runs up to terminal punctuation (or end of line); whitespace
# runs and newlines are separate tokens so joins are lossless.
_SENTENCE_TOKEN_RE = re.compile(r"\n+|[ \t]+|[^\n]+?(?:[.!?](?=[ \t\n]|$)|(?=\n)|$)")


@dataclass(frozen=True)
class Segment:
    id: str
    kind: SegmentKind
    before: str
    after: str
    ops: list[WordDiffOp]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "before": self.before,
            "after": self.after,
            "ops": [op.to_dict() for op in self.ops],
        }


def tokenize_sentences(text: str) -> list[str]:
    """Split into sentence / whitespace / newline tokens; ``"".join`` round-trips."""
    return [t for t in _SENTENCE_TOKEN_RE.findall(text) if t]


def segment_sentences(before: str, after: str) -> list[Segment]:
    """Align sentences of `before` and `after` into ordered, gap-free segments."""
    a, b = tokenize_sentences(before), tokenize_sentences(after)
    matcher = SequenceMatcher(a=a, b=b, autojunk=False)
    segments: list[Segment] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old, new = "".join(a[i1:i2]), "".join(b[j1:j2])
        kind: SegmentKind = "equal" if tag == "equal" else "change"
        ops = [] if kind == "equal" else diff_words(old, new)
        segments.append(Segment(f"s{len(segments)}", kind, old, new, ops))
    return _merge_adjacent_equal(segments)


def _merge_adjacent_equal(segments: list[Segment]) -> list[Segment]:
    """difflib never emits two consecutive equal opcodes, but re-id defensively."""
    return [
        Segment(f"s{i}", s.kind, s.before, s.after, s.ops)
        for i, s in enumerate(segments)
    ]


def resolve_segments(segments: list[Segment], rejected: set[str]) -> str:
    """Rebuild text: rejected change segments keep `before`, everything else `after`."""
    return "".join(
        s.before if (s.kind == "change" and s.id in rejected) else s.after
        for s in segments
    )


__all__ = ["Segment", "SegmentKind", "resolve_segments", "segment_sentences", "tokenize_sentences"]
```

If `test_changed_sentence_becomes_a_change_segment` shows the change segment absorbing the surrounding space (e.g. `before == " Delve into the topic."`), that is acceptable **only if** the round-trip and resolve assertions still hold — adjust the test's `.strip()` expectations rather than the tokenizer. Do not weaken the round-trip invariants.

- [x] **Step 4: Run to verify they pass**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/content/test_sentence_segments.py -q`
Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/services/content/sentence_segments.py tests/unit/services/content/test_sentence_segments.py
git commit -m "feat(content): sentence-level segmenter for humanize accept/reject (AUTHOR-009)"
```

---

### Task 2: Streaming humanization service (multi-pass)

**Files:**
- Create: `src/services/content/humanize_stream.py`
- Modify: `src/config/settings.py`
- Test: `tests/unit/services/content/test_humanize_stream.py`

**Interfaces:**
- Consumes: `fix_mechanical`, `rewrite_section` (`src/agents/content/humanizer.py`), `score_section` (`slop_scorer`), `REWRITE_THRESHOLD` (`humanize_preview.py`), `diff_words`, `segment_sentences` (Task 1), `model_label` (`section_rewriter.py`).
- Produces:
  ```python
  @dataclass(frozen=True)
  class HumanizeEvent:
      type: Literal["pass", "done", "error"]
      data: dict[str, object]
      def to_sse(self) -> str   # f"event: {type}\ndata: {json.dumps(data)}\n\n"
  async def stream_humanization(*, section_index: int, title: str, markdown: str, llm: BaseChatModel, max_llm_passes: int) -> AsyncIterator[HumanizeEvent]
  ```
  `pass` data: `{index, name: "mechanical"|"llm", score_before, score_after, rating, changed: bool, model: str|None}`.
  `done` data: `{original, rewritten, diff: [WordDiffOp dicts], segments: [Segment dicts], passes: int, llm_called: bool, model: str|None, score_before, score_after}`.
  `error` data: `{message}`.
- `Settings.humanize_preview_max_passes: int = 2` (`COGNIFY_HUMANIZE_PREVIEW_MAX_PASSES`).
- Loop rules: always one mechanical pass first; then LLM passes while `score < REWRITE_THRESHOLD` and `passes_done < max_llm_passes`; stop early when a pass leaves the text unchanged (`changed=False`). An exception inside a pass yields `error` and ends the stream (no `done`).

- [x] **Step 1: Write the failing tests** — `tests/unit/services/content/test_humanize_stream.py`:

```python
"""AUTHOR-009 — multi-pass humanization as an event stream."""

from __future__ import annotations

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content import slop_scorer
from src.models.content_pipeline import SlopScore
from src.services.content.humanize_stream import HumanizeEvent, stream_humanization


def _score(score: int) -> SlopScore:
    return SlopScore(
        score=score,
        rating="LIKELY_AI" if score < 60 else "MOSTLY_HUMAN",
        violations=[],
        phrase_deductions=0,
        pattern_deductions=0,
    )


def _scores_by_prefix(mapping: dict[str, int], default: int):
    def _fake(text: str) -> SlopScore:
        for prefix, score in mapping.items():
            if text.startswith(prefix):
                return _score(score)
        return _score(default)

    return _fake


async def _collect(gen) -> list[HumanizeEvent]:
    return [ev async for ev in gen]


class TestStreamHumanization:
    async def test_clean_text_emits_mechanical_pass_then_done(self, monkeypatch) -> None:
        monkeypatch.setattr(slop_scorer, "score_text", _scores_by_prefix({}, 90))
        events = await _collect(
            stream_humanization(
                section_index=0, title="S", markdown="Clean prose.",
                llm=FakeListChatModel(responses=["unused"]), max_llm_passes=2,
            )
        )
        assert [e.type for e in events] == ["pass", "done"]
        assert events[0].data["name"] == "mechanical"
        assert events[-1].data["llm_called"] is False
        assert events[-1].data["passes"] == 1

    async def test_two_llm_passes_until_threshold(self, monkeypatch) -> None:
        # original 30 → pass1 output 50 → pass2 output 80 (clears 70)
        monkeypatch.setattr(
            slop_scorer, "score_text", _scores_by_prefix({"First": 50, "Second": 80}, 30)
        )
        llm = FakeListChatModel(responses=["First rewrite.", "Second rewrite."])
        events = await _collect(
            stream_humanization(
                section_index=0, title="S", markdown="Delve into it.",
                llm=llm, max_llm_passes=2,
            )
        )
        assert [e.type for e in events] == ["pass", "pass", "pass", "done"]
        assert [e.data["name"] for e in events[:3]] == ["mechanical", "llm", "llm"]
        assert events[1].data["index"] == 1 and events[2].data["index"] == 2
        done = events[-1].data
        assert done["passes"] == 3 and done["llm_called"] is True
        assert done["rewritten"].startswith("Second")
        assert done["segments"] and done["diff"]

    async def test_stops_after_first_llm_pass_when_threshold_cleared(self, monkeypatch) -> None:
        monkeypatch.setattr(slop_scorer, "score_text", _scores_by_prefix({"Good": 85}, 30))
        llm = FakeListChatModel(responses=["Good rewrite.", "never used"])
        events = await _collect(
            stream_humanization(
                section_index=0, title="S", markdown="Delve.", llm=llm, max_llm_passes=2
            )
        )
        assert [e.type for e in events] == ["pass", "pass", "done"]

    async def test_max_passes_caps_iteration(self, monkeypatch) -> None:
        monkeypatch.setattr(slop_scorer, "score_text", _scores_by_prefix({}, 30))
        llm = FakeListChatModel(responses=["One.", "Two.", "Three."])
        events = await _collect(
            stream_humanization(
                section_index=0, title="S", markdown="Delve.", llm=llm, max_llm_passes=2
            )
        )
        assert [e.type for e in events] == ["pass", "pass", "pass", "done"]

    async def test_stops_when_llm_pass_changes_nothing(self, monkeypatch) -> None:
        monkeypatch.setattr(slop_scorer, "score_text", _scores_by_prefix({}, 30))
        llm = FakeListChatModel(responses=["Delve.", "Delve."])
        events = await _collect(
            stream_humanization(
                section_index=0, title="S", markdown="Delve.", llm=llm, max_llm_passes=2
            )
        )
        assert [e.type for e in events] == ["pass", "pass", "done"]
        assert events[1].data["changed"] is False

    async def test_llm_failure_emits_error_and_stops(self, monkeypatch) -> None:
        monkeypatch.setattr(slop_scorer, "score_text", _scores_by_prefix({}, 30))

        class _Boom(FakeListChatModel):
            async def ainvoke(self, *a, **k):  # type: ignore[override]
                raise RuntimeError("llm down")

        events = await _collect(
            stream_humanization(
                section_index=0, title="S", markdown="Delve.",
                llm=_Boom(responses=["x"]), max_llm_passes=2,
            )
        )
        assert [e.type for e in events] == ["pass", "error"]
        assert "llm down" in str(events[-1].data["message"])

    def test_to_sse_frame_shape(self) -> None:
        frame = HumanizeEvent(type="pass", data={"index": 0}).to_sse()
        assert frame.startswith("event: pass\ndata: ")
        assert frame.endswith("\n\n")
        assert json.loads(frame.split("data: ", 1)[1]) == {"index": 0}


class TestSettings:
    def test_default_max_passes(self) -> None:
        from src.config.settings import Settings

        assert Settings(_env_file=None).humanize_preview_max_passes == 2  # type: ignore[call-arg]
```

- [x] **Step 2: Run to verify they fail**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/content/test_humanize_stream.py -q`
Expected: import error.

- [x] **Step 3: Implement**

`src/config/settings.py` — after `length_budgets_json`:

```python
    # AUTHOR-009: max LLM rewrite passes in the streaming humanize preview
    # (mechanical pass always runs first; loop stops early at score >= 70
    # or when a pass changes nothing). The pipeline node stays single-pass.
    humanize_preview_max_passes: int = 2
```

`src/services/content/humanize_stream.py`:

```python
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
        section_index=index, title=title, body_markdown=text,
        word_count=len(text.split()), citations_used=[],
    )


def _pass_event(
    index: int, name: str, scores: tuple[SlopScore, SlopScore], *,
    changed: bool, model: str | None,
) -> HumanizeEvent:
    before, after = scores
    return HumanizeEvent("pass", {
        "index": index, "name": name, "score_before": before.score,
        "score_after": after.score, "rating": after.rating,
        "changed": changed, "model": model,
    })


async def _llm_pass(draft: SectionDraft, score: SlopScore, llm: BaseChatModel) -> SectionDraft:
    rewritten = await rewrite_section(draft, score, llm)
    return _draft(draft.section_index, draft.title, fix_mechanical(rewritten.body_markdown))


def _done_event(
    original: SectionDraft, final: SectionDraft, scores: tuple[SlopScore, SlopScore],
    *, passes: int, llm_calls: int, model: str | None,
) -> HumanizeEvent:
    return HumanizeEvent("done", {
        "original": original.body_markdown, "rewritten": final.body_markdown,
        "diff": [op.to_dict() for op in diff_words(original.body_markdown, final.body_markdown)],
        "segments": [s.to_dict() for s in segment_sentences(original.body_markdown, final.body_markdown)],
        "passes": passes, "llm_called": llm_calls > 0, "model": model,
        "score_before": scores[0].score, "score_after": scores[1].score,
    })


async def stream_humanization(
    *, section_index: int, title: str, markdown: str,
    llm: BaseChatModel, max_llm_passes: int,
) -> AsyncIterator[HumanizeEvent]:
    """Yield one `pass` per humanization pass, then `done` (or `error`)."""
    original = _draft(section_index, title, markdown)
    score_orig = score_section(original)
    current = _draft(section_index, title, fix_mechanical(markdown))
    score = score_section(current)
    yield _pass_event(0, "mechanical", (score_orig, score),
                      changed=current.body_markdown != markdown, model=None)
    passes, llm_calls, model = 1, 0, None
    try:
        while score.score < REWRITE_THRESHOLD and llm_calls < max_llm_passes:
            nxt = await _llm_pass(current, score, llm)
            llm_calls += 1
            model = model_label(llm)
            changed = nxt.body_markdown != current.body_markdown
            score_next = score_section(nxt)
            yield _pass_event(passes, "llm", (score, score_next), changed=changed, model=model)
            passes += 1
            current, score = nxt, score_next
            if not changed:
                break
    except Exception as exc:  # noqa: BLE001 — surface to the client, never crash the stream
        logger.warning("humanize_stream_failed", section_index=section_index, error=str(exc))
        yield HumanizeEvent("error", {"message": str(exc)})
        return
    logger.info("humanize_stream_done", section_index=section_index,
                passes=passes, llm_calls=llm_calls, score_after=score.score)
    yield _done_event(original, current, (score_orig, score),
                      passes=passes, llm_calls=llm_calls, model=model)


__all__ = ["HumanizeEvent", "stream_humanization"]
```

Note the `passes` counter counts *all* passes (mechanical + LLM) — matches the test expectations (`passes == 1` for clean text, `3` for two LLM passes). If a helper exceeds 20 lines under `ruff format`, split `_done_event`'s dict into a `_done_payload()` helper.

- [x] **Step 4: Run to verify they pass**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/content/test_humanize_stream.py tests/unit/services/content/test_humanize_preview.py -q`
Expected: all pass (existing preview tests untouched).

- [x] **Step 5: Commit**

```bash
git add src/services/content/humanize_stream.py src/config/settings.py tests/unit/services/content/test_humanize_stream.py
git commit -m "feat(content): multi-pass streaming humanization service (AUTHOR-009)"
```

---

### Task 3: `POST /content/humanize-preview/stream` endpoint

**Files:**
- Create: `src/api/routers/content_humanize_stream.py`, `tests/unit/api/test_content_humanize_stream_endpoint.py`
- Modify: `src/api/main.py`

**Interfaces:**
- Consumes: `stream_humanization` (Task 2), `_get_content_llm` (re-exported from `src.api.routers.content`), `parse_section_id` (`section_history_contracts`), `require_editor_or_above`, `limiter`.
- Produces: request `HumanizeStreamRequest {section_id: str (3..80), title: str = "Section" (≤200), current_markdown: str (1..20000)}` — **`current_markdown` is required** (the panel always has it; this keeps the stream free of the history service). Response: `text/event-stream` with `pass`/`done`/`error` frames; stops on client disconnect. Router variable `content_humanize_stream_router`.

- [x] **Step 1: Write the failing tests** — `tests/unit/api/test_content_humanize_stream_endpoint.py`:

```python
"""AUTHOR-009 — POST-SSE humanize stream endpoint."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content import slop_scorer
from src.api.main import create_app
from src.config.settings import Settings
from src.models.content_pipeline import SlopScore
from tests.unit.api.conftest import make_auth_header

from .test_content_endpoints import _PRIV, _PUB

SECTION_ID = "11111111-1111-1111-1111-111111111111:0"


@pytest.fixture
def stream_settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        jwt_private_key=_PRIV,
        jwt_public_key=_PUB,
        anthropic_api_key="test-anthropic",
        database_url="",
    )


@pytest.fixture
def stream_app(stream_settings: Settings) -> FastAPI:
    return create_app(stream_settings)


@pytest.fixture
async def stream_client(stream_app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=stream_app), base_url="http://test"
    ) as ac:
        yield ac


def _fake_score(text: str) -> SlopScore:
    score = 85 if text.startswith("Tighter") else 30
    return SlopScore(score=score, rating="x", violations=[], phrase_deductions=0, pattern_deductions=0)


async def _frames(resp: httpx.Response) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    event = "message"
    async for line in resp.aiter_lines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            out.append((event, json.loads(line[5:].strip())))
    return out


class TestHumanizeStreamEndpoint:
    async def test_streams_pass_events_then_done(
        self, stream_client: httpx.AsyncClient, stream_settings: Settings
    ) -> None:
        llm = FakeListChatModel(responses=["Tighter rewrite."])
        with (
            patch("src.api.routers.content_humanize_stream._get_content_llm", return_value=llm),
            patch.object(slop_scorer, "score_text", _fake_score),
        ):
            async with stream_client.stream(
                "POST",
                "/api/v1/content/humanize-preview/stream",
                json={"section_id": SECTION_ID, "current_markdown": "Delve into it."},
                headers=make_auth_header("editor", stream_settings),
            ) as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("text/event-stream")
                frames = await _frames(resp)
        types = [t for t, _ in frames]
        assert types == ["pass", "pass", "done"]
        done = frames[-1][1]
        assert done["rewritten"].startswith("Tighter")
        assert done["segments"] and done["diff"]
        assert done["llm_called"] is True

    async def test_requires_editor(
        self, stream_client: httpx.AsyncClient, stream_settings: Settings
    ) -> None:
        resp = await stream_client.post(
            "/api/v1/content/humanize-preview/stream",
            json={"section_id": SECTION_ID, "current_markdown": "hi"},
            headers=make_auth_header("viewer", stream_settings),
        )
        assert resp.status_code == 403

    async def test_requires_auth(self, stream_client: httpx.AsyncClient) -> None:
        resp = await stream_client.post(
            "/api/v1/content/humanize-preview/stream",
            json={"section_id": SECTION_ID, "current_markdown": "hi"},
        )
        assert resp.status_code == 401

    async def test_bad_section_id_is_400(
        self, stream_client: httpx.AsyncClient, stream_settings: Settings
    ) -> None:
        resp = await stream_client.post(
            "/api/v1/content/humanize-preview/stream",
            json={"section_id": "not-a-section-id", "current_markdown": "hi"},
            headers=make_auth_header("editor", stream_settings),
        )
        assert resp.status_code == 400

    async def test_rate_limited_after_20(
        self, stream_client: httpx.AsyncClient, stream_settings: Settings
    ) -> None:
        headers = make_auth_header("editor", stream_settings)
        body = {"section_id": "not-a-section-id", "current_markdown": "hi"}
        for _ in range(20):
            await stream_client.post("/api/v1/content/humanize-preview/stream", json=body, headers=headers)
        resp = await stream_client.post("/api/v1/content/humanize-preview/stream", json=body, headers=headers)
        assert resp.status_code == 429
```

Confirm `_PRIV`/`_PUB` are the module-level key names in `test_content_endpoints.py` (line ~80 shows `jwt_private_key=_PRIV`); if they are named differently, import the actual names. The rate-limit test relies on the `reset_rate_limiter` autouse fixture in `tests/unit/api/conftest.py`.

- [x] **Step 2: Run to verify they fail**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_content_humanize_stream_endpoint.py -q`
Expected: 404s / import error on the router module.

- [x] **Step 3: Implement** — `src/api/routers/content_humanize_stream.py`:

```python
"""AUTHOR-009 — POST-SSE endpoint for the multi-pass humanize preview.

Kept in its own module (content.py is already over the line budget).
Preview-only: the client stages the resolved markdown through
`/content/section-update`, which runs the anchor validator.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.rate_limiter import limiter
from src.api.routers.content import _get_content_llm
from src.services.content.humanize_stream import stream_humanization
from src.services.content.section_history_contracts import parse_section_id

content_humanize_stream_router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


class HumanizeStreamRequest(BaseModel):
    section_id: str = Field(min_length=3, max_length=80)
    title: str = Field(default="Section", max_length=200)
    current_markdown: str = Field(min_length=1, max_length=20000)


def _section_index_or_400(section_id: str) -> int:
    try:
        return parse_section_id(section_id)[1]
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


# Route decorator OUTERMOST or slowapi never evaluates the limit (AUTHOR-006).
@content_humanize_stream_router.post(
    "/content/humanize-preview/stream",
    summary="Stream a multi-pass humanization preview (SSE)",
)
@limiter.limit("20/minute")
async def humanize_preview_stream(
    request: Request,
    body: HumanizeStreamRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> StreamingResponse:
    section_index = _section_index_or_400(body.section_id)
    llm = _get_content_llm(request)
    max_passes = request.app.state.settings.humanize_preview_max_passes

    async def gen() -> AsyncIterator[str]:
        events = stream_humanization(
            section_index=section_index, title=body.title,
            markdown=body.current_markdown, llm=llm, max_llm_passes=max_passes,
        )
        async for event in events:
            if await request.is_disconnected():
                return
            yield event.to_sse()

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


__all__ = ["content_humanize_stream_router"]
```

`src/api/main.py` — add `from src.api.routers.content_humanize_stream import content_humanize_stream_router` next to the `content_regenerate_router` import, and in `_register_routers` right after the `content_regenerate_router` block:

```python
    app.include_router(
        content_humanize_stream_router,
        prefix=settings.api_v1_prefix,
        tags=["content"],
    )
```

- [x] **Step 4: Run to verify they pass**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_content_humanize_stream_endpoint.py tests/unit/api/test_content_endpoints.py -q`
Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/api/routers/content_humanize_stream.py src/api/main.py tests/unit/api/test_content_humanize_stream_endpoint.py
git commit -m "feat(api): POST-SSE /content/humanize-preview/stream (AUTHOR-009)"
```

---

### Task 4: POST support in the shared SSE consumer

**Files:**
- Modify: `frontend/src/lib/sse/consume-sse.ts`
- Test: `frontend/src/lib/sse/consume-sse.test.ts` (create if it does not exist; if it exists, append the two cases)

**Interfaces:**
- Produces: `ConsumeSseOptions` gains `method?: "GET" | "POST"` (default `"GET"`) and `body?: unknown` (JSON-serialised; sets `Content-Type: application/json`). GET behaviour byte-identical.

- [x] **Step 1: Failing test** — `frontend/src/lib/sse/consume-sse.test.ts` (new file, or append the `describe` block):

```ts
import { describe, expect, it, vi, afterEach } from "vitest";
import { consumeSse } from "./consume-sse";

function sseResponse(frames: string): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(frames));
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

describe("consumeSse POST support", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("POSTs a JSON body and dispatches frames", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse('event: pass\ndata: {"index":0}\n\nevent: done\ndata: {"ok":true}\n\n'),
    );
    vi.stubGlobal("fetch", fetchMock);
    const events: Array<[string, unknown]> = [];
    await consumeSse("http://api/x", {
      method: "POST",
      body: { section_id: "a:0" },
      token: "T",
      onEvent: (t, d) => events.push([t, d]),
    });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ section_id: "a:0" }));
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.headers.Authorization).toBe("Bearer T");
    expect(events).toEqual([["pass", { index: 0 }], ["done", { ok: true }]]);
  });

  it("defaults to GET with no body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseResponse("event: a\ndata: 1\n\n"));
    vi.stubGlobal("fetch", fetchMock);
    await consumeSse("http://api/y", { onEvent: () => {} });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method ?? "GET").toBe("GET");
    expect(init.body).toBeUndefined();
  });
});
```

Run: `cd frontend && npx vitest run src/lib/sse/consume-sse.test.ts` → the POST case fails (`init.method` undefined / body missing).

- [x] **Step 2: Implement** — in `consume-sse.ts`:

```ts
export interface ConsumeSseOptions {
  token?: string | null;
  signal?: AbortSignal;
  method?: "GET" | "POST";
  body?: unknown;
  onEvent: (type: string, data: unknown) => void;
}
```

and in `consumeSse` replace the `fetch(...)` call:

```ts
    const init: RequestInit = { headers, signal: opts.signal, credentials: "include" };
    if (opts.method === "POST") {
      init.method = "POST";
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.body ?? {});
    }
    const res = await fetch(url, init);
```

- [x] **Step 3: Verify**

Run: `cd frontend && npx vitest run src/lib/sse src/hooks/use-session-events.test.tsx`
Expected: pass (GET path unchanged).

- [x] **Step 4: Commit**

```bash
git add frontend/src/lib/sse/consume-sse.ts frontend/src/lib/sse/consume-sse.test.ts
git commit -m "feat(frontend): POST support in the shared SSE consumer (AUTHOR-009)"
```

---

### Task 5: Types, URL helper, and pure segment resolver

**Files:**
- Create: `frontend/src/lib/content/resolve-segments.ts`, `frontend/src/lib/content/resolve-segments.test.ts`
- Modify: `frontend/src/types/content.ts`, `frontend/src/lib/api/content.ts`

**Interfaces:**
- `types/content.ts` adds:
  ```ts
  export interface HumanizeSegment { id: string; kind: "equal" | "change"; before: string; after: string; ops: WordDiffEntry[] }
  export interface HumanizePassEvent { index: number; name: "mechanical" | "llm"; score_before: number; score_after: number; rating: string; changed: boolean; model: string | null }
  export interface HumanizeDoneEvent { original: string; rewritten: string; diff: WordDiffEntry[]; segments: HumanizeSegment[]; passes: number; llm_called: boolean; model: string | null; score_before: number; score_after: number }
  export interface HumanizeStreamRequest { section_id: string; title?: string; current_markdown: string }
  ```
- `lib/api/content.ts` adds `export function humanizeStreamUrl(): string { return \`${apiClient.defaults.baseURL}/content/humanize-preview/stream\`; }`.
- `resolve-segments.ts` exports `resolveSegments(segments: HumanizeSegment[], rejected: ReadonlySet<string>): string` and `changeIds(segments): string[]`.

- [x] **Step 1: Failing test** — `resolve-segments.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { changeIds, resolveSegments } from "./resolve-segments";
import type { HumanizeSegment } from "@/types/content";

const SEGS: HumanizeSegment[] = [
  { id: "s0", kind: "equal", before: "A. ", after: "A. ", ops: [] },
  { id: "s1", kind: "change", before: "Old.", after: "New.", ops: [] },
  { id: "s2", kind: "equal", before: " C. ", after: " C. ", ops: [] },
  { id: "s3", kind: "change", before: "Older.", after: "Newer.", ops: [] },
];

describe("resolveSegments", () => {
  it("returns the final text when nothing is rejected", () => {
    expect(resolveSegments(SEGS, new Set())).toBe("A. New. C. Newer.");
  });
  it("restores rejected change segments", () => {
    expect(resolveSegments(SEGS, new Set(["s1"]))).toBe("A. Old. C. Newer.");
    expect(resolveSegments(SEGS, new Set(["s1", "s3"]))).toBe("A. Old. C. Older.");
  });
  it("changeIds lists only change segments in order", () => {
    expect(changeIds(SEGS)).toEqual(["s1", "s3"]);
  });
});
```

Run: `cd frontend && npx vitest run src/lib/content/resolve-segments.test.ts` → FAIL (module missing).

- [x] **Step 2: Implement**

`resolve-segments.ts`:

```ts
import type { HumanizeSegment } from "@/types/content";

/** Rebuild markdown from per-segment decisions (AUTHOR-009). Mirrors
 *  `src/services/content/sentence_segments.resolve_segments`. */
export function resolveSegments(
  segments: HumanizeSegment[],
  rejected: ReadonlySet<string>,
): string {
  return segments
    .map((s) => (s.kind === "change" && rejected.has(s.id) ? s.before : s.after))
    .join("");
}

export function changeIds(segments: HumanizeSegment[]): string[] {
  return segments.filter((s) => s.kind === "change").map((s) => s.id);
}
```

Add the four interfaces to `types/content.ts` (next to `HumanizePreviewResponse`) and `humanizeStreamUrl` to `lib/api/content.ts` (next to `previewHumanization`).

- [x] **Step 3: Verify** — `cd frontend && npx vitest run src/lib/content && npx tsc --noEmit 2>&1 | grep -c "error TS"` → tests pass; tsc count = 13 (baseline).

- [x] **Step 4: Commit**

```bash
git add frontend/src/lib/content/resolve-segments.ts frontend/src/lib/content/resolve-segments.test.ts frontend/src/types/content.ts frontend/src/lib/api/content.ts
git commit -m "feat(frontend): humanize stream types + segment resolver (AUTHOR-009)"
```

---

### Task 6: `useHumanizeStream` hook

**Files:**
- Create: `frontend/src/hooks/use-humanize-stream.ts`, `frontend/src/hooks/use-humanize-stream.test.tsx`

**Interfaces:**
- Consumes: `consumeSse` (Task 4), `humanizeStreamUrl`, `getAccessToken`, `resolveSegments`/`changeIds` (Task 5).
- Produces:
  ```ts
  export type HumanizeStreamStatus = "idle" | "streaming" | "done" | "error";
  export function useHumanizeStream(args: { sectionId: string; currentMarkdown: string }) => {
    status; passes: HumanizePassEvent[]; done: HumanizeDoneEvent | null; error: string | null;
    rejected: ReadonlySet<string>; resolvedMarkdown: string | null;
    run(): void; cancel(): void; reset(): void;
    toggle(id: string): void; acceptAll(): void; rejectAll(): void;
  }
  ```
- Rules: `run()` aborts any in-flight stream, clears state, POSTs `{section_id, current_markdown}`; `pass` events append; `done` sets `done`, `status="done"`, `rejected = ∅` (all accepted); `error` event or thrown error → `status="error"`; stream ending without `done` → `error: "Stream ended early"`; `cancel()` aborts and returns to `idle`; unmount aborts.

- [x] **Step 1: Failing test** — `use-humanize-stream.test.tsx`:

```tsx
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const consume = vi.fn();
vi.mock("@/lib/sse/consume-sse", () => ({ consumeSse: (...a: unknown[]) => consume(...a) }));
vi.mock("@/lib/api/client", () => ({
  getAccessToken: () => "T",
  apiClient: { defaults: { baseURL: "http://api/api/v1" } },
}));

import { useHumanizeStream } from "./use-humanize-stream";

const DONE = {
  original: "A. Old.", rewritten: "A. New.", diff: [], passes: 2, llm_called: true,
  model: "claude", score_before: 30, score_after: 85,
  segments: [
    { id: "s0", kind: "equal" as const, before: "A. ", after: "A. ", ops: [] },
    { id: "s1", kind: "change" as const, before: "Old.", after: "New.", ops: [] },
  ],
};

let emit!: (t: string, d: unknown) => void;
let finish!: () => void;

beforeEach(() => {
  consume.mockReset();
  consume.mockImplementation(async (_url: string, o: { onEvent: typeof emit }) => {
    emit = o.onEvent;
    await new Promise<void>((resolve) => {
      finish = resolve;
    });
  });
});

describe("useHumanizeStream", () => {
  it("POSTs to the stream url and accumulates pass events", async () => {
    const { result } = renderHook(() =>
      useHumanizeStream({ sectionId: "a:0", currentMarkdown: "A. Old." }),
    );
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    const [url, opts] = consume.mock.calls[0];
    expect(url).toBe("http://api/api/v1/content/humanize-preview/stream");
    expect(opts.method).toBe("POST");
    expect(opts.body).toEqual({ section_id: "a:0", current_markdown: "A. Old." });
    expect(opts.token).toBe("T");
    act(() => emit("pass", { index: 0, name: "mechanical", score_before: 30, score_after: 32, rating: "x", changed: false, model: null }));
    act(() => emit("pass", { index: 1, name: "llm", score_before: 32, score_after: 85, rating: "y", changed: true, model: "claude" }));
    expect(result.current.status).toBe("streaming");
    expect(result.current.passes).toHaveLength(2);
  });

  it("done → all changes accepted; toggle/rejectAll/acceptAll drive resolvedMarkdown", async () => {
    const { result } = renderHook(() =>
      useHumanizeStream({ sectionId: "a:0", currentMarkdown: "A. Old." }),
    );
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() => emit("done", DONE));
    act(() => finish());
    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.resolvedMarkdown).toBe("A. New.");
    act(() => result.current.toggle("s1"));
    expect(result.current.resolvedMarkdown).toBe("A. Old.");
    act(() => result.current.acceptAll());
    expect(result.current.resolvedMarkdown).toBe("A. New.");
    act(() => result.current.rejectAll());
    expect(result.current.rejected.has("s1")).toBe(true);
  });

  it("error event sets status=error with the message", async () => {
    const { result } = renderHook(() =>
      useHumanizeStream({ sectionId: "a:0", currentMarkdown: "A." }),
    );
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() => emit("error", { message: "llm down" }));
    act(() => finish());
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error).toBe("llm down");
  });

  it("stream ending without done is an error", async () => {
    const { result } = renderHook(() =>
      useHumanizeStream({ sectionId: "a:0", currentMarkdown: "A." }),
    );
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() => finish());
    await waitFor(() => expect(result.current.status).toBe("error"));
  });

  it("cancel aborts the stream and returns to idle", async () => {
    const { result } = renderHook(() =>
      useHumanizeStream({ sectionId: "a:0", currentMarkdown: "A." }),
    );
    act(() => result.current.run());
    await waitFor(() => expect(consume).toHaveBeenCalled());
    const opts = consume.mock.calls[0][1] as { signal: AbortSignal };
    act(() => result.current.cancel());
    expect(opts.signal.aborted).toBe(true);
    expect(result.current.status).toBe("idle");
  });
});
```

Run: `cd frontend && npx vitest run src/hooks/use-humanize-stream.test.tsx` → FAIL (module missing).

- [x] **Step 2: Implement** — `use-humanize-stream.ts`:

```ts
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getAccessToken } from "@/lib/api/client";
import { humanizeStreamUrl } from "@/lib/api/content";
import { changeIds, resolveSegments } from "@/lib/content/resolve-segments";
import { consumeSse } from "@/lib/sse/consume-sse";
import type { HumanizeDoneEvent, HumanizePassEvent } from "@/types/content";

export type HumanizeStreamStatus = "idle" | "streaming" | "done" | "error";

export interface UseHumanizeStreamArgs {
  sectionId: string;
  currentMarkdown: string;
}

interface StreamState {
  status: HumanizeStreamStatus;
  passes: HumanizePassEvent[];
  done: HumanizeDoneEvent | null;
  error: string | null;
}

const IDLE: StreamState = { status: "idle", passes: [], done: null, error: null };

/** Drives `POST /content/humanize-preview/stream` (AUTHOR-009). */
export function useHumanizeStream({ sectionId, currentMarkdown }: UseHumanizeStreamArgs) {
  const [state, setState] = useState<StreamState>(IDLE);
  const [rejected, setRejected] = useState<ReadonlySet<string>>(new Set());
  const controller = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
    setState(IDLE);
    setRejected(new Set());
  }, []);

  useEffect(() => () => controller.current?.abort(), []);

  const onEvent = useCallback((type: string, data: unknown) => {
    if (type === "pass") {
      setState((s) => ({ ...s, passes: [...s.passes, data as HumanizePassEvent] }));
    } else if (type === "done") {
      setRejected(new Set());
      setState((s) => ({ ...s, status: "done", done: data as HumanizeDoneEvent }));
    } else if (type === "error") {
      const msg = (data as { message?: string })?.message ?? "Humanize failed";
      setState((s) => ({ ...s, status: "error", error: msg }));
    }
  }, []);

  const run = useCallback(() => {
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setRejected(new Set());
    setState({ ...IDLE, status: "streaming" });
    consumeSse(humanizeStreamUrl(), {
      method: "POST",
      body: { section_id: sectionId, current_markdown: currentMarkdown },
      token: getAccessToken(),
      signal: ctrl.signal,
      onEvent,
    })
      .then(() => {
        if (ctrl.signal.aborted) return;
        setState((s) => (s.status === "streaming" ? { ...s, status: "error", error: "Stream ended early" } : s));
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        const msg = err instanceof Error ? err.message : "Humanize failed";
        setState((s) => ({ ...s, status: "error", error: msg }));
      });
  }, [sectionId, currentMarkdown, onEvent]);

  const toggle = useCallback((id: string) => {
    setRejected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);
  const acceptAll = useCallback(() => setRejected(new Set()), []);
  const rejectAll = useCallback(
    () => setRejected(new Set(state.done ? changeIds(state.done.segments) : [])),
    [state.done],
  );

  const resolvedMarkdown = useMemo(
    () => (state.done ? resolveSegments(state.done.segments, rejected) : null),
    [state.done, rejected],
  );

  return { ...state, rejected, resolvedMarkdown, run, cancel, reset: cancel, toggle, acceptAll, rejectAll };
}
```

If the file lands over 200 lines after formatting, move `onEvent`'s reducer logic into `lib/content/humanize-stream-reducer.ts` (pure `applyHumanizeEvent(state, type, data)`).

- [x] **Step 3: Verify** — `cd frontend && npx vitest run src/hooks/use-humanize-stream.test.tsx` → 5 passed.

- [x] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-humanize-stream.ts frontend/src/hooks/use-humanize-stream.test.tsx
git commit -m "feat(frontend): useHumanizeStream hook (AUTHOR-009)"
```

---

### Task 7: Panel — pass tiles + change list + streaming wiring

**Files:**
- Create: `frontend/src/components/article/HumanizePassTiles.tsx`, `frontend/src/components/article/HumanizeChangeList.tsx`
- Modify: `frontend/src/components/article/HumanizationDiffPanel.tsx`, `frontend/src/components/article/HumanizationDiffPanel.test.tsx`

**Interfaces:**
- `HumanizePassTiles({ passes, streaming }: { passes: HumanizePassEvent[]; streaming: boolean })` — one tile per pass (`data-testid="humanize-pass-tile"`): label (`Mechanical` / `LLM pass N`), `score_before → score_after`, `changed ? "changed" : "no change"`, model when present; a pulsing placeholder tile (`data-testid="humanize-pass-pending"`) while `streaming`.
- `HumanizeChangeList({ segments, rejected, onToggle, onAcceptAll, onRejectAll })` — renders only `kind === "change"` segments; each row (`data-testid="humanize-change"`, `data-rejected="true|false"`) shows `<WordDiffView ops={segment.ops} />` and a toggle button (`data-testid="toggle-change-{id}"`, label `Reject` when accepted / `Accept` when rejected); header shows `N of M changes accepted` with `Accept all` / `Reject all` buttons (`data-testid="accept-all-changes"` / `"reject-all-changes"`); empty state text `No sentence changes — mechanical fixes only.` when there are zero change segments.
- `HumanizationDiffPanel` keeps its props (`sectionId, currentMarkdown, onAccept, onCancel, className`) and test ids (`run-humanize`, `accept-humanize`, `reject-humanize`, `humanize-score-badges`); it now uses `useHumanizeStream`; `onAccept(resolvedMarkdown)`; `Reject` = `reset()`; `Close` = `cancel()` then `onCancel?.()`; while streaming the Run button reads `Humanizing… (pass N)` and a `Cancel` button (`data-testid="cancel-humanize"`) is shown. Score badges show `done.score_before → done.score_after`. **`WordDiffView` for the whole text is no longer rendered** — the per-change diffs replace it (existing `word-diff-view` test id still appears inside each change row).

- [x] **Step 1: Rewrite the panel test** — replace `HumanizationDiffPanel.test.tsx` with:

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, act } from "@testing-library/react";

const consume = vi.fn();
vi.mock("@/lib/sse/consume-sse", () => ({ consumeSse: (...a: unknown[]) => consume(...a) }));
vi.mock("@/lib/api/client", () => ({
  getAccessToken: () => "T",
  apiClient: { defaults: { baseURL: "http://api/api/v1" } },
}));

import { HumanizationDiffPanel } from "./HumanizationDiffPanel";

const PASS0 = { index: 0, name: "mechanical", score_before: 35, score_after: 40, rating: "SUSPICIOUS", changed: true, model: null };
const PASS1 = { index: 1, name: "llm", score_before: 40, score_after: 85, rating: "CLEAN", changed: true, model: "claude" };
const DONE = {
  original: "Old wordy paragraph. Keep me.",
  rewritten: "Tighter paragraph. Keep me.",
  diff: [],
  passes: 2, llm_called: true, model: "claude", score_before: 35, score_after: 85,
  segments: [
    { id: "s0", kind: "change", before: "Old wordy paragraph.", after: "Tighter paragraph.",
      ops: [{ kind: "replace", before: "Old wordy", after: "Tighter" }, { kind: "equal", before: " paragraph.", after: " paragraph." }] },
    { id: "s1", kind: "equal", before: " Keep me.", after: " Keep me.", ops: [] },
  ],
};

let emit!: (t: string, d: unknown) => void;
let finish!: () => void;

beforeEach(() => {
  consume.mockReset();
  consume.mockImplementation(async (_url: string, o: { onEvent: typeof emit }) => {
    emit = o.onEvent;
    await new Promise<void>((resolve) => { finish = resolve; });
  });
});

function setup() {
  const onAccept = vi.fn();
  const onCancel = vi.fn();
  render(
    <HumanizationDiffPanel
      sectionId="abc:1"
      currentMarkdown="Old wordy paragraph. Keep me."
      onAccept={onAccept}
      onCancel={onCancel}
    />,
  );
  return { onAccept, onCancel };
}

async function runToDone() {
  fireEvent.click(screen.getByTestId("run-humanize"));
  await waitFor(() => expect(consume).toHaveBeenCalled());
  act(() => emit("pass", PASS0));
  act(() => emit("pass", PASS1));
  act(() => emit("done", DONE));
  act(() => finish());
  await waitFor(() => screen.getByTestId("accept-humanize"));
}

describe("HumanizationDiffPanel (streaming)", () => {
  it("streams pass tiles as events arrive, then shows score badges", async () => {
    setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => expect(consume).toHaveBeenCalled());
    expect(screen.getByTestId("humanize-pass-pending")).toBeInTheDocument();
    act(() => emit("pass", PASS0));
    expect(screen.getAllByTestId("humanize-pass-tile")).toHaveLength(1);
    act(() => emit("pass", PASS1));
    expect(screen.getAllByTestId("humanize-pass-tile")).toHaveLength(2);
    act(() => emit("done", DONE));
    act(() => finish());
    await waitFor(() => expect(screen.getByTestId("humanize-score-badges")).toHaveTextContent("35"));
    expect(screen.queryByTestId("humanize-pass-pending")).not.toBeInTheDocument();
  });

  it("Accept emits the resolved markdown; rejecting a sentence restores it", async () => {
    const { onAccept } = setup();
    await runToDone();
    expect(screen.getAllByTestId("humanize-change")).toHaveLength(1);
    fireEvent.click(screen.getByTestId("accept-humanize"));
    expect(onAccept).toHaveBeenLastCalledWith("Tighter paragraph. Keep me.");
    fireEvent.click(screen.getByTestId("toggle-change-s0"));
    expect(screen.getByTestId("humanize-change")).toHaveAttribute("data-rejected", "true");
    fireEvent.click(screen.getByTestId("accept-humanize"));
    expect(onAccept).toHaveBeenLastCalledWith("Old wordy paragraph. Keep me.");
  });

  it("Reject all / Accept all flip every change", async () => {
    setup();
    await runToDone();
    fireEvent.click(screen.getByTestId("reject-all-changes"));
    expect(screen.getByTestId("humanize-change")).toHaveAttribute("data-rejected", "true");
    fireEvent.click(screen.getByTestId("accept-all-changes"));
    expect(screen.getByTestId("humanize-change")).toHaveAttribute("data-rejected", "false");
  });

  it("Reject clears the result and shows Run again", async () => {
    setup();
    await runToDone();
    fireEvent.click(screen.getByTestId("reject-humanize"));
    expect(screen.queryByTestId("humanize-change")).not.toBeInTheDocument();
    expect(screen.getByTestId("run-humanize")).toBeInTheDocument();
  });

  it("Cancel while streaming aborts and Close calls onCancel", async () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => expect(consume).toHaveBeenCalled());
    const opts = consume.mock.calls[0][1] as { signal: AbortSignal };
    fireEvent.click(screen.getByTestId("cancel-humanize"));
    expect(opts.signal.aborted).toBe(true);
    expect(screen.getByTestId("run-humanize")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Close"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("renders the error event", async () => {
    setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() => emit("error", { message: "boom" }));
    act(() => finish());
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("boom"));
  });
});
```

Run: `cd frontend && npx vitest run src/components/article/HumanizationDiffPanel.test.tsx` → FAIL (panel still calls `previewHumanization`).

- [x] **Step 2: Implement the two sub-components**

`HumanizePassTiles.tsx`:

```tsx
"use client";

import { cn } from "@/lib/utils";
import type { HumanizePassEvent } from "@/types/content";

/** One tile per humanization pass, streaming in (AUTHOR-009). */
export function HumanizePassTiles({
  passes,
  streaming,
}: {
  passes: HumanizePassEvent[];
  streaming: boolean;
}) {
  if (passes.length === 0 && !streaming) return null;
  return (
    <ol data-testid="humanize-pass-tiles" className="flex flex-wrap gap-2">
      {passes.map((p) => (
        <li
          key={p.index}
          data-testid="humanize-pass-tile"
          className="flex flex-col gap-0.5 rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-[11px]"
        >
          <span className="font-medium text-neutral-700">
            {p.name === "mechanical" ? "Mechanical" : `LLM pass ${p.index}`}
            {p.model ? ` · ${p.model}` : ""}
          </span>
          <span className="font-mono text-neutral-600">
            {p.score_before} → {p.score_after}
          </span>
          <span className={cn(p.changed ? "text-success" : "text-neutral-400")}>
            {p.changed ? "changed" : "no change"}
          </span>
        </li>
      ))}
      {streaming ? (
        <li
          data-testid="humanize-pass-pending"
          role="status"
          className="animate-pulse rounded-md border border-dashed border-warning/40 bg-warning-light/40 px-3 py-2 text-[11px] text-warning"
        >
          Running pass {passes.length}…
        </li>
      ) : null}
    </ol>
  );
}
```

`HumanizeChangeList.tsx`:

```tsx
"use client";

import { cn } from "@/lib/utils";
import type { HumanizeSegment } from "@/types/content";
import { WordDiffView } from "./WordDiffView";

export interface HumanizeChangeListProps {
  segments: HumanizeSegment[];
  rejected: ReadonlySet<string>;
  onToggle: (id: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
}

const PILL =
  "rounded-md px-2 py-1 text-[11px] font-medium hover:bg-neutral-200 bg-neutral-100 text-neutral-700";

/** Per-sentence accept/reject list (AUTHOR-009). Changes start accepted. */
export function HumanizeChangeList({
  segments,
  rejected,
  onToggle,
  onAcceptAll,
  onRejectAll,
}: HumanizeChangeListProps) {
  const changes = segments.filter((s) => s.kind === "change");
  if (changes.length === 0) {
    return (
      <p className="text-xs text-neutral-500">No sentence changes — mechanical fixes only.</p>
    );
  }
  const accepted = changes.length - changes.filter((c) => rejected.has(c.id)).length;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-[11px] text-neutral-500">
        <span>
          {accepted} of {changes.length} changes accepted
        </span>
        <span className="flex gap-1">
          <button type="button" onClick={onAcceptAll} data-testid="accept-all-changes" className={PILL}>
            Accept all
          </button>
          <button type="button" onClick={onRejectAll} data-testid="reject-all-changes" className={PILL}>
            Reject all
          </button>
        </span>
      </div>
      <ul className="flex flex-col gap-2">
        {changes.map((c) => {
          const isRejected = rejected.has(c.id);
          return (
            <li
              key={c.id}
              data-testid="humanize-change"
              data-rejected={isRejected ? "true" : "false"}
              className={cn(
                "flex flex-col gap-1 rounded-md border p-2",
                isRejected ? "border-neutral-200 opacity-60" : "border-success/40",
              )}
            >
              <WordDiffView ops={c.ops} ariaLabel={`Change ${c.id}`} />
              <button
                type="button"
                onClick={() => onToggle(c.id)}
                data-testid={`toggle-change-${c.id}`}
                className={cn(PILL, "self-end")}
              >
                {isRejected ? "Accept" : "Reject"}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
```

- [x] **Step 3: Rewrite `HumanizationDiffPanel.tsx`** — keep the header (`Wand2`, title, `ScoreBadgePair` when `done`), replace the body:

```tsx
  const stream = useHumanizeStream({ sectionId, currentMarkdown });
  const streaming = stream.status === "streaming";

  function handleAccept() {
    if (stream.resolvedMarkdown !== null) onAccept(stream.resolvedMarkdown);
  }
  function handleClose() {
    stream.cancel();
    onCancel?.();
  }
```

Body order: error `<p role="alert">` (when `stream.error`), `<HumanizePassTiles passes={stream.passes} streaming={streaming} />`, then when `stream.done`: `<HumanizeChangeList segments={stream.done.segments} rejected={stream.rejected} onToggle={stream.toggle} onAcceptAll={stream.acceptAll} onRejectAll={stream.rejectAll} />` + the existing `llm_called` hint line (reads `stream.done.llm_called` / `stream.done.model`, plus `· ${stream.done.passes} passes`); otherwise the existing intro paragraph. Footer: `Close` → `handleClose`; when `streaming` a `Cancel` button (`data-testid="cancel-humanize"`, `onClick={stream.cancel}`); when `stream.done` the `Reject` (`stream.reset`) + `Accept` (`handleAccept`) pair; otherwise `Run humanizer` (`stream.run`, disabled when `streaming || !currentMarkdown.trim()`, label `Humanizing… (pass ${stream.passes.length})` while streaming). Drop the `previewHumanization` import and `PanelState`. Keep `ScoreBadgePair` in this file.

- [x] **Step 4: Verify**

Run: `cd frontend && npx vitest run src/components/article src/file-size-budget.test.ts && wc -l src/components/article/HumanizationDiffPanel.tsx src/components/article/HumanizePassTiles.tsx src/components/article/HumanizeChangeList.tsx`
Expected: all pass (incl. `SectionEditingWorkbench.test.tsx`, which must not need changes — it only checks the panel mounts); each file ≤ 200 lines.

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/article/HumanizationDiffPanel.tsx frontend/src/components/article/HumanizationDiffPanel.test.tsx frontend/src/components/article/HumanizePassTiles.tsx frontend/src/components/article/HumanizeChangeList.tsx
git commit -m "feat(frontend): streaming humanize panel with per-sentence accept/reject (AUTHOR-009)"
```

---

### Task 8: Full verification, live smoke, docs, PR

**Files:**
- Modify: `project-management/PROGRESS.md`, `project-management/BACKLOG.md`, `CLAUDE.md`, this plan

- [x] **Step 1: Backend gates** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/ -q` (≥ 1771 + ~25 new, 0 failures); `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`; `uv run mypy src/ --ignore-missing-imports 2>&1 | tail -1` — no new errors in touched files (baseline 116 in the worktree venv / 114 on develop's venv; the delta is `types-markdown`).

- [x] **Step 2: Frontend gates** — `cd frontend && npx vitest run && npm run lint && npx tsc --noEmit 2>&1 | grep -c "error TS"` → all green, 0 eslint errors, tsc = 13.

- [x] **Step 3: Live smoke** — the Docker stack is down; run the API in-process as in INFRA-008 (`COGNIFY_DATABASE_URL= COGNIFY_DEBUG=true uv run uvicorn src.api.main:app --port 8011 --env-file D:/Workbench/github/cognify/.env` — **with the real Anthropic key from `.env`**, do NOT blank it) and `curl -N -X POST …/content/humanize-preview/stream` with an editor token and a sloppy paragraph (`"Let me delve into this. It's important to note that…"`): expect ≥ 2 `pass` frames, a `done` frame whose `segments` round-trip (`"".join(before) == input`), and `passes ≤ 3`. Then run the frontend dev server against it (`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8011/api/v1 npm run dev`), open an article, Humanize prose → tiles stream in → untick one sentence → Accept → Save → confirm the saved section keeps the original sentence and `/content/section/{id}/history` shows a `manual` version (that is the anchors-intact round-trip through `section-update`). Record scores/pass counts in PROGRESS.

- [x] **Step 4: Docs** — PROGRESS.md: Epic 11 row → Done; RESUME block item 11 (what shipped, `COGNIFY_HUMANIZE_PREVIEW_MAX_PASSES`, smoke numbers, follow-ups: learning loop #19, pipeline-node multi-pass, migrate JSON endpoint callers / retire `/humanize-preview` once nothing else uses it, `content.py` still > 200 lines); BACKLOG.md: AUTHOR-009 row DONE, summary counts (Done 11 / Remaining 6 / ~30 SP), velocity 396 SP; CLAUDE.md Current Status sentence + Next action (AUTHOR-010 or PUBLISH-002); tick this plan's boxes.

- [x] **Step 5: Commit + PR**

```bash
git add project-management/ CLAUDE.md docs/superpowers/plans/2026-08-28-author-009-humanize-stream.md
git commit -m "docs: AUTHOR-009 done — progress/backlog/CLAUDE status"
git push -u origin feature/AUTHOR-009-humanize-stream
gh pr create --base develop --title "AUTHOR-009: humanize per-pass streaming + sentence-level accept/reject" --body-file <scratchpad>/pr-body.md
```

PR body: summary of the four parts, the two design decisions (2 LLM passes; changes start accepted), test counts, smoke results, follow-ups, and the standard footer.

---

## Self-review

- **Spec coverage**: "streams ≥2 events" → Task 2 (`pass` per pass + `done`) + Task 3 endpoint test asserting `["pass","pass","done"]`; "score per pass" → `pass.score_before/score_after` + tiles (Task 7); "which sentences changed" → Task 1 segments; "accept/reject per change in HumanizationDiffPanel" → Tasks 6–7; "round-trips through `section-update` with anchors intact" → resolved markdown is staged into the existing editor → save path (unchanged) + Task 8 smoke step; iteration ceiling decision → `humanize_preview_max_passes` (Task 2); default-accepted decision → hook `done` handler clears `rejected` (Task 6).
- **Placeholders**: none — every step has code or an exact edit; the `_PRIV/_PUB` import and the `.strip()` note are explicit "verify then use the real name" instructions, not TBDs.
- **Type consistency**: `Segment.to_dict()` keys (`id, kind, before, after, ops`) = `HumanizeSegment` fields; `pass` data keys = `HumanizePassEvent`; `done` data keys = `HumanizeDoneEvent`; `resolve_segments`/`resolveSegments` share semantics (rejected change → `before`); hook return names (`toggle`, `acceptAll`, `rejectAll`, `resolvedMarkdown`, `cancel`, `reset`, `run`) match Task 7 usage; test ids in Task 7 tests match the components.
