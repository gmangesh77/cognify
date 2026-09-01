"""Tests for the score_voice / fix_voice_deviations graph nodes (AUTHOR-011)."""

from __future__ import annotations

import structlog
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.pipeline import _extract_output
from src.agents.content.voice_nodes import (
    make_fix_voice_node,
    make_score_voice_node,
    make_voice_router,
)
from src.models.content_pipeline import SectionDraft
from src.models.persona import DimStat, VoiceFingerprint
from src.services.persona.fingerprint import DIMENSIONS, text_features
from src.services.persona.scoring import score_text

# A section that (by construction) matches its own fingerprint exactly —
# scores 100 no matter the threshold.
MATCH_TEXT = (
    "The team ships fast. Users see results daily. Small changes compound over "
    "time. This works well for us. The plan stays simple. Feedback drives every "
    "decision. We track outcomes closely. Results matter more than talk. The "
    "process stays lean. Teams move quickly here. Progress happens every week. "
    "Quality remains the top goal. The roadmap stays clear. New ideas ship "
    "weekly."
)  # 60 real words — must clear SHORT_SECTION_WORDS after a rewrite recomputes
# word_count from the actual rewritten body.

# Structurally opposite of MATCH_TEXT (long run-on sentences, semicolons,
# commas, first person, hedges, contractions, questions) — scores far below
# any reasonable threshold against a fingerprint built from MATCH_TEXT.
WEAK_TEXT = (
    "I think, perhaps, that we're clearly onto something absolutely remarkable "
    "here; isn't that fascinating? I'm not entirely sure, but I believe, quite "
    "honestly, that this approach, which I've been mulling over for weeks, might "
    "possibly, in some way, eventually work out; don't you think? I'm hopeful, "
    "cautiously, that we'll see results, although I could be wrong about several "
    "of these rather speculative assumptions, couldn't I? Honestly, I suspect, "
    "in my own humble opinion, that we're clearly making progress; wouldn't you "
    "agree, perhaps?"
)


def _fingerprint() -> VoiceFingerprint:
    feats = text_features(MATCH_TEXT)
    dims = {
        name: DimStat(
            mean=feats[name], stddev=max(0.5, abs(feats[name]) * 0.15), confidence=1.0
        )
        for name in DIMENSIONS
    }
    return VoiceFingerprint(dims=dims, sample_count=8)


def _section(index: int, title: str, body: str, word_count: int = 90) -> SectionDraft:
    # word_count is a plain int field, decoupled from actual token count —
    # SHORT_SECTION_WORDS gating only cares about this value.
    return SectionDraft(
        section_index=index,
        title=title,
        body_markdown=body,
        word_count=word_count,
        citations_used=[],
    )


class _CountingLLM:
    """Wraps a FakeListChatModel and counts `.ainvoke` calls.

    A plain FakeListChatModel is a pydantic model — its fields can't be
    monkeypatched with a Mock, so this thin duck-typed wrapper (the node
    only ever calls `.ainvoke`) is the simplest way to assert call counts.
    """

    def __init__(self, inner: FakeListChatModel) -> None:
        self.inner = inner
        self.call_count = 0

    async def ainvoke(self, messages: object) -> object:
        self.call_count += 1
        return await self.inner.ainvoke(messages)  # type: ignore[arg-type]


class _RaisingLLM:
    """A `.ainvoke` that always raises — for the never-fail-the-run tests."""

    async def ainvoke(self, messages: object) -> object:
        raise RuntimeError("llm boom")


class TestScoreVoiceNode:
    async def test_noop_without_fingerprint(self) -> None:
        node = make_score_voice_node()
        state = {"section_drafts": [_section(0, "A", MATCH_TEXT)], "status": "ok"}
        assert await node(state) == {}

    async def test_noop_when_status_failed(self) -> None:
        node = make_score_voice_node()
        state = {
            "section_drafts": [_section(0, "A", MATCH_TEXT)],
            "voice_fingerprint": _fingerprint(),
            "status": "failed",
        }
        assert await node(state) == {}

    async def test_scores_sections_and_overall(self) -> None:
        node = make_score_voice_node()
        fp = _fingerprint()
        state = {
            "section_drafts": [
                _section(0, "A", MATCH_TEXT),
                _section(1, "B", WEAK_TEXT),
            ],
            "voice_fingerprint": fp,
            "status": "ok",
        }
        result = await node(state)
        assert result["voice_scores_by_section"] == {
            "0": score_text(MATCH_TEXT, fp).score,
            "1": score_text(WEAK_TEXT, fp).score,
        }
        assert result["voice_match_score"] is not None

    async def test_node_level_exception_returns_empty_dict_and_logs(self) -> None:
        """Review item 4c: a malformed draft dict raises inside
        `_coerce_drafts`; the node must catch it, log, and return {}."""
        node = make_score_voice_node()
        state = {
            "section_drafts": [{"not": "a valid section draft"}],
            "voice_fingerprint": _fingerprint(),
            "status": "ok",
        }
        with structlog.testing.capture_logs() as logs:
            result = await node(state)
        assert result == {}
        failed = [e for e in logs if e["event"] == "voice_score_failed"]
        assert len(failed) == 1


