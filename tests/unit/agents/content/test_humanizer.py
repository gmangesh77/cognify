"""Tests for mechanical text fixes and LLM rewriting."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.humanizer import (
    fix_mechanical,
    payload_for_llm,
    rewrite_section,
    slot_back,
)
from src.models.content_pipeline import (
    SectionDraft,
    SlopScore,
    Violation,
)


def _make_section(text: str) -> SectionDraft:
    return SectionDraft(
        section_index=0,
        title="Test Section",
        body_markdown=text,
        word_count=len(text.split()),
        citations_used=[],
    )


def _make_score(score: int = 50) -> SlopScore:
    return SlopScore(
        score=score,
        rating="SUSPICIOUS",
        violations=[Violation(category="buzzwords", phrase="delve", sentence_index=0)],
        phrase_deductions=4,
        pattern_deductions=0,
    )


class TestFixMechanical:
    def test_replaces_em_dash_with_comma_before_lowercase(self) -> None:
        text = "This concept \u2014 which is important \u2014 matters."
        result = fix_mechanical(text)
        assert "\u2014" not in result
        assert "concept, which" in result

    def test_replaces_em_dash_with_period_before_uppercase(self) -> None:
        text = "The results were clear \u2014 Productivity increased."
        result = fix_mechanical(text)
        assert "\u2014" not in result
        assert "clear. Productivity" in result

    def test_replaces_en_dash(self) -> None:
        text = "The system \u2013 a new approach \u2013 worked well."
        result = fix_mechanical(text)
        assert "\u2013" not in result

    def test_normalizes_whitespace(self) -> None:
        text = "Word   word  \n\n\n  word."
        result = fix_mechanical(text)
        assert "   " not in result

    def test_preserves_citations(self) -> None:
        text = "This is important [1] \u2014 very important [2]."
        result = fix_mechanical(text)
        assert "[1]" in result
        assert "[2]" in result


class TestRewriteSection:
    @pytest.mark.asyncio
    async def test_returns_updated_section(self) -> None:
        section = _make_section("Let me delve into this transformative topic [1].")
        llm = FakeListChatModel(responses=["This topic covers important ground [1]."])
        result = await rewrite_section(section, _make_score(), llm)
        assert isinstance(result, SectionDraft)
        assert result.word_count > 0
        assert result.body_markdown != section.body_markdown

    @pytest.mark.asyncio
    async def test_preserves_citations(self) -> None:
        section = _make_section("The data shows [1] that leverage is key [2].")
        llm = FakeListChatModel(
            responses=["The data shows [1] that this approach works [2]."]
        )
        result = await rewrite_section(section, _make_score(), llm)
        assert "[1]" in result.body_markdown
        assert "[2]" in result.body_markdown

    @pytest.mark.asyncio
    async def test_rejects_rewrite_if_citations_lost(self) -> None:
        section = _make_section("Important finding [1] and another [2].")
        llm = FakeListChatModel(responses=["Important finding without any citations."])
        result = await rewrite_section(section, _make_score(), llm)
        # Should keep original since citations were lost
        assert result.body_markdown == section.body_markdown

    @pytest.mark.asyncio
    async def test_single_attempt_no_retry(self) -> None:
        """LLM is called exactly once, even if rewrite still has slop."""
        section = _make_section("Let me delve into this transformative topic [1].")
        llm = FakeListChatModel(
            responses=["Let me explore this innovative concept [1]."]
        )
        result = await rewrite_section(section, _make_score(), llm)
        assert result.body_markdown == "Let me explore this innovative concept [1]."


class TestStructureAwareRewrite:
    """CONTENT-007: structure-aware humanization preserves non-prose blocks."""

    @pytest.mark.asyncio
    async def test_preserves_heading_image_and_code_block(self) -> None:
        """Headings, images, and code blocks must NOT be sent to the LLM
        and must appear unchanged in the output."""
        section = _make_section(
            "## Inner Heading\n\n"
            "Some prose to rewrite.\n\n"
            "![chart](https://example.com/chart.png)\n\n"
            "```python\nprint('keep me')\n```\n\n"
            "Another paragraph to refine."
        )
        # Two prose blocks → LLM emits two chunks separated by sentinel.
        llm = FakeListChatModel(
            responses=[
                "Rewritten prose body.\n\n<<<BLOCK>>>\n\nRewritten closing paragraph."
            ]
        )
        result = await rewrite_section(section, _make_score(), llm)
        body = result.body_markdown
        assert "## Inner Heading" in body
        assert "![chart](https://example.com/chart.png)" in body
        assert "print('keep me')" in body
        assert "Rewritten prose body." in body
        assert "Rewritten closing paragraph." in body

    @pytest.mark.asyncio
    async def test_falls_back_when_llm_loses_sentinel(self) -> None:
        """If the LLM emits the wrong number of blocks, restore originals."""
        section = _make_section("First prose paragraph.\n\nSecond prose paragraph.")
        # LLM dropped the sentinel — only one chunk returned.
        llm = FakeListChatModel(responses=["A single merged response."])
        result = await rewrite_section(section, _make_score(), llm)
        # Falls back to the original body to keep structure intact.
        assert "First prose paragraph." in result.body_markdown
        assert "Second prose paragraph." in result.body_markdown

    @pytest.mark.asyncio
    async def test_no_prose_blocks_returns_section_unchanged(self) -> None:
        """A section that's all structure (heading + image) is left alone."""
        section = _make_section("## Title\n\n![banner](https://example.com/b.png)")
        # No LLM call should happen, but FakeListChatModel needs at least
        # one entry in case our fallback path changes.
        llm = FakeListChatModel(responses=["unused"])
        result = await rewrite_section(section, _make_score(), llm)
        assert result.body_markdown == section.body_markdown


class TestPublicAliases:
    def test_payload_for_llm_and_slot_back_are_importable(self) -> None:
        """AUTHOR-011: voice_nodes.py reuses these via the public aliases."""
        assert callable(payload_for_llm)
        assert callable(slot_back)
