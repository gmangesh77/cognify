"""Tests for Ghost CMS transformer."""

from src.models.content import CanonicalArticle
from src.services.publishing.ghost.transformer import GhostTransformer


class TestGhostTransformer:
    def test_platform_is_ghost(self, sample_article: CanonicalArticle) -> None:
        result = GhostTransformer().transform(sample_article)
        assert result.platform == "ghost"

    def test_article_id_matches(self, sample_article: CanonicalArticle) -> None:
        result = GhostTransformer().transform(sample_article)
        assert result.article_id == sample_article.id

    def test_converts_markdown_to_html(self, sample_article: CanonicalArticle) -> None:
        result = GhostTransformer().transform(sample_article)
        assert "<h2>" in result.content
        assert "<li>" in result.content

    def test_includes_code_blocks(self, sample_article: CanonicalArticle) -> None:
        result = GhostTransformer().transform(sample_article)
        assert "<pre>" in result.content
        assert "print(" in result.content

    def test_includes_json_ld(self, sample_article: CanonicalArticle) -> None:
        result = GhostTransformer().transform(sample_article)
        assert "application/ld+json" in result.content
        assert "schema.org" in result.content

    def test_tags_from_domain_and_keywords(
        self, sample_article: CanonicalArticle,
    ) -> None:
        result = GhostTransformer().transform(sample_article)
        tags = result.metadata["tags"]
        assert isinstance(tags, str)
        assert "cybersecurity" in tags
        assert "zero-day" in tags

    def test_featured_image_from_first_visual(
        self, sample_article: CanonicalArticle,
    ) -> None:
        result = GhostTransformer().transform(sample_article)
        assert result.metadata["feature_image"] == "https://cdn.cognify.app/img/hero.png"

    def test_no_visuals_omits_feature_image(
        self, sample_article: CanonicalArticle,
    ) -> None:
        article = sample_article.model_copy(update={"visuals": []})
        result = GhostTransformer().transform(article)
        assert "feature_image" not in result.metadata

    def test_sets_canonical_url(self, sample_article: CanonicalArticle) -> None:
        result = GhostTransformer().transform(sample_article)
        assert result.metadata["canonical_url"] == "https://cognify.app/articles/zero-day-2026"

    def test_sets_seo_metadata(self, sample_article: CanonicalArticle) -> None:
        result = GhostTransformer().transform(sample_article)
        assert result.metadata["meta_title"] == "Zero-Day Exploits 2026"
        assert "zero-day" in str(result.metadata["meta_description"])

    def test_slug_from_title(self, sample_article: CanonicalArticle) -> None:
        result = GhostTransformer().transform(sample_article)
        slug = result.metadata["slug"]
        assert isinstance(slug, str)
        assert " " not in slug
        assert slug.islower() or "-" in slug

    def test_custom_excerpt_from_summary(
        self, sample_article: CanonicalArticle,
    ) -> None:
        result = GhostTransformer().transform(sample_article)
        assert result.metadata["custom_excerpt"] == sample_article.summary
