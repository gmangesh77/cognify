"""AUTHOR-009 — multi-pass humanization as an event stream."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable

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


def _scores_by_prefix(
    mapping: dict[str, int], default: int
) -> Callable[[str], SlopScore]:
    def _fake(text: str) -> SlopScore:
        for prefix, score in mapping.items():
            if text.startswith(prefix):
                return _score(score)
        return _score(default)

    return _fake


async def _collect(gen: AsyncIterator[HumanizeEvent]) -> list[HumanizeEvent]:
    return [ev async for ev in gen]


class TestStreamHumanization:
    async def test_clean_text_emits_mechanical_pass_then_done(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(slop_scorer, "score_text", _scores_by_prefix({}, 90))
        events = await _collect(
            stream_humanization(
                section_index=0,
                title="S",
                markdown="Clean prose.",
                llm=FakeListChatModel(responses=["unused"]),
                max_llm_passes=2,
            )
        )
        assert [e.type for e in events] == ["pass", "done"]
        assert events[0].data["name"] == "mechanical"
        assert events[-1].data["llm_called"] is False
        assert events[-1].data["passes"] == 1

    async def test_two_llm_passes_until_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # original 30 → pass1 output 50 → pass2 output 80 (clears 70)
        monkeypatch.setattr(
            slop_scorer,
            "score_text",
            _scores_by_prefix({"First": 50, "Second": 80}, 30),
        )
        llm = FakeListChatModel(responses=["First rewrite.", "Second rewrite."])
        events = await _collect(
            stream_humanization(
                section_index=0,
                title="S",
                markdown="Delve into it.",
                llm=llm,
                max_llm_passes=2,
            )
        )
        assert [e.type for e in events] == ["pass", "pass", "pass", "done"]
        assert [e.data["name"] for e in events[:3]] == ["mechanical", "llm", "llm"]
        assert events[1].data["index"] == 1 and events[2].data["index"] == 2
        done = events[-1].data
        assert done["passes"] == 3 and done["llm_called"] is True
        assert str(done["rewritten"]).startswith("Second")
        assert done["segments"] and done["diff"]

    async def test_stops_after_first_llm_pass_when_threshold_cleared(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            slop_scorer, "score_text", _scores_by_prefix({"Good": 85}, 30)
        )
        llm = FakeListChatModel(responses=["Good rewrite.", "never used"])
        events = await _collect(
            stream_humanization(
                section_index=0, title="S", markdown="Delve.", llm=llm, max_llm_passes=2
            )
        )
        assert [e.type for e in events] == ["pass", "pass", "done"]

    async def test_max_passes_caps_iteration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(slop_scorer, "score_text", _scores_by_prefix({}, 30))
        llm = FakeListChatModel(responses=["One.", "Two.", "Three."])
        events = await _collect(
            stream_humanization(
                section_index=0, title="S", markdown="Delve.", llm=llm, max_llm_passes=2
            )
        )
        assert [e.type for e in events] == ["pass", "pass", "pass", "done"]

    async def test_stops_when_llm_pass_changes_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(slop_scorer, "score_text", _scores_by_prefix({}, 30))
        llm = FakeListChatModel(responses=["Delve.", "Delve."])
        events = await _collect(
            stream_humanization(
                section_index=0, title="S", markdown="Delve.", llm=llm, max_llm_passes=2
            )
        )
        assert [e.type for e in events] == ["pass", "pass", "done"]
        assert events[1].data["changed"] is False

    async def test_llm_failure_emits_error_and_stops(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(slop_scorer, "score_text", _scores_by_prefix({}, 30))

        class _Boom(FakeListChatModel):
            async def ainvoke(self, *a: object, **k: object) -> object:  # type: ignore[override]
                raise RuntimeError("llm down")

        events = await _collect(
            stream_humanization(
                section_index=0,
                title="S",
                markdown="Delve.",
                llm=_Boom(responses=["x"]),
                max_llm_passes=2,
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

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.humanize_preview_max_passes == 2