class TestFixVoiceNode:
    async def test_rewrites_only_the_weak_section(self) -> None:
        fp = _fingerprint()
        llm = _CountingLLM(FakeListChatModel(responses=[MATCH_TEXT]))
        node = make_fix_voice_node(llm, 70)  # type: ignore[arg-type]
        state = {
            "section_drafts": [
                _section(0, "A", MATCH_TEXT),
                _section(1, "B", MATCH_TEXT),
                _section(2, "C", WEAK_TEXT),
            ],
            "voice_fingerprint": fp,
            "voice_block": "Voice",
            "status": "ok",
        }
        result = await node(state)
        assert llm.call_count == 1
        drafts = result["section_drafts"]
        assert drafts[0].body_markdown == MATCH_TEXT
        assert drafts[1].body_markdown == MATCH_TEXT
        assert drafts[2].body_markdown != WEAK_TEXT

    async def test_skips_when_all_sections_above_threshold(self) -> None:
        fp = _fingerprint()
        llm = _CountingLLM(FakeListChatModel(responses=[]))
        node = make_fix_voice_node(llm, 70)  # type: ignore[arg-type]
        state = {
            "section_drafts": [
                _section(0, "A", MATCH_TEXT),
                _section(1, "B", MATCH_TEXT),
            ],
            "voice_fingerprint": fp,
            "voice_block": "",
            "status": "ok",
        }
        result = await node(state)
        assert llm.call_count == 0
        assert result["section_drafts"][0].body_markdown == MATCH_TEXT
        assert result["section_drafts"][1].body_markdown == MATCH_TEXT

    async def test_skips_short_section_even_below_threshold(self) -> None:
        """Review item 4a: a short, weak-scoring section is never rewritten."""
        fp = _fingerprint()
        llm = _CountingLLM(FakeListChatModel(responses=[]))
        node = make_fix_voice_node(llm, 70)  # type: ignore[arg-type]
        short_weak = _section(0, "A", WEAK_TEXT, word_count=10)
        state = {
            "section_drafts": [short_weak],
            "voice_fingerprint": fp,
            "voice_block": "",
            "status": "ok",
        }
        result = await node(state)
        assert llm.call_count == 0
        assert result["section_drafts"][0].body_markdown == WEAK_TEXT

    async def test_llm_failure_keeps_original_and_still_returns_scores(self) -> None:
        """Review item 4b: llm.ainvoke raising -> voice_fix_failed, original
        draft kept, node still returns scores (never fails the run)."""
        fp = _fingerprint()
        node = make_fix_voice_node(_RaisingLLM(), 70)  # type: ignore[arg-type]
        state = {
            "section_drafts": [_section(0, "A", WEAK_TEXT)],
            "voice_fingerprint": fp,
            "voice_block": "",
            "status": "ok",
        }
        with structlog.testing.capture_logs() as logs:
            result = await node(state)
        assert result["section_drafts"][0].body_markdown == WEAK_TEXT
        assert result["voice_scores_by_section"] == {
            "0": score_text(WEAK_TEXT, fp).score
        }
        failed = [e for e in logs if e["event"] == "voice_fix_failed"]
        assert len(failed) == 1
        assert failed[0]["section_index"] == 0

    async def test_node_level_exception_returns_empty_dict_and_logs(self) -> None:
        """Review item 4c: a malformed draft dict raises inside
        `_coerce_drafts`; the node must catch it, log, and return {}."""
        node = make_fix_voice_node(_RaisingLLM(), 70)  # type: ignore[arg-type]
        state = {
            "section_drafts": [{"not": "a valid section draft"}],
            "voice_fingerprint": _fingerprint(),
            "status": "ok",
        }
        with structlog.testing.capture_logs() as logs:
            result = await node(state)
        assert result == {}
        failed = [e for e in logs if e["event"] == "voice_fix_failed"]
        assert len(failed) == 1

    async def test_rewritten_word_count_is_recomputed(self) -> None:
        """Review item 4d."""
        fp = _fingerprint()
        llm = _CountingLLM(FakeListChatModel(responses=[MATCH_TEXT]))
        node = make_fix_voice_node(llm, 70)  # type: ignore[arg-type]
        state = {
            "section_drafts": [_section(0, "A", WEAK_TEXT, word_count=90)],
            "voice_fingerprint": fp,
            "voice_block": "",
            "status": "ok",
        }
        result = await node(state)
        rewritten = result["section_drafts"][0]
        assert rewritten.body_markdown == MATCH_TEXT
        assert rewritten.word_count == len(MATCH_TEXT.split())
        assert rewritten.word_count != 90

    async def test_noop_without_fingerprint(self) -> None:
        llm = _CountingLLM(FakeListChatModel(responses=[]))
        node = make_fix_voice_node(llm, 70)  # type: ignore[arg-type]
        state = {"section_drafts": [_section(0, "A", WEAK_TEXT)], "status": "ok"}
        assert await node(state) == {}
        assert llm.call_count == 0

    async def test_keeps_original_when_rewrite_drops_a_citation(self) -> None:
        fp = _fingerprint()
        cited = WEAK_TEXT + " [1]"
        # Response echoes MATCH_TEXT — grammatically fine, but drops [1].
        llm = _CountingLLM(FakeListChatModel(responses=[MATCH_TEXT]))
        node = make_fix_voice_node(llm, 70)  # type: ignore[arg-type]
        state = {
            "section_drafts": [_section(0, "A", cited)],
            "voice_fingerprint": fp,
            "voice_block": "",
            "status": "ok",
        }
        result = await node(state)
        assert llm.call_count == 1
        assert result["section_drafts"][0].body_markdown == cited

    async def test_keeps_original_when_rewrite_scores_no_better(self) -> None:
        fp = _fingerprint()
        # LLM "rewrites" but echoes the same off-voice style back.
        llm = _CountingLLM(FakeListChatModel(responses=[WEAK_TEXT]))
        node = make_fix_voice_node(llm, 70)  # type: ignore[arg-type]
        state = {
            "section_drafts": [_section(0, "A", WEAK_TEXT)],
            "voice_fingerprint": fp,
            "voice_block": "",
            "status": "ok",
        }
        result = await node(state)
        assert llm.call_count == 1
        assert result["section_drafts"][0].body_markdown == WEAK_TEXT

    async def test_recomputes_scores_after_fixing(self) -> None:
        fp = _fingerprint()
        llm = _CountingLLM(FakeListChatModel(responses=[MATCH_TEXT]))
        node = make_fix_voice_node(llm, 70)  # type: ignore[arg-type]
        state = {
            "section_drafts": [_section(0, "A", WEAK_TEXT)],
            "voice_fingerprint": fp,
            "voice_block": "",
            "status": "ok",
        }
        result = await node(state)
        assert result["voice_scores_by_section"]["0"] > score_text(WEAK_TEXT, fp).score
        assert result["voice_match_score"] == result["voice_scores_by_section"]["0"]


