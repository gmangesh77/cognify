"""Tests for section drafter — RAG retrieval + LLM drafting + citation extraction."""

from unittest.mock import AsyncMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.section_drafter import (
    DraftingContext,
    draft_section,
    extract_citations,
)
from src.models.content_pipeline import (
    CitationRef,
    OutlineSection,
    SectionDraft,
    SectionQueries,
)
from src.models.research import ChunkResult


def _make_section(index: int = 0) -> OutlineSection:
    return OutlineSection(
        index=index,
        title=f"Section {index}",
        description=f"Description {index}",
        key_points=[f"Point {index}"],
        target_word_count=300,
        relevant_facets=[0],
    )


def _make_queries(index: int = 0) -> SectionQueries:
    return SectionQueries(section_index=index, queries=["query a", "query b"])


def _make_chunks(count: int = 5) -> list[ChunkResult]:
    return [
        ChunkResult(
            text=f"Chunk {i} content about the topic.",
            source_url=f"https://source{i}.com",
            source_title=f"Source {i}",
            score=0.9 - i * 0.1,
            chunk_index=i,
        )
        for i in range(count)
    ]


def _make_context(
    chunks: list[ChunkResult] | None = None,
    prior: list[SectionDraft] | None = None,
) -> DraftingContext:
    retriever = AsyncMock()
    retriever.retrieve = AsyncMock(
        return_value=_make_chunks() if chunks is None else chunks,
    )
    llm = FakeListChatModel(
        responses=[
            "This section discusses findings [1] and analysis [2]. More details [3]."
        ]
    )
    return DraftingContext(
        retriever=retriever,
        topic_id="topic-123",
        llm=llm,
        prior_drafts=prior or [],
    )


class TestExtractCitations:
    def test_extracts_valid_refs(self) -> None:
        chunks = _make_chunks(3)
        text = "Fact one [1] and fact two [2]."
        refs = extract_citations(text, chunks)
        assert len(refs) == 2
        assert refs[0] == CitationRef(
            index=1, source_url="https://source0.com", source_title="Source 0"
        )
        assert refs[1] == CitationRef(
            index=2, source_url="https://source1.com", source_title="Source 1"
        )

    def test_ignores_invalid_refs(self) -> None:
        chunks = _make_chunks(2)
        text = "Valid [1] and invalid [5]."
        refs = extract_citations(text, chunks)
        assert len(refs) == 1
        assert refs[0].index == 1

    def test_no_citations(self) -> None:
        chunks = _make_chunks(3)
        refs = extract_citations("No citations here.", chunks)
        assert refs == []


class TestDraftSection:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        ctx = _make_context()
        result = await draft_section(_make_section(), _make_queries(), ctx)
        assert isinstance(result, SectionDraft)
        assert result.section_index == 0
        assert result.title == "Section 0"
        assert result.word_count > 0
        assert len(result.citations_used) > 0
        ctx.retriever.retrieve.assert_called()

    @pytest.mark.asyncio
    async def test_deduplicates_chunks(self) -> None:
        chunk = ChunkResult(
            text="Dup",
            source_url="https://dup.com",
            source_title="Dup",
            score=0.9,
            chunk_index=0,
        )
        retriever = AsyncMock()
        retriever.retrieve = AsyncMock(return_value=[chunk])
        llm = FakeListChatModel(responses=["Text with [1] ref."])
        ctx = DraftingContext(
            retriever=retriever,
            topic_id="t",
            llm=llm,
            prior_drafts=[],
        )
        result = await draft_section(_make_section(), _make_queries(), ctx)
        assert result.word_count > 0

    @pytest.mark.asyncio
    async def test_zero_chunks_fallback(self) -> None:
        ctx = _make_context(chunks=[])
        result = await draft_section(_make_section(), _make_queries(), ctx)
        assert isinstance(result, SectionDraft)
        assert result.citations_used == []

    @pytest.mark.asyncio
    async def test_prior_drafts_in_prompt(self) -> None:
        prior = SectionDraft(
            section_index=0,
            title="Intro",
            body_markdown="First sentence here. More text.",
            word_count=5,
            citations_used=[],
        )
        ctx = _make_context(prior=[prior])
        result = await draft_section(_make_section(1), _make_queries(1), ctx)
        assert isinstance(result, SectionDraft)
        ctx.retriever.retrieve.assert_called()

    @pytest.mark.asyncio
    async def test_word_count_correct(self) -> None:
        ctx = _make_context()
        result = await draft_section(_make_section(), _make_queries(), ctx)
        actual = len(result.body_markdown.split())
        assert result.word_count == actual
