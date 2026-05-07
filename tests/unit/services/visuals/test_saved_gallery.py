"""Tests for the saved-asset gallery aggregator (VISUAL-008 finish)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
)
from src.services.visuals.saved_gallery import aggregate_saved_assets


def _provenance() -> Provenance:
    return Provenance(
        research_session_id=uuid4(),
        primary_model="claude-opus-4",
        drafting_model="claude-sonnet-4",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="1.0.0",
    )


def _article(
    *,
    title: str,
    visuals: list[ImageAsset],
    generated_at: datetime | None = None,
    article_id: UUID | None = None,
) -> CanonicalArticle:
    return CanonicalArticle(
        id=article_id or uuid4(),
        title=title,
        body_markdown="# x\n\nbody",
        summary="summary",
        key_claims=["claim"],
        content_type=ContentType.ARTICLE,
        seo=SEOMetadata(title="t", description="d"),
        citations=[Citation(index=1, title="s", url="https://e.test/1")],
        visuals=visuals,
        authors=["Cognify"],
        domain="engineering",
        generated_at=generated_at or datetime.now(UTC),
        provenance=_provenance(),
    )


def _planned_asset(
    *,
    spec_id: str,
    role_style: str = "hero",
    provider: str = "gemini_flash",
    cost_usd: float | None = 0.001,
    visual_style: str | None = "lifestyle_photo",
    aspect: str = "16:9",
    url: str | None = None,
) -> ImageAsset:
    return ImageAsset(
        url=url or f"/visuals/{spec_id}.png",
        alt_text=f"alt {spec_id}",
        caption=f"caption {spec_id}",
        metadata={
            "spec_id": spec_id,
            "role_style": role_style,
            "visual_style": visual_style or "",
            "aspect_ratio": aspect,
            "provider": provider,
            "model": f"{provider}-model",
            "cost_usd": cost_usd,
            "generation_ms": 100,
        },
    )


def _legacy_chart() -> ImageAsset:
    """Pre-VISUAL-005 chart asset with no spec_id."""
    return ImageAsset(
        url="/charts/x.png",
        metadata={"type": "chart", "source_section": 1},
    )


class TestAggregateSavedAssets:
    def test_empty_input_yields_empty_feed(self) -> None:
        feed = aggregate_saved_assets([])
        assert feed.items == []
        assert feed.total_count == 0
        assert feed.total_spend_usd == 0.0

    def test_skips_legacy_chart_visuals(self) -> None:
        article = _article(
            title="Mixed",
            visuals=[
                _legacy_chart(),
                _planned_asset(spec_id="hero1"),
            ],
        )
        feed = aggregate_saved_assets([article])
        assert feed.total_count == 1
        assert feed.items[0].spec_id == "hero1"

    def test_sorts_by_generated_at_descending(self) -> None:
        now = datetime.now(UTC)
        old = _article(
            title="Old",
            visuals=[_planned_asset(spec_id="old1")],
            generated_at=now - timedelta(days=2),
        )
        recent = _article(
            title="Recent",
            visuals=[_planned_asset(spec_id="rec1")],
            generated_at=now,
        )
        feed = aggregate_saved_assets([old, recent])
        assert [e.spec_id for e in feed.items] == ["rec1", "old1"]

    def test_role_style_filter_intersection(self) -> None:
        article = _article(
            title="Mixed",
            visuals=[
                _planned_asset(spec_id="hero1", role_style="hero"),
                _planned_asset(spec_id="card1", role_style="feature_card"),
            ],
        )
        feed = aggregate_saved_assets([article], role_style="hero")
        assert [e.spec_id for e in feed.items] == ["hero1"]

    def test_provider_filter(self) -> None:
        article = _article(
            title="Mixed providers",
            visuals=[
                _planned_asset(spec_id="a", provider="gemini_flash"),
                _planned_asset(spec_id="b", provider="imagen_4"),
            ],
        )
        feed = aggregate_saved_assets([article], provider="imagen_4")
        assert [e.spec_id for e in feed.items] == ["b"]

    def test_article_id_filter(self) -> None:
        kept_id = uuid4()
        kept = _article(
            title="Kept",
            visuals=[_planned_asset(spec_id="keep")],
            article_id=kept_id,
        )
        other = _article(
            title="Other",
            visuals=[_planned_asset(spec_id="other")],
        )
        feed = aggregate_saved_assets([kept, other], article_id=kept_id)
        assert [e.spec_id for e in feed.items] == ["keep"]

    def test_facets_count_each_dimension(self) -> None:
        a1 = _article(
            title="A1",
            visuals=[
                _planned_asset(spec_id="x", provider="gemini_flash"),
                _planned_asset(spec_id="y", provider="imagen_4"),
            ],
        )
        a2 = _article(
            title="A2",
            visuals=[
                _planned_asset(spec_id="z", provider="gemini_flash"),
            ],
        )
        feed = aggregate_saved_assets([a1, a2])
        assert feed.facets.by_provider == {
            "gemini_flash": 2,
            "imagen_4": 1,
        }
        assert feed.facets.by_article == {"A1": 2, "A2": 1}

    def test_total_spend_sums_cost_usd(self) -> None:
        article = _article(
            title="Spend",
            visuals=[
                _planned_asset(spec_id="a", cost_usd=0.001),
                _planned_asset(spec_id="b", cost_usd=0.04),
                _planned_asset(spec_id="c", cost_usd=None),
            ],
        )
        feed = aggregate_saved_assets([article])
        assert feed.total_count == 3
        assert feed.total_spend_usd == 0.041

    def test_limit_truncates_items_but_not_facets(self) -> None:
        article = _article(
            title="Many",
            visuals=[_planned_asset(spec_id=f"id{i}") for i in range(5)],
        )
        feed = aggregate_saved_assets([article], limit=2)
        assert len(feed.items) == 2
        assert feed.total_count == 5
