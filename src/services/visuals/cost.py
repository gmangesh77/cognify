"""Per-article visual-generation cost aggregator (Phase 6 / VISUAL-009).

Reads `ImageAsset.metadata` (the §4.2 extension shipped in VISUAL-005)
and produces a structured cost breakdown. Pure: takes a list of assets
and returns a `CostBreakdown` — no DB, no I/O. The HTTP endpoint owns
the article lookup and serialisation.

The metadata fields we depend on:
- `provider`: str — provider key (gemini_flash, imagen_4, …)
- `model`: str — concrete model identifier
- `cost_usd`: float | None — per-render cost from the provider
- `generation_ms`: int — wall-clock latency
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.content import ImageAsset


@dataclass(frozen=True)
class ProviderCostEntry:
    """Cost roll-up for one provider key."""

    provider: str
    model: str
    count: int
    total_usd: float
    avg_latency_ms: int


@dataclass(frozen=True)
class CostBreakdown:
    """Per-article cost breakdown."""

    total_usd: float
    image_count: int
    breakdown: list[ProviderCostEntry]


@dataclass
class _ProviderBucket:
    """Mutable accumulator keyed on provider name during aggregation."""

    model: str = ""
    count: int = 0
    total_usd: float = 0.0
    latency_sum: int = 0


def aggregate_cost(visuals: list[ImageAsset]) -> CostBreakdown:
    """Aggregate cost across a list of `ImageAsset` rows.

    Assets without a provider tag (legacy charts/diagrams pre-VISUAL-005)
    are skipped — they don't carry cost metadata. Assets with
    `cost_usd=None` count toward the image total but contribute $0.
    """
    grouped: dict[str, _ProviderBucket] = {}
    total_usd = 0.0
    counted = 0
    for asset in visuals:
        meta = asset.metadata or {}
        provider = meta.get("provider")
        if not isinstance(provider, str) or not provider:
            continue
        model_raw = meta.get("model")
        model = model_raw if isinstance(model_raw, str) else "unknown"
        cost_raw = meta.get("cost_usd")
        cost = float(cost_raw) if isinstance(cost_raw, int | float) else 0.0
        latency_raw = meta.get("generation_ms")
        latency = int(latency_raw) if isinstance(latency_raw, int | float) else 0
        bucket = grouped.setdefault(provider, _ProviderBucket(model=model))
        bucket.count += 1
        bucket.total_usd += cost
        bucket.latency_sum += latency
        # Keep first non-empty model — providers don't usually mix models
        # within an article.
        if not bucket.model and model:
            bucket.model = model
        total_usd += cost
        counted += 1

    breakdown: list[ProviderCostEntry] = []
    for provider, bucket in sorted(grouped.items()):
        avg_latency = bucket.latency_sum // bucket.count if bucket.count > 0 else 0
        breakdown.append(
            ProviderCostEntry(
                provider=provider,
                model=bucket.model,
                count=bucket.count,
                total_usd=round(bucket.total_usd, 6),
                avg_latency_ms=avg_latency,
            )
        )
    return CostBreakdown(
        total_usd=round(total_usd, 6),
        image_count=counted,
        breakdown=breakdown,
    )


__all__ = ["CostBreakdown", "ProviderCostEntry", "aggregate_cost"]
