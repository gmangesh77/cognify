"""Shared fixtures for publishing tests."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SchemaOrgAuthor,
    SEOMetadata,
    StructuredDataLD,
)


@pytest.fixture
def sample_article() -> CanonicalArticle:
    """Build a complete CanonicalArticle for publishing tests."""
    now = datetime.now(UTC).isoformat()
    return CanonicalArticle(
        title="Zero-Day Exploits in 2026",
        subtitle="A comprehensive analysis",
        body_markdown=(
            "## Introduction\n\n"
            "Zero-day exploits remain a critical threat.\n\n"
            "## Key Findings\n\n"
            "- Finding one\n- Finding two\n\n"
            "```python\nprint('hello')\n```\n"
        ),
        summary="An analysis of zero-day exploits in 2026.",
        key_claims=["Claim one", "Claim two"],
        content_type=ContentType.ANALYSIS,
        seo=SEOMetadata(
            title="Zero-Day Exploits 2026",
            description="Comprehensive analysis of zero-day threats.",
            keywords=[
                "cybersecurity", "zero-day", "exploits",
                "threats", "analysis", "2026",
            ],
            canonical_url="https://cognify.app/articles/zero-day-2026",
            structured_data=StructuredDataLD(
                headline="Zero-Day Exploits in 2026",
                description="Comprehensive analysis.",
                keywords=["cybersecurity"],
                author=SchemaOrgAuthor(),
                datePublished=now,
                dateModified=now,
            ),
        ),
        citations=[
            Citation(index=1, title="Source One", url="https://example.com/1"),
            Citation(index=2, title="Source Two", url="https://example.com/2"),
        ],
        visuals=[
            ImageAsset(
                url="https://cdn.cognify.app/img/hero.png",
                caption="Hero image",
            ),
        ],
        authors=["Cognify"],
        domain="cybersecurity",
        provenance=Provenance(
            research_session_id=uuid4(),
            primary_model="claude-sonnet-4",
            drafting_model="claude-sonnet-4",
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="v1",
        ),
    )
