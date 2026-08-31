"""Tests for the persona-aware image planner (Phase 2 / VISUAL-005)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    Provenance,
    SEOMetadata,
)
from src.models.content_pipeline import SectionDraft
from src.models.research import TopicInput
from src.services.visuals.image_planner import (
    build_planner_messages,
    plan_article_cover,
    plan_section_images,
)
from tests.fixtures.visual_planner.planner_responses import (
    COVER_HERO_CTO_JSON,
    COVER_HERO_DESCRIPTION_FIELD_JSON,
    COVER_HERO_GENERAL_JSON,
    CTO_CONCLUSION_EMPTY_JSON,
    CTO_DEEP_DIVE_JSON,
    EMPTY_LIST_RESPONSE,
    GARBAGE_RESPONSE,
    GENERAL_BUSINESS_INTRO_JSON,
    GENERAL_BUSINESS_QUOTE_JSON,
    MARKETER_COMPARISON_JSON,
)


def _topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="The quiet refactor",
        description="How small steady cleanups outperform big rewrites.",
        domain="engineering",
    )


def _section(*, index: int = 0, title: str = "Why small steps matter") -> SectionDraft:
    return SectionDraft(
        section_index=index,
        title=title,
        body_markdown=(
            "Small steps compound. Teams that ship a careful refactor "
            "every week move faster than teams that pause for a quarter "
            "to rebuild from scratch.\n\n"
            "The data backs this up across multiple studies."
        ),
        word_count=42,
        citations_used=[],
    )


def _article() -> CanonicalArticle:
    return CanonicalArticle(
        title="The quiet refactor",
        body_markdown="# Heading\n\nBody.",
        summary="A quiet refactor wins over a loud rewrite.",
        key_claims=["Small steps compound."],
        content_type=ContentType.ARTICLE,
        seo=SEOMetadata(title="Quiet Refactor", description="Wins via small steps."),
        citations=[Citation(index=1, title="Source", url="https://x.test/1")],
        authors=["Cognify"],
        domain="engineering",
        provenance=Provenance(
            research_session_id=uuid4(),
            primary_model="claude-opus-4",
            drafting_model="claude-sonnet-4",
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="1.0.0",
        ),
    )


class TestBuildPlannerMessages:
    def test_messages_include_catalogue_persona_and_cliches(self) -> None:
        messages = build_planner_messages(
            section=_section(),
            article_topic=_topic(),
            page_art_direction="warm slate, morning light",
            brand_context="Cognify — calm, grounded brand",
            audience_persona="cto",
            target_audience="staff engineers",
            max_images=3,
        )
        # The system message contains the catalogue + persona + cliches blocks.
        flat = "\n".join(m.content for m in messages if isinstance(m.content, str))
        assert "Available visual styles" in flat
        assert "BANNED CLICHES" in flat
        # The CTO register should override the default general_business one.
        cto_register_keywords = ("engineering", "technical", "code", "ide")
        assert any(kw in flat.lower() for kw in cto_register_keywords)

    def test_default_persona_used_when_none_supplied(self) -> None:
        messages = build_planner_messages(
            section=_section(),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona=None,
            target_audience=None,
            max_images=2,
        )
        flat = "\n".join(m.content for m in messages if isinstance(m.content, str))
        assert "general business" in flat.lower() or "general_business" in flat.lower()

    def test_max_images_bound_appears_in_prompt(self) -> None:
        messages = build_planner_messages(
            section=_section(),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona="cto",
            target_audience=None,
            max_images=4,
        )
        flat = "\n".join(m.content for m in messages if isinstance(m.content, str))
        assert "4" in flat

    def test_output_shape_requests_caption_title_not_reader_meta(self) -> None:
        messages = build_planner_messages(
            section=_section(),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona="cto",
            target_audience=None,
            max_images=2,
        )
        flat = "\n".join(m.content for m in messages if isinstance(m.content, str))
        assert '"caption"' in flat
        # The planner must be told captions are plain titles, not reader meta.
        assert "do NOT describe the reader" in flat


@pytest.mark.asyncio
class TestPlanSectionImages:
    async def test_general_business_intro_returns_one_spec(self) -> None:
        llm = FakeListChatModel(responses=[GENERAL_BUSINESS_INTRO_JSON])
        specs = await plan_section_images(
            section=_section(index=0, title="Why small steps matter"),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona="general_business",
            target_audience=None,
            max_images=4,
            llm=llm,
        )
        assert len(specs) == 1
        assert specs[0].id == "intro_hero"
        assert specs[0].role_style == "hero"
        assert specs[0].visual_style == "lifestyle_photo"

    async def test_cto_deep_dive_returns_two_specs(self) -> None:
        llm = FakeListChatModel(responses=[CTO_DEEP_DIVE_JSON])
        specs = await plan_section_images(
            section=_section(index=1, title="Architecture"),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona="cto",
            target_audience="staff engineers",
            max_images=4,
            llm=llm,
        )
        assert len(specs) == 2
        assert {s.role_style for s in specs} == {"concept", "feature_card"}

    async def test_marketer_comparison(self) -> None:
        llm = FakeListChatModel(responses=[MARKETER_COMPARISON_JSON])
        specs = await plan_section_images(
            section=_section(index=2, title="Old way vs new way"),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona="marketer",
            target_audience=None,
            max_images=2,
            llm=llm,
        )
        assert len(specs) == 1
        assert specs[0].role_style == "comparison_split"

    async def test_quote_section(self) -> None:
        llm = FakeListChatModel(responses=[GENERAL_BUSINESS_QUOTE_JSON])
        specs = await plan_section_images(
            section=_section(index=3, title="A quote"),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona="general_business",
            target_audience=None,
            max_images=2,
            llm=llm,
        )
        assert len(specs) == 1
        assert specs[0].role_style == "quote_card"

    async def test_empty_response_returns_empty_list(self) -> None:
        llm = FakeListChatModel(responses=[CTO_CONCLUSION_EMPTY_JSON])
        specs = await plan_section_images(
            section=_section(index=4, title="Conclusion"),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona="cto",
            target_audience=None,
            max_images=4,
            llm=llm,
        )
        assert specs == []

    async def test_garbage_response_falls_back_to_one_spec(self) -> None:
        llm = FakeListChatModel(responses=[GARBAGE_RESPONSE])
        specs = await plan_section_images(
            section=_section(index=0, title="Intro"),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona="general_business",
            target_audience=None,
            max_images=4,
            llm=llm,
        )
        # Fallback path synthesises one spec from ROLE_STYLE_DEFAULTS.
        assert len(specs) == 1
        assert specs[0].role_style in {
            "hero",
            "feature_card",
            "concept",
            "process_step",
            "comparison_split",
            "quote_card",
            "stat_card",
            "screenshot_mock",
            "editorial",
            "background",
        }
        # Fallback IDs are deterministic and prefixed to be inspectable.
        assert specs[0].id.startswith("fallback_")

    async def test_max_images_caps_returned_specs(self) -> None:
        llm = FakeListChatModel(responses=[CTO_DEEP_DIVE_JSON])
        specs = await plan_section_images(
            section=_section(index=1, title="Architecture"),
            article_topic=_topic(),
            page_art_direction=None,
            brand_context=None,
            audience_persona="cto",
            target_audience=None,
            max_images=1,
            llm=llm,
        )
        assert len(specs) == 1


@pytest.mark.asyncio
class TestPlanArticleCover:
    async def test_general_persona_cover(self) -> None:
        llm = FakeListChatModel(responses=[COVER_HERO_GENERAL_JSON])
        cover = await plan_article_cover(
            article_title=_article().title,
            article_summary=_article().summary,
            article_domain=_article().domain,
            page_art_direction=None,
            audience_persona="general_business",
            llm=llm,
        )
        assert cover.role_style == "hero"
        assert cover.placement.anchor == "cover"
        assert cover.placement.section_index == -1

    async def test_cto_persona_cover(self) -> None:
        llm = FakeListChatModel(responses=[COVER_HERO_CTO_JSON])
        cover = await plan_article_cover(
            article_title=_article().title,
            article_summary=_article().summary,
            article_domain=_article().domain,
            page_art_direction=None,
            audience_persona="cto",
            llm=llm,
        )
        assert cover.role_style == "hero"
        assert cover.visual_style == "blueprint"

    async def test_garbage_response_falls_back_to_hero_cover(self) -> None:
        llm = FakeListChatModel(responses=[GARBAGE_RESPONSE])
        cover = await plan_article_cover(
            article_title=_article().title,
            article_summary=_article().summary,
            article_domain=_article().domain,
            page_art_direction=None,
            audience_persona="general_business",
            llm=llm,
        )
        assert cover.role_style == "hero"
        assert cover.placement.anchor == "cover"
        assert cover.id.startswith("fallback_")

    async def test_empty_response_falls_back_to_hero_cover(self) -> None:
        llm = FakeListChatModel(responses=[EMPTY_LIST_RESPONSE])
        cover = await plan_article_cover(
            article_title=_article().title,
            article_summary=_article().summary,
            article_domain=_article().domain,
            page_art_direction=None,
            audience_persona="general_business",
            llm=llm,
        )
        # Empty cover is unacceptable — the article needs a hero.
        assert cover.role_style == "hero"
        assert cover.placement.anchor == "cover"

    async def test_description_field_is_accepted_as_prompt(self) -> None:
        # Real Claude cover responses name the subject field "description"
        # (the cover system prompt used to omit the field list, so the
        # model invented its own name). This must NOT silently fall back
        # to the generic hero — every article was getting the same cover.
        cover = await plan_article_cover(
            article_title=_article().title,
            article_summary=_article().summary,
            article_domain=_article().domain,
            page_art_direction=None,
            audience_persona="general_business",
            llm=FakeListChatModel(responses=[COVER_HERO_DESCRIPTION_FIELD_JSON]),
        )
        assert not cover.id.startswith("fallback_")
        assert cover.prompt.startswith("A dimly lit, focused workspace")
        assert cover.placement.anchor == "cover"
        assert cover.placement.section_index == -1


class TestBuildCoverMessages:
    def test_cover_system_message_spells_out_the_field_list(self) -> None:
        # "Fields are the same as a section spec" is useless when the
        # section field list is not in the message — the model invents
        # field names ("description") and the cover silently degrades to
        # the fallback. The cover system prompt must carry the shape.
        from src.services.visuals.image_planner import build_cover_messages

        messages = build_cover_messages(
            article_title="The quiet refactor",
            article_summary="A quiet refactor wins over a loud rewrite.",
            article_domain="engineering",
            page_art_direction=None,
            audience_persona="general_business",
        )
        flat = "\n".join(m.content for m in messages if isinstance(m.content, str))
        assert '"prompt"' in flat
        assert '"alt_text"' in flat
        # The field list must not drag the SECTION preamble along — a cover
        # message that says "return a JSON array (zero or more)" right before
        # "return a JSON OBJECT" invites an empty-array reply.
        assert "JSON array" not in flat
        assert "JSON OBJECT" in flat
