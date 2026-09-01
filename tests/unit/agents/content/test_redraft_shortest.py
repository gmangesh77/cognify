"""AUTHOR-011 Task 9 review round 1 — the validate node's redraft path
must carry the same `voice_block` as the normal per-section drafting
path (`_make_draft_ctx`), not a second, independently-built
`DraftingContext` that can drift from it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from src.agents.content.nodes import _redraft_shortest
from src.models.content_pipeline import (
    ArticleOutline,
    OutlineSection,
    SectionDraft,
    SectionQueries,
)
from src.models.research import TopicInput


def _outline() -> ArticleOutline:
    return ArticleOutline(
        title="T",
        content_type="article",
        sections=[
            OutlineSection(
                index=0,
                title="Section 0",
                description="D",
                key_points=["P"],
                target_word_count=100,
                relevant_facets=[0],
            )
        ],
        total_target_words=100,
        reasoning="R",
    )


def _draft(idx: int) -> SectionDraft:
    return SectionDraft(
        section_index=idx,
        title=f"Section {idx}",
        body_markdown="short",
        word_count=1,
        citations_used=[],
    )


def _llm() -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Redrafted body text."))
    return llm


def _base_state() -> dict[str, object]:
    return {
        "topic": TopicInput(id=uuid4(), title="T", description="D", domain="tech"),
        "outline": _outline(),
        "section_queries": [SectionQueries(section_index=0, queries=["q"])],
    }


class TestRedraftCarriesVoiceBlock:
    @pytest.mark.asyncio
    async def test_redraft_system_prompt_contains_voice_block(self) -> None:
        llm = _llm()
        state = {**_base_state(), "voice_block": "Voice. Write like this author."}
        await _redraft_shortest(state, [_draft(0)], 0, llm, None)  # type: ignore[arg-type]
        sent = llm.ainvoke.await_args.args[0]
        assert "Voice. Write like this author." in str(sent[0].content)

    @pytest.mark.asyncio
    async def test_redraft_omits_voice_block_when_absent(self) -> None:
        llm = _llm()
        state = _base_state()
        await _redraft_shortest(state, [_draft(0)], 0, llm, None)  # type: ignore[arg-type]
        sent = llm.ainvoke.await_args.args[0]
        assert "Voice." not in str(sent[0].content)