class TestVoiceRouter:
    def test_routes_to_fix_when_any_section_below_threshold(self) -> None:
        router = make_voice_router(70)
        state = {
            "voice_scores_by_section": {"0": 50, "1": 90},
            "section_drafts": [
                _section(0, "A", WEAK_TEXT),
                _section(1, "B", MATCH_TEXT),
            ],
        }
        assert router(state) == "fix_voice_deviations"

    def test_routes_to_seo_when_all_sections_at_or_above_threshold(self) -> None:
        router = make_voice_router(70)
        state = {
            "voice_scores_by_section": {"0": 70, "1": 90},
            "section_drafts": [
                _section(0, "A", MATCH_TEXT),
                _section(1, "B", MATCH_TEXT),
            ],
        }
        assert router(state) == "seo_optimize"

    def test_routes_to_seo_when_no_scores_present(self) -> None:
        router = make_voice_router(70)
        assert router({}) == "seo_optimize"

    def test_routes_to_seo_when_weak_section_is_too_short(self) -> None:
        """Review item 3: a short section that scored below threshold must
        not route through a no-op fix_voice_deviations step."""
        router = make_voice_router(70)
        state = {
            "voice_scores_by_section": {"0": 20},
            "section_drafts": [_section(0, "A", WEAK_TEXT, word_count=10)],
        }
        assert router(state) == "seo_optimize"


class TestExtractOutputVoiceMatchScore:
    def test_returns_voice_match_score_when_present(self) -> None:
        result = {"voice_match_score": 82, "section_drafts": ["should be ignored"]}
        assert _extract_output("score_voice", result) == {"voice_match_score": 82}

    def test_returns_voice_match_score_even_when_none(self) -> None:
        result = {"voice_match_score": None, "voice_scores_by_section": {}}
        assert _extract_output("score_voice", result) == {"voice_match_score": None}

    def test_falls_through_to_section_drafts_without_voice_key(self) -> None:
        result = {"section_drafts": [1, 2, 3]}
        assert _extract_output("draft", result) == {"sections_drafted": 3}
