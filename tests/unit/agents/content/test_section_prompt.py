"""AUTHOR-004 Task 2 — prompt assembly split + instruction slot + draft_one_section."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.content.section_drafter import (
    _SYSTEM_PROMPT,
    DraftingContext,
    OneSectionDraft,
    draft_one_section,
    draft_section,
)
from src.agents.content.section_prompt import (
    SYSTEM_PROMPT,
    build_messages,
    build_system_prompt,
    build_user_prompt,
)
from src.models.content_pipeline import OutlineSection, SectionDraft, SectionQueries


def _section(index: int = 0) -> OutlineSection:
    return OutlineSection(
        index=index,
        title=f"Section {index}",
        description="What this section covers",
        key_points=["point a", "point b"],
        target_word_count=300,
        relevant_facets=[0],
    )


def _prior() -> SectionDraft:
    return SectionDraft(
        section_index=0,
        title="Intro",
        body_markdown="First sentence here. Second sentence.",
        word_count=5,
        citations_used=[],
    )


def _ctx(
    instruction: str | None = None,
    reply: AIMessage | None = None,
    prior: list[SectionDraft] | None = None,
) -> DraftingContext:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=reply or AIMessage(content="Drafted body."))
    return DraftingContext(
        retriever=None,
        topic_id="topic-1",
        llm=llm,
        prior_drafts=prior or [],
        target_audience="CTOs",
        instruction=instruction,
    )


class TestSystemPrompt:
    def test_reexport_is_identical(self) -> None:
        assert _SYSTEM_PROMPT == SYSTEM_PROMPT
        assert "{target_word_count}" in SYSTEM_PROMPT

    def test_builds_audience_and_word_target(self) -> None:
        system = build_system_prompt(_section(), _ctx())
        assert "approximately 300 words" in system
        assert "Write for this audience: CTOs." in system

    def test_instruction_never_enters_the_system_prompt(self) -> None:
        system = build_system_prompt(
            _section(), _ctx(instruction="Lead with the metric")
        )
        assert "Lead with the metric" not in system
        assert "Editor instruction" not in system


class TestUserPrompt:
    def test_prior_sections_use_first_sentence(self) -> None:
        user = build_user_prompt(_section(1), [], _ctx(prior=[_prior()]))
        assert "### Prior Sections" in user
        assert "- Intro: First sentence here." in user
        assert "### Research Context" not in user
        assert "### Editor instruction" not in user

    def test_instruction_is_trailing_human_part_after_prior_sections(self) -> None:
        user = build_user_prompt(
            _section(1), [], _ctx(instruction="Lead with the metric", prior=[_prior()])
        )
        assert user.rstrip().endswith("### Editor instruction\nLead with the metric")
        assert user.index("### Prior Sections") < user.index("### Editor instruction")

    def test_blank_instruction_is_ignored(self) -> None:
        assert "Editor instruction" not in build_user_prompt(
            _section(), [], _ctx("   ")
        )


class TestBuildMessages:
    def test_returns_system_then_human_with_instruction_in_human(self) -> None:
        messages = build_messages(_section(), [], _ctx(instruction="shorter"))
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        assert "shorter" not in str(messages[0].content)
        assert "shorter" in str(messages[1].content)


class TestDraftOneSection:
    @pytest.mark.asyncio
    async def test_returns_body_word_count_and_no_usage_when_absent(self) -> None:
        ctx = _ctx(reply=AIMessage(content="New prose [1] here."))
        out = await draft_one_section(
            _section(), SectionQueries(section_index=0, queries=[]), ctx
        )
        assert isinstance(out, OneSectionDraft)
        assert out.body_markdown == "New prose [1] here."
        assert out.word_count == 4
        assert out.tokens_input is None and out.tokens_output is None
        ctx.llm.ainvoke.assert_awaited_once()  # exactly one LLM call (L-007)

    @pytest.mark.asyncio
    async def test_returns_token_usage_when_present(self) -> None:
        reply = AIMessage(
            content="Prose.",
            usage_metadata={
                "input_tokens": 120,
                "output_tokens": 40,
                "total_tokens": 160,
            },
        )
        out = await draft_one_section(
            _section(), SectionQueries(section_index=0, queries=[]), _ctx(reply=reply)
        )
        assert (out.tokens_input, out.tokens_output) == (120, 40)

    @pytest.mark.asyncio
    async def test_instruction_reaches_the_llm_in_the_human_turn(self) -> None:
        ctx = _ctx(instruction="Use a worked example")
        await draft_one_section(
            _section(), SectionQueries(section_index=0, queries=[]), ctx
        )
        sent = ctx.llm.ainvoke.await_args.args[0]
        assert "Use a worked example" not in str(sent[0].content)
        assert "Use a worked example" in str(sent[1].content)

    @pytest.mark.asyncio
    async def test_draft_section_still_returns_section_draft(self) -> None:
        ctx = _ctx(reply=AIMessage(content="Body text."))
        draft = await draft_section(
            _section(2), SectionQueries(section_index=2, queries=[]), ctx
        )
        assert draft.section_index == 2
        assert draft.body_markdown == "Body text."
