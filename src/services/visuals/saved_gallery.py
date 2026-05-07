"""Saved visual-asset gallery aggregator (Phase 5 follow-up / VISUAL-008).

Walks every CanonicalArticle's `visuals[]` list and projects the rendered
ImageAssets into a flat, filterable feed. This is the same single-source-
of-truth design as the cost endpoint: no separate `image_assets` DB table
exists yet (that lands in VISUAL-010 Phase 7), so we aggregate from the
JSONB column the rest of the system already maintains.

Boundary invariants:
- Pure projection. Takes a list of `(article_id, article_title,
  visuals)` tuples and returns `SavedAssetEntry` rows. No DB, no I/O.
  The HTTP endpoint owns the article walk + serialisation.
- Skips legacy charts/diagrams (no `spec_id` in metadata) since the
  gallery is for AI-rendered visuals only — those are the ones the
  user wants to re-use across articles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.models.content import CanonicalArticle, ImageAsset


@dataclass(frozen=True)
class SavedAssetEntry:
    """One row in the saved-asset gallery feed."""

    spec_id: str
    article_id: str
    article_title: str
    image_url: str
    role_style: str
    visual_style: str | None
    aspect_ratio: str
    provider: str
    cost_usd: float | None
    generated_at: datetime
    alt_text: str | None
    caption: str | None


@dataclass(frozen=True)
class SavedAssetFacets:
    """Filter buckets surfaced in the gallery sidebar."""

    by_article: dict[str, int]
    by_provider: dict[str, int]
    by_role_style: dict[str, int]


@dataclass(frozen=True)
class SavedAssetFeed:
    """Top-level response. Frontend uses this to render the modal."""

    items: list[SavedAssetEntry]
    facets: SavedAssetFacets
    total_count: int
    total_spend_usd: float


def aggregate_saved_assets(
    articles: list[CanonicalArticle],
    *,
    role_style: str | None = None,
    provider: str | None = None,
    article_id: UUID | None = None,
    limit: int = 100,
) -> SavedAssetFeed:
    """Project visuals across articles into a single filterable feed.

    Filters compose: passing both `role_style` and `provider` returns the
    intersection. Newest articles come first; within an article the
    natural order of `visuals[]` is preserved.
    """
    sorted_articles = sorted(articles, key=lambda a: a.generated_at, reverse=True)
    items: list[SavedAssetEntry] = []
    article_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    total_spend = 0.0

    for article in sorted_articles:
        if article_id is not None and article.id != article_id:
            continue
        for asset in article.visuals:
            entry = _entry_from_asset(asset, article)
            if entry is None:
                continue
            if role_style is not None and entry.role_style != role_style:
                continue
            if provider is not None and entry.provider != provider:
                continue
            items.append(entry)
            article_counts[article.title] = article_counts.get(article.title, 0) + 1
            provider_counts[entry.provider] = provider_counts.get(entry.provider, 0) + 1
            role_counts[entry.role_style] = role_counts.get(entry.role_style, 0) + 1
            if entry.cost_usd is not None:
                total_spend += entry.cost_usd

    truncated = items[:limit]
    return SavedAssetFeed(
        items=truncated,
        facets=SavedAssetFacets(
            by_article=article_counts,
            by_provider=provider_counts,
            by_role_style=role_counts,
        ),
        total_count=len(items),
        total_spend_usd=round(total_spend, 4),
    )


def _entry_from_asset(
    asset: ImageAsset, article: CanonicalArticle
) -> SavedAssetEntry | None:
    """Convert one `ImageAsset` to a `SavedAssetEntry`. Skips legacy."""
    meta = asset.metadata or {}
    spec_id = meta.get("spec_id")
    provider = meta.get("provider")
    if not isinstance(spec_id, str) or not isinstance(provider, str):
        # Pre-VISUAL-005 charts/diagrams without a spec_id: not in the
        # saved-asset gallery (they're regenerated alongside the article,
        # not picked from a library).
        return None
    role_raw = meta.get("role_style")
    aspect_raw = meta.get("aspect_ratio")
    visual_style_raw = meta.get("visual_style")
    cost_raw = meta.get("cost_usd")

    cost: float | None = None
    if isinstance(cost_raw, int | float):
        cost = float(cost_raw)

    return SavedAssetEntry(
        spec_id=spec_id,
        article_id=str(article.id),
        article_title=article.title,
        image_url=asset.url,
        role_style=role_raw if isinstance(role_raw, str) else "unknown",
        visual_style=visual_style_raw
        if isinstance(visual_style_raw, str) and visual_style_raw
        else None,
        aspect_ratio=aspect_raw if isinstance(aspect_raw, str) else "16:9",
        provider=provider,
        cost_usd=cost,
        generated_at=article.generated_at,
        alt_text=asset.alt_text,
        caption=asset.caption,
    )
