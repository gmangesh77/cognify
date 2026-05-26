"""Tests for the LangGraph image planner node (Phase 2 / VISUAL-005)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.image_planner_node import make_image_planner_node
from src.models.content import Provenance, SEOMetadata
from src.models.content_pipeline import (
    ArticleOutline,
    OutlineSection,
    SectionDraft,
    SEOResult,
)
from src.models.research import TopicInput
from tests.fixtures.visual_planner.planner_responses import (
    COVER_HERO_GENERAL_JSON,
    GENERAL_BUSINESS_INTRO_CONCEPT_JSON,
    GENERAL_BUSINESS_INTRO_JSON,
)


def _topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="The quiet refactor",
        description="Steady cleanups beat big rewrites.",
        domain="engineering",
    )


def _section(idx: int = 0) -> SectionDraft:
    return SectionDraft(
        section_index=idx,
        title=f"Section {idx}",
        body_markdown="A first paragraph.\n\nA second paragraph.",
        word_count=10,
        citations_used=[],
    )


def _seo_result() -> SEOResult:
    return SEOResult(
        seo=SEOMetadata(title="Quiet refactor", description="Wins via small steps."),
        summary="Small steps compound.",
        key_claims=["Small steps compound."],
        provenance=Provenance(
            research_session_id=uuid4(),
            primary_model="claude-opus-4",
            drafting_model="claude-sonnet-4",
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="1.0.0",
        ),
        ai_disclosure="Generated with AI.",
    )


def _outline() -> ArticleOutline:
    return ArticleOutline(
        title="The quiet refactor",
        subtitle=None,
        content_type="article",
        sections=[
            OutlineSection(
                index=0,
                title="Why small steps matter",
                description="The case for steady cleanups.",
                key_points=["Steady > heroic"],
                target_word_count=300,
                relevant_facets=[0],
            ),
        ],
        total_target_words=300,
        reasoning="Article structure.",
    )


def _state(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "topic": _topic(),
        "research_plan": None,
        "findings": [],
        "session_id": uuid4(),
        "outline": _outline(),
        "status": "active",
        "error": None,
        "section_drafts": [_section(0)],
        "seo_result": _seo_result(),
        "visuals": [],
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
class TestImagePlannerNode:
    async def test_returns_empty_when_disabled(self) -> None:
        llm = FakeListChatModel(responses=["should never be called"])
        node = make_image_planner_node(llm, enabled=False)
        result = await node(_state())
        assert result == {}

    async def test_plans_cover_and_section_specs_when_enabled(self) -> None:
        llm = FakeListChatModel(
            responses=[
                COVER_HERO_GENERAL_JSON,
                GENERAL_BUSINESS_INTRO_CONCEPT_JSON,
            ]
        )
        node = make_image_planner_node(llm, enabled=True)
        result = await node(_state())
        assert "image_specs" in result
        specs = result["image_specs"]
        assert isinstance(specs, list)
        # 1 cover + 1 section spec.
        assert len(specs) == 2
        # The cover comes first.
        assert specs[0].placement.anchor == "cover"
        assert specs[0].placement.section_index == -1
        # The section spec carries section_index 0.
        assert specs[1].placement.section_index == 0

    async def test_drops_per_section_heroes(self) -> None:
        """Only the article cover may be a hero. Section-level hero specs
        from the planner are silently dropped during truncation."""
        llm = FakeListChatModel(
            responses=[COVER_HERO_GENERAL_JSON, GENERAL_BUSINESS_INTRO_JSON]
        )
        node = make_image_planner_node(llm, enabled=True)
        result = await node(_state())
        specs = result["image_specs"]
        assert len(specs) == 1
        assert specs[0].placement.anchor == "cover"
        assert specs[0].role_style == "hero"

    async def test_enforces_max_total_cap(self) -> None:
        """`max_total_images` is a hard ceiling across cover + inline."""
        llm = FakeListChatModel(
            responses=[
                COVER_HERO_GENERAL_JSON,
                GENERAL_BUSINESS_INTRO_CONCEPT_JSON,
            ]
        )
        node = make_image_planner_node(llm, enabled=True, max_total_images=1)
        result = await node(_state())
        specs = result["image_specs"]
        assert len(specs) == 1
        # The cover wins when only 1 slot is available.
        assert specs[0].placement.anchor == "cover"

    async def test_threads_audience_persona_from_state(self) -> None:
        llm = FakeListChatModel(
            responses=[
                COVER_HERO_GENERAL_JSON,
                GENERAL_BUSINESS_INTRO_CONCEPT_JSON,
            ]
        )
        node = make_image_planner_node(llm, enabled=True)
        # audience_persona on the state replaces the default.
        result = await node(_state(audience_persona="cto"))
        assert "image_specs" in result

    async def test_skips_when_no_section_drafts(self) -> None:
        llm = FakeListChatModel(responses=[])
        node = make_image_planner_node(llm, enabled=True)
        result = await node(_state(section_drafts=[]))
        assert result == {}
