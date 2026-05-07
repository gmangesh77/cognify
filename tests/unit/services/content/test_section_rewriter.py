"""Tests for the Claude-driven section rewriter."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.services.content.section_rewriter import (
    TONE_PRESETS,
    expand_tone_preset,
    rewrite_section_prose,
)


class TestExpandTonePreset:
    def test_known_presets_return_non_empty_strings(self) -> None:
        for preset in TONE_PRESETS:
            assert expand_tone_preset(preset).strip() != ""

    def test_presets_cover_required_set(self) -> None:
        # The handoff brief enumerates these four — guard against drift.
        required = {
            "shorter",
            "more_concrete",
            "more_conversational",
            "more_authoritative",
        }
        assert required.issubset(set(TONE_PRESETS))


class TestRewriteSectionProse:
    @pytest.mark.asyncio
    async def test_returns_rewritten_markdown(self) -> None:
        llm = FakeListChatModel(responses=["Tighter rewritten body."])
        result = await rewrite_section_prose(
            section_id="abc:0",
            instruction="Tighten the prose.",
            current_markdown="Original verbose body that meanders a lot.",
            llm=llm,
        )
        assert result.markdown_fragment == "Tighter rewritten body."
        assert result.diff, "expected non-empty diff for changed text"
        assert result.instruction == "Tighten the prose."

    @pytest.mark.asyncio
    async def test_strips_leading_code_fences(self) -> None:
        fenced = "```markdown\nClean fenced output.\n```"
        llm = FakeListChatModel(responses=[fenced])
        result = await rewrite_section_prose(
            section_id="abc:0",
            instruction="x",
            current_markdown="y",
            llm=llm,
        )
        assert result.markdown_fragment == "Clean fenced output."

    @pytest.mark.asyncio
    async def test_persona_register_is_woven_into_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        class _Capture(FakeListChatModel):
            async def ainvoke(self, messages, *args, **kwargs):  # type: ignore[override]
                captured["messages"] = messages
                return await super().ainvoke(messages, *args, **kwargs)

        llm = _Capture(responses=["ok"])
        await rewrite_section_prose(
            section_id="abc:0",
            instruction="Whatever",
            current_markdown="Body.",
            audience_persona="cto",
            llm=llm,
        )
        rendered = "\n".join(str(m.content) for m in captured["messages"])  # type: ignore[union-attr]
        assert "Audience register" in rendered
        # CTO register snippet — guard against persona switch losing the
        # backend-driven content. Single substring check keeps the test
        # robust against persona text edits beyond a couple of words.
        assert "technical leadership" in rendered or "real code" in rendered

    @pytest.mark.asyncio
    async def test_banned_pattern_block_is_in_prompt(self) -> None:
        captured: dict[str, object] = {}

        class _Capture(FakeListChatModel):
            async def ainvoke(self, messages, *args, **kwargs):  # type: ignore[override]
                captured["messages"] = messages
                return await super().ainvoke(messages, *args, **kwargs)

        llm = _Capture(responses=["ok"])
        await rewrite_section_prose(
            section_id="abc:0",
            instruction="rewrite",
            current_markdown="Body.",
            llm=llm,
        )
        rendered = "\n".join(str(m.content) for m in captured["messages"])  # type: ignore[union-attr]
        assert "Hard rules" in rendered
        assert "data-spec-id" in rendered
