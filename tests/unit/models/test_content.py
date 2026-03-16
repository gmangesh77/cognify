"""Tests for content pipeline models."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
)


def _make_seo() -> SEOMetadata:
    return SEOMetadata(
        title="Test Article Title",
        description="A test article description for SEO purposes.",
        keywords=["test", "article"],
    )


def _make_citation() -> Citation:
    return Citation(index=1, title="Source Paper", url="https://example.com/paper")


def _make_provenance() -> Provenance:
    return Provenance(
        research_session_id=uuid4(),
        primary_model="claude-opus-4",
        drafting_model="claude-sonnet-4",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="1.0.0",
    )


def _make_article(**overrides: object) -> CanonicalArticle:
    defaults = {
        "title": "Test Article",
        "body_markdown": "# Heading\n\nBody content [1].",
        "summary": "A test article summary.",
        "key_claims": ["Claim one backed by source [1]."],
        "content_type": ContentType.ARTICLE,
        "seo": _make_seo(),
        "citations": [_make_citation()],
        "authors": ["Cognify Research"],
        "domain": "cybersecurity",
        "provenance": _make_provenance(),
    }
    defaults.update(overrides)
    return CanonicalArticle(**defaults)


class TestSEOMetadata:
    def test_valid_construction(self):
        seo = SEOMetadata(
            title="Valid Title",
            description="Valid description.",
            keywords=["seo"],
        )
        assert seo.title == "Valid Title"
        assert seo.canonical_url is None

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            SEOMetadata(title="", description="Valid.")

    def test_empty_description_rejected(self):
        with pytest.raises(ValidationError):
            SEOMetadata(title="Valid", description="")

    def test_title_over_max_rejected(self):
        with pytest.raises(ValidationError):
            SEOMetadata(title="x" * 71, description="Valid.")

    def test_description_over_max_rejected(self):
        with pytest.raises(ValidationError):
            SEOMetadata(title="Valid", description="x" * 171)


class TestCitation:
    def test_valid_construction(self):
        c = Citation(index=1, title="Paper", url="https://example.com")
        assert c.index == 1
        assert c.authors == []
        assert c.published_at is None

    def test_index_zero_rejected(self):
        with pytest.raises(ValidationError):
            Citation(index=0, title="Paper", url="https://example.com")

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            Citation(index=1, title="", url="https://example.com")


class TestImageAsset:
    def test_valid_construction(self):
        img = ImageAsset(url="https://example.com/image.png")
        assert isinstance(img.id, UUID)
        assert img.caption is None
        assert img.metadata == {}

    def test_metadata_accepts_mixed_types(self):
        img = ImageAsset(
            url="https://example.com/img.png",
            metadata={"width": 1024, "height": 768, "format": "png", "dpi": 72.0},
        )
        assert img.metadata["width"] == 1024
        assert img.metadata["format"] == "png"


class TestProvenance:
    def test_valid_construction(self):
        p = _make_provenance()
        assert isinstance(p.research_session_id, UUID)
        assert p.primary_model == "claude-opus-4"

    def test_empty_model_rejected(self):
        with pytest.raises(ValidationError):
            Provenance(
                research_session_id=uuid4(),
                primary_model="",
                drafting_model="claude-sonnet-4",
                embedding_model="all-MiniLM-L6-v2",
                embedding_version="1.0.0",
            )


class TestContentType:
    def test_values(self):
        assert ContentType.ARTICLE == "article"
        assert ContentType.HOW_TO == "how-to"
        assert ContentType.ANALYSIS == "analysis"
        assert ContentType.REPORT == "report"


class TestCanonicalArticle:
    def test_valid_construction(self):
        article = _make_article()
        assert isinstance(article.id, UUID)
        assert article.title == "Test Article"
        assert article.ai_generated is True
        assert isinstance(article.generated_at, datetime)

    def test_round_trip_serialization(self):
        article = _make_article()
        data = article.model_dump()
        restored = CanonicalArticle.model_validate(data)
        assert restored.title == article.title
        assert restored.citations[0].index == 1

    def test_frozen_immutability(self):
        article = _make_article()
        with pytest.raises(ValidationError):
            article.title = "Modified"

    def test_missing_title_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(title=None)

    def test_empty_citations_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(citations=[])

    def test_empty_authors_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(authors=[])

    def test_empty_key_claims_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(key_claims=[])

    def test_invalid_content_type_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(content_type="blog-post")

    def test_optional_subtitle_none(self):
        article = _make_article(subtitle=None)
        assert article.subtitle is None

    def test_optional_visuals_empty(self):
        article = _make_article(visuals=[])
        assert article.visuals == []

    def test_default_id_generated(self):
        a1 = _make_article()
        a2 = _make_article()
        assert a1.id != a2.id

    def test_nested_invalid_seo_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(seo=SEOMetadata(title="", description="Valid."))

    def test_missing_body_markdown_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(body_markdown=None)

    def test_missing_summary_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(summary=None)

    def test_missing_seo_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(seo=None)

    def test_missing_provenance_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(provenance=None)
