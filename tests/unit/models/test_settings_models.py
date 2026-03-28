"""Unit tests for settings Pydantic models."""

from src.models.settings import (
    ApiKeyConfig,
    DomainConfig,
    GeneralConfig,
    LlmConfig,
    SeoDefaults,
)


class TestDomainConfig:
    def test_defaults(self) -> None:
        d = DomainConfig(name="Cybersecurity")
        assert d.status == "active"
        assert d.trend_sources == []
        assert d.keywords == []
        assert d.article_count == 0
        assert d.id is not None

    def test_custom_values(self) -> None:
        d = DomainConfig(
            name="AI",
            status="inactive",
            trend_sources=["hackernews", "reddit"],
            keywords=["machine learning"],
            article_count=5,
        )
        assert d.name == "AI"
        assert d.status == "inactive"
        assert "hackernews" in d.trend_sources


class TestApiKeyConfig:
    def test_defaults(self) -> None:
        k = ApiKeyConfig(service="anthropic")
        assert k.masked_key == ""
        assert k.status == "active"
        assert k.id is not None

    def test_service_stored(self) -> None:
        k = ApiKeyConfig(service="serpapi", masked_key="sk-serp••••••••1234")
        assert k.service == "serpapi"
        assert "••••••••" in k.masked_key


class TestLlmConfig:
    def test_defaults(self) -> None:
        c = LlmConfig()
        assert c.primary_model == "claude-opus-4"
        assert c.drafting_model == "claude-sonnet-4"
        assert c.image_generation == "stable-diffusion-xl"

    def test_override(self) -> None:
        c = LlmConfig(primary_model="claude-opus-4-5")
        assert c.primary_model == "claude-opus-4-5"


class TestSeoDefaults:
    def test_all_true_by_default(self) -> None:
        s = SeoDefaults()
        assert s.auto_meta_tags is True
        assert s.keyword_optimization is True
        assert s.auto_cover_images is True
        assert s.include_citations is True
        assert s.human_review_before_publish is True

    def test_can_disable_flags(self) -> None:
        s = SeoDefaults(auto_meta_tags=False, human_review_before_publish=False)
        assert s.auto_meta_tags is False
        assert s.human_review_before_publish is False


class TestGeneralConfig:
    def test_defaults(self) -> None:
        g = GeneralConfig()
        assert g.article_length_target == "3000-5000"
        assert g.content_tone == "professional"

    def test_override(self) -> None:
        g = GeneralConfig(content_tone="casual")
        assert g.content_tone == "casual"
