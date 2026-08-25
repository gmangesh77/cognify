"""Tests for the LLM-based article outline generator."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.length_budgets import DEFAULT_LENGTH_BUDGETS
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
        llm, captured = _capturing_llm([_outline_json(3)])
        ctx = OutlineContext(instruction="Make it punchier and cut the jargon.")
        await generate_outline(_make_topic(), _make_findings(), llm, ctx)
        assert any(
            "Editor instructions for this revision: "
            "Make it punchier and cut the jargon." in msg
            for msg in captured
        )

    async def test_no_ctx_omits_instruction_line(self) -> None:
        llm, captured = _capturing_llm([_outline_json(3)])
        await generate_outline(_make_topic(), _make_findings(), llm)
        assert all("Editor instructions" not in msg for msg in captured)


def _capturing_llm(responses: list[str]) -> tuple[FakeListChatModel, list[str]]:
    captured: list[str] = []

    class _CapturingLLM(FakeListChatModel):
        async def ainvoke(self, messages, *args, **kwargs):  # type: ignore[no-untyped-def]
            captured.append(str(messages[-1].content))
            return await super().ainvoke(messages, *args, **kwargs)

    return _CapturingLLM(responses=responses), captured


class TestBudgetPrompt:
    async def test_pillar_budget_lines_in_prompt(self) -> None:
        llm, captured = _capturing_llm([_outline_json(8)])
        ctx = OutlineContext(budget=DEFAULT_LENGTH_BUDGETS["pillar"])
        await generate_outline(_make_topic(), _make_findings(), llm, ctx)
        prompt = captured[0]
        assert "8-12 sections" in prompt
        assert "150-350" not in prompt
        assert "Each section: 500-900 target words" in prompt
        assert "Total: 5000-8000 words" in prompt

    async def test_no_ctx_keeps_legacy_medium_numbers(self) -> None:
        llm, captured = _capturing_llm([_outline_json(4)])
        await generate_outline(_make_topic(), _make_findings(), llm)
        prompt = captured[0]
        assert "4-8 sections" in prompt
        assert "Each section: 200-500 target words" in prompt
        assert "Total: 1500-3000 words" in prompt

    async def test_content_type_guidance_and_pin_in_prompt(self) -> None:
        llm, captured = _capturing_llm([_outline_json(4)])
        ctx = OutlineContext(content_type="how-to")
        await generate_outline(_make_topic(), _make_findings(), llm, ctx)
        prompt = captured[0]
        assert "how-to guide" in prompt
        assert 'Set "content_type" to "how-to"' in prompt

    async def test_article_content_type_adds_no_guidance(self) -> None:
        llm, captured = _capturing_llm([_outline_json(4)])
        ctx = OutlineContext(content_type="article")
        await generate_outline(_make_topic(), _make_findings(), llm, ctx)
        assert 'Set "content_type"' not in captured[0]

    async def test_budget_and_instruction_coexist(self) -> None:
        llm, captured = _capturing_llm([_outline_json(3)])
        ctx = OutlineContext(
            budget=DEFAULT_LENGTH_BUDGETS["short"],
            instruction="Punchier.",
        )
        await generate_outline(_make_topic(), _make_findings(), llm, ctx)
        prompt = captured[0]
        assert "3-5 sections" in prompt
        assert "Editor instructions for this revision: Punchier." in prompt


class TestOutlineNodeBudget:
    async def test_state_length_target_reaches_prompt(self) -> None:
        from src.agents.content.nodes import make_outline_node

        llm, captured = _capturing_llm([_outline_json(3)])
        node = make_outline_node(llm)
        state = {
            "topic": _make_topic(),
            "findings": _make_findings(),
            "length_target": "short",
            "content_type": "how-to",
        }
        result = await node(state)
        assert result["status"] == "outline_complete"
        assert "3-5 sections" in captured[0]
        assert 'Set "content_type" to "how-to"' in captured[0]

    async def test_state_without_sizing_keys_uses_medium(self) -> None:
        from src.agents.content.nodes import make_outline_node

        llm, captured = _capturing_llm([_outline_json(4)])
        node = make_outline_node(llm)
        state = {"topic": _make_topic(), "findings": _make_findings()}
        await node(state)
        assert "4-8 sections" in captured[0]

    async def test_settings_overrides_reach_the_prompt(self) -> None:
        from src.agents.content.nodes import make_outline_node
        from src.config.settings import Settings

        llm, captured = _capturing_llm([_outline_json(6)])
        settings = Settings(
            _env_file=None,
            length_budgets_json={"long": {"total_max": 6000}},
        )
        node = make_outline_node(llm, settings)
        state = {
            "topic": _make_topic(),
            "findings": _make_findings(),
            "length_target": "long",
        }
        await node(state)
        assert "Total: 3000-6000 words" in captured[0]
