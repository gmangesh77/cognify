"""Tests for the LLM-based article outline generator."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.outline_generator import OutlineContext, generate_outline
from src.models.content_pipeline import ArticleOutline
from src.models.research import FacetFindings, SourceDocument, TopicInput


def _make_topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="AI Security Trends in 2026",
        description="Emerging threats and defenses",
        domain="cybersecurity",
    )


def _make_findings(num_facets: int = 3) -> list[FacetFindings]:
    return [
        FacetFindings(
            facet_index=i,
            sources=[
                SourceDocument(
                    url=f"https://example.com/{i}",
                    title=f"Source {i}",
                    snippet=f"Content about facet {i}",
                    retrieved_at=datetime.now(UTC),
                )
            ],
            claims=[f"Claim {i}a", f"Claim {i}b"],
            summary=f"Summary of facet {i} research findings.",
        )
        for i in range(num_facets)
    ]


def _outline_json(num_sections: int = 5) -> str:
    sections = [
        {
            "index": i,
            "title": f"Section {i}",
            "description": f"Covers aspect {i}",
            "key_points": [f"Point {i}a", f"Point {i}b", f"Point {i}c"],
            "target_word_count": 300,
            "relevant_facets": [i % 3],
        }
        for i in range(num_sections)
    ]
    return json.dumps(
        {
            "title": "AI Security Trends: A Comprehensive Analysis",
            "subtitle": "Emerging threats and defense strategies",
            "content_type": "article",
            "sections": sections,
            "total_target_words": num_sections * 300,
            "reasoning": "Structured for narrative flow.",
        }
    )


class TestGenerateOutline:
    async def test_returns_valid_outline(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json(5)])
        outline = await generate_outline(_make_topic(), _make_findings(), llm)
        assert isinstance(outline, ArticleOutline)
        assert len(outline.sections) == 5
        assert outline.total_target_words == 1500

    async def test_sections_have_required_fields(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json(4)])
        outline = await generate_outline(_make_topic(), _make_findings(), llm)
        for section in outline.sections:
            assert section.title != ""
            assert len(section.key_points) >= 1
            assert section.target_word_count > 0
            assert len(section.relevant_facets) >= 1

    async def test_handles_malformed_json(self) -> None:
        llm = FakeListChatModel(responses=["not json", _outline_json(5)])
        outline = await generate_outline(_make_topic(), _make_findings(), llm)
        assert isinstance(outline, ArticleOutline)

    async def test_raises_on_repeated_failure(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_outline(_make_topic(), _make_findings(), llm)


class TestOutlineContext:
    async def test_context_kwargs_still_accepted_via_ctx(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json(3)])
        ctx = OutlineContext(
            target_audience="engineers",
            preferred_angle="practical",
            content_tone="direct",
            keywords=["zero trust"],
        )
        outline = await generate_outline(_make_topic(), _make_findings(), llm, ctx)
        assert isinstance(outline, ArticleOutline)

    async def test_instruction_appears_in_prompt(self) -> None:
        captured: list[str] = []

        class _CapturingLLM(FakeListChatModel):
            async def ainvoke(self, messages, *args, **kwargs):  # type: ignore[no-untyped-def]
                captured.append(str(messages[-1].content))
                return await super().ainvoke(messages, *args, **kwargs)

        llm = _CapturingLLM(responses=[_outline_json(3)])
        ctx = OutlineContext(instruction="Make it punchier and cut the jargon.")
        await generate_outline(_make_topic(), _make_findings(), llm, ctx)
        assert any(
            "Editor instructions for this revision: "
            "Make it punchier and cut the jargon." in msg
            for msg in captured
        )

    async def test_no_ctx_omits_instruction_line(self) -> None:
        captured: list[str] = []

        class _CapturingLLM(FakeListChatModel):
            async def ainvoke(self, messages, *args, **kwargs):  # type: ignore[no-untyped-def]
                captured.append(str(messages[-1].content))
                return await super().ainvoke(messages, *args, **kwargs)

        llm = _CapturingLLM(responses=[_outline_json(3)])
        await generate_outline(_make_topic(), _make_findings(), llm)
        assert all("Editor instructions" not in msg for msg in captured)
