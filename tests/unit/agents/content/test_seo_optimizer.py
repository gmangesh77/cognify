"""Tests for SEO metadata and AI discoverability generation."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.seo_optimizer import (
    AI_DISCLOSURE_TEXT,
    build_structured_data,
    generate_ai_discoverability,
    generate_seo_metadata,
)
from src.models.content import SEOMetadata, StructuredDataLD
from src.models.content_pipeline import (
    AIDiscoverabilityResult,
    CitationRef,
    SectionDraft,
)


def _seo_json() -> str:
    return json.dumps({
        "title": "Test Article About AI Security Trends",
        "description": "A comprehensive analysis of emerging AI security threats and mitigation strategies for 2026.",
        "keywords": ["AI security", "cybersecurity", "threat analysis", "2026 trends", "mitigation"],
    })


def _discoverability_json() -> str:
    return json.dumps({
        "summary": "This article examines emerging AI security threats in 2026.",
        "key_claims": [
            "AI-powered phishing attacks increased 300% in 2025 [1]",
            "Zero-trust architecture reduces breach risk by 60% [2]",
            "Most organizations lack AI-specific response plans [3]",
        ],
    })


def _make_section_drafts() -> list[SectionDraft]:
    return [
        SectionDraft(
            section_index=0,
            title="Introduction",
            body_markdown="AI security is evolving [1].",
            word_count=5,
            citations_used=[CitationRef(index=1, source_url="https://a.com", source_title="A")],
        ),
    ]


class TestGenerateSeoMetadata:
    async def test_happy_path(self) -> None:
        llm = FakeListChatModel(responses=[_seo_json()])
        result = await generate_seo_metadata("Test Article", "Body text here.", llm)
        assert isinstance(result, SEOMetadata)
        assert len(result.title) > 0
        assert len(result.keywords) > 0

    async def test_retries_on_bad_json(self) -> None:
        llm = FakeListChatModel(responses=["bad", _seo_json()])
        result = await generate_seo_metadata("Test", "Body.", llm)
        assert isinstance(result, SEOMetadata)

    async def test_raises_after_max_retries(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_seo_metadata("Test", "Body.", llm)


class TestGenerateAiDiscoverability:
    async def test_happy_path(self) -> None:
        llm = FakeListChatModel(responses=[_discoverability_json()])
        drafts = _make_section_drafts()
        citations = [CitationRef(index=1, source_url="https://a.com", source_title="A")]
        result = await generate_ai_discoverability(drafts, citations, llm)
        assert isinstance(result, AIDiscoverabilityResult)
        assert len(result.summary) > 0
        assert len(result.key_claims) >= 1

    async def test_retries_on_bad_json(self) -> None:
        llm = FakeListChatModel(responses=["bad", _discoverability_json()])
        result = await generate_ai_discoverability(_make_section_drafts(), [], llm)
        assert isinstance(result, AIDiscoverabilityResult)

    async def test_raises_after_max_retries(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_ai_discoverability(_make_section_drafts(), [], llm)

    async def test_truncates_long_summary(self) -> None:
        long_summary = "A" * 450 + ". " + "B" * 100 + ". Short end."
        data = json.dumps({"summary": long_summary, "key_claims": ["Claim [1]"]})
        llm = FakeListChatModel(responses=[data])
        result = await generate_ai_discoverability(_make_section_drafts(), [], llm)
        assert len(result.summary) <= 500
        assert result.summary.endswith(".")


class TestBuildStructuredData:
    def test_builds_json_ld(self) -> None:
        seo = SEOMetadata(title="Test Title", description="Test desc.", keywords=["ai", "test"])
        result = build_structured_data(seo, "My Article", "2026-03-19T00:00:00Z")
        assert isinstance(result, StructuredDataLD)
        assert result.headline == "My Article"
        assert result.description == "Test desc."

    def test_includes_keywords(self) -> None:
        seo = SEOMetadata(title="T", description="D", keywords=["k1", "k2"])
        result = build_structured_data(seo, "Title", "2026-03-19")
        assert result.keywords == ["k1", "k2"]

    def test_serializes_with_schema_org_aliases(self) -> None:
        seo = SEOMetadata(title="T", description="D", keywords=["k"])
        result = build_structured_data(seo, "Title", "2026-03-19")
        data = result.model_dump(by_alias=True)
        assert data["@context"] == "https://schema.org"
        assert data["@type"] == "Article"
        assert "datePublished" in data


class TestAiDisclosureConstant:
    def test_is_nonempty_string(self) -> None:
        assert isinstance(AI_DISCLOSURE_TEXT, str)
        assert len(AI_DISCLOSURE_TEXT) > 0
