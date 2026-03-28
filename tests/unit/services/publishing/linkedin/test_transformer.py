"""Tests for LinkedIn transformer."""

from src.models.content import CanonicalArticle
from src.services.publishing.linkedin.transformer import LinkedInTransformer


class TestLinkedInTransformer:
    def test_platform_is_linkedin(self, sample_article: CanonicalArticle) -> None:
        result = LinkedInTransformer().transform(sample_article)
        assert result.platform == "linkedin"

    def test_article_id_matches(self, sample_article: CanonicalArticle) -> None:
        result = LinkedInTransformer().transform(sample_article)
        assert result.article_id == sample_article.id

    def test_commentary_includes_title(
        self, sample_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(sample_article)
        assert sample_article.title in result.content

    def test_commentary_includes_summary(
        self, sample_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(sample_article)
        assert sample_article.summary in result.content

    def test_commentary_includes_hashtags(
        self, sample_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(sample_article)
        assert "#cybersecurity" in result.content

    def test_hashtags_limited_to_five(
        self, sample_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(sample_article)
        hashtag_count = result.content.count("#")
        assert hashtag_count <= 5

    def test_metadata_has_source_url(
        self, sample_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(sample_article)
        assert (
            result.metadata["source_url"]
            == "https://cognify.app/articles/zero-day-2026"
        )

    def test_metadata_has_title(self, sample_article: CanonicalArticle) -> None:
        result = LinkedInTransformer().transform(sample_article)
        assert result.metadata["title"] == sample_article.title

    def test_metadata_has_description(
        self, sample_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(sample_article)
        desc = str(result.metadata["description"])
        assert len(desc) <= 256
        assert desc.startswith("An analysis")

    def test_no_canonical_url_uses_empty(
        self, sample_article: CanonicalArticle
    ) -> None:
        seo = sample_article.seo.model_copy(update={"canonical_url": None})
        article = sample_article.model_copy(update={"seo": seo})
        result = LinkedInTransformer().transform(article)
        assert result.metadata["source_url"] == ""

    def test_commentary_under_3000_chars(
        self, sample_article: CanonicalArticle
    ) -> None:
        result = LinkedInTransformer().transform(sample_article)
        assert len(result.content) <= 3000
