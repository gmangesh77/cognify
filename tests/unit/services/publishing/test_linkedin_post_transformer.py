"""Tests for LinkedInPostTransformer (AUTHOR-013)."""

from __future__ import annotations

from src.models.content import CanonicalArticle
from src.services.publishing.linkedin.post_transformer import LinkedInPostTransformer
from src.services.publishing.linkedin.transformer import LinkedInTransformer


class TestLinkedInPostTransformer:
    def test_platform_key(self, sample_article: CanonicalArticle) -> None:
        result = LinkedInPostTransformer().transform(sample_article)
        assert result.platform == "linkedin_post"

    def test_metadata_equals_linkedin_transformer(
        self, sample_article: CanonicalArticle
    ) -> None:
        post_result = LinkedInPostTransformer().transform(sample_article)
        legacy_result = LinkedInTransformer().transform(sample_article)
        assert post_result.metadata == legacy_result.metadata

    def test_fallback_body_non_empty(self, sample_article: CanonicalArticle) -> None:
        result = LinkedInPostTransformer().transform(sample_article)
        assert result.content.strip() != ""

    def test_article_id_matches(self, sample_article: CanonicalArticle) -> None:
        result = LinkedInPostTransformer().transform(sample_article)
        assert result.article_id == sample_article.id

    def test_pure_no_io(self, sample_article: CanonicalArticle) -> None:
        # Two calls with the same article produce byte-identical output —
        # no hidden I/O or non-determinism.
        transformer = LinkedInPostTransformer()
        first = transformer.transform(sample_article)
        second = transformer.transform(sample_article)
        assert first.content == second.content
        assert first.metadata == second.metadata
