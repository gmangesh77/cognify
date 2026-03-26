"""Tests for Medium transformer."""

from src.models.content import CanonicalArticle
from src.services.publishing.medium.transformer import MediumTransformer


class TestMediumTransformer:
    def test_platform_is_medium(self, sample_article: CanonicalArticle) -> None:
        result = MediumTransformer().transform(sample_article)
        assert result.platform == "medium"

    def test_article_id_matches(self, sample_article: CanonicalArticle) -> None:
        result = MediumTransformer().transform(sample_article)
        assert result.article_id == sample_article.id

    def test_converts_markdown_to_html(self, sample_article: CanonicalArticle) -> None:
        result = MediumTransformer().transform(sample_article)
        assert "<h2>" in result.content

    def test_limits_tags_to_five(self, sample_article: CanonicalArticle) -> None:
        result = MediumTransformer().transform(sample_article)
        tags = str(result.metadata["tags"]).split(",")
        assert len(tags) <= 5

    def test_sets_canonical_url(self, sample_article: CanonicalArticle) -> None:
        result = MediumTransformer().transform(sample_article)
        assert result.metadata["canonicalUrl"] == "https://cognify.app/articles/zero-day-2026"

    def test_content_format_is_html(self, sample_article: CanonicalArticle) -> None:
        result = MediumTransformer().transform(sample_article)
        assert result.metadata["contentFormat"] == "html"

    def test_no_canonical_url_omits_field(
        self, sample_article: CanonicalArticle,
    ) -> None:
        seo = sample_article.seo.model_copy(update={"canonical_url": None})
        article = sample_article.model_copy(update={"seo": seo})
        result = MediumTransformer().transform(article)
        assert "canonicalUrl" not in result.metadata
