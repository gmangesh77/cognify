"""Tests for LLM-based section query generation."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.query_generator import generate_section_queries
from src.models.content_pipeline import (
    ArticleOutline,
    OutlineSection,
    SectionQueries,
)


def _make_outline(section_count: int = 3) -> ArticleOutline:
    sections = [
        OutlineSection(
            index=i,
            title=f"Section {i}",
            description=f"Desc {i}",
            key_points=[f"Point {i}"],
            target_word_count=300,
            relevant_facets=[0],
        )
        for i in range(section_count)
    ]
    return ArticleOutline(
        title="Test",
        content_type="article",
        sections=sections,
        total_target_words=section_count * 300,
        reasoning="R",
    )


def _queries_json(section_count: int = 3) -> str:
    return json.dumps(
        [
            {"section_index": i, "queries": [f"query {i}a", f"query {i}b"]}
            for i in range(section_count)
        ]
    )


class TestGenerateSectionQueries:
    async def test_happy_path(self) -> None:
        llm = FakeListChatModel(responses=[_queries_json(3)])
        outline = _make_outline(3)
        result = await generate_section_queries(outline, llm)
        assert len(result) == 3
        assert all(isinstance(sq, SectionQueries) for sq in result)
        assert result[0].section_index == 0
        assert len(result[0].queries) == 2

    async def test_single_section(self) -> None:
        llm = FakeListChatModel(responses=[_queries_json(1)])
        outline = _make_outline(1)
        result = await generate_section_queries(outline, llm)
        assert len(result) == 1

    async def test_retries_on_bad_json(self) -> None:
        llm = FakeListChatModel(responses=["bad json", _queries_json(2)])
        outline = _make_outline(2)
        result = await generate_section_queries(outline, llm)
        assert len(result) == 2

    async def test_raises_after_max_retries(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        outline = _make_outline(2)
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_section_queries(outline, llm)
