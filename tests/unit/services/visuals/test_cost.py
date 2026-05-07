"""Tests for the visual-generation cost aggregator (Phase 6 / VISUAL-009)."""

from __future__ import annotations

from src.models.content import ImageAsset
from src.services.visuals.cost import aggregate_cost


def _asset(
    *,
    provider: str | None = "gemini_flash",
    model: str = "gemini-2.5-flash-image",
    cost_usd: float | None = 0.001,
    generation_ms: int = 100,
) -> ImageAsset:
    metadata: dict[str, str | int | float | None] = {}
    if provider is not None:
        metadata["provider"] = provider
    metadata["model"] = model
    metadata["cost_usd"] = cost_usd
    metadata["generation_ms"] = generation_ms
    return ImageAsset(url="/visuals/x.png", metadata=metadata)


class TestAggregateCost:
    def test_empty_list_zero_total(self) -> None:
        result = aggregate_cost([])
        assert result.total_usd == 0.0
        assert result.image_count == 0
        assert result.breakdown == []

    def test_groups_by_provider(self) -> None:
        result = aggregate_cost(
            [
                _asset(provider="gemini_flash", cost_usd=0.001),
                _asset(provider="gemini_flash", cost_usd=0.001),
                _asset(provider="imagen_4", cost_usd=0.04),
            ]
        )
        assert result.image_count == 3
        assert result.total_usd == 0.042
        providers = {entry.provider for entry in result.breakdown}
        assert providers == {"gemini_flash", "imagen_4"}
        flash = next(e for e in result.breakdown if e.provider == "gemini_flash")
        assert flash.count == 2
        assert flash.total_usd == 0.002

    def test_skips_assets_without_provider(self) -> None:
        legacy = ImageAsset(
            url="/charts/x.png",
            metadata={"type": "chart", "source_section": 1},
        )
        result = aggregate_cost(
            [legacy, _asset(provider="gemini_flash", cost_usd=0.001)]
        )
        assert result.image_count == 1
        assert result.total_usd == 0.001

    def test_treats_none_cost_as_zero(self) -> None:
        result = aggregate_cost(
            [
                _asset(provider="gemini_flash", cost_usd=None),
                _asset(provider="gemini_flash", cost_usd=0.001),
            ]
        )
        assert result.image_count == 2
        assert result.total_usd == 0.001
        flash = next(e for e in result.breakdown if e.provider == "gemini_flash")
        assert flash.count == 2

    def test_average_latency(self) -> None:
        result = aggregate_cost(
            [
                _asset(provider="gemini_flash", generation_ms=100),
                _asset(provider="gemini_flash", generation_ms=300),
            ]
        )
        flash = next(e for e in result.breakdown if e.provider == "gemini_flash")
        assert flash.avg_latency_ms == 200

    def test_breakdown_is_sorted_alphabetically(self) -> None:
        result = aggregate_cost(
            [
                _asset(provider="imagen_4"),
                _asset(provider="dalle_3"),
                _asset(provider="gemini_flash"),
            ]
        )
        assert [e.provider for e in result.breakdown] == [
            "dalle_3",
            "gemini_flash",
            "imagen_4",
        ]

    def test_rounded_to_six_decimals(self) -> None:
        result = aggregate_cost(
            [_asset(provider="gemini_flash", cost_usd=0.0010001234567)]
        )
        assert result.total_usd == 0.001
