"""Tests for the on-demand humanization preview service."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.services.content.humanize_preview import preview_humanization


class TestPreviewHumanization:
    @pytest.mark.asyncio
    async def test_clean_text_skips_llm(self) -> None:
        """Text scoring above the rewrite threshold gets mechanical-only fixes."""
        # Plain prose with no slop patterns — should score high enough
        # that the LLM is not invoked.
        clean = "Cognify ships visual generation overhaul. Editors can refine prose."
        llm = FakeListChatModel(responses=["unused"])
        preview = await preview_humanization(
            section_index=0,
            title="Section",
            markdown=clean,
            llm=llm,
        )
        assert preview.llm_called is False
        assert preview.original == clean
        assert preview.rewritten == preview.mechanical_fixed

    @pytest.mark.asyncio
    async def test_dirty_text_below_threshold_calls_llm_and_emits_diff(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Text scoring below the rewrite threshold gets the LLM rewrite."""
        # Drive the slop score below the threshold by patching the
        # threshold low-side so we don't have to handcraft prose that
        # the scorer specifically penalises (the pattern catalogue
        # evolves over time and we don't want this test brittle to it).
        from src.agents.content import slop_scorer
        from src.models.content_pipeline import SlopScore

        def _fake_score_text(text: str) -> SlopScore:
            # Original gets a low score, rewritten gets a high one.
            score = 80 if text.startswith("Tighter") else 30
            return SlopScore(
                score=score,
                rating="LIKELY_AI" if score < 60 else "MOSTLY_HUMAN",
                violations=[],
                phrase_deductions=0,
                pattern_deductions=0,
            )

        monkeypatch.setattr(slop_scorer, "score_text", _fake_score_text)
        llm = FakeListChatModel(responses=["Tighter rewrite without the slop."])
        preview = await preview_humanization(
            section_index=0,
            title="Section",
            markdown="Let me delve into this overly verbose paragraph.",
            llm=llm,
        )
        assert preview.llm_called is True
        assert preview.diff, "expected a non-empty word-level diff"
        assert preview.score_after.score >= preview.score_before.score
