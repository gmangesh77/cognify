"""Tests for ImageProviderRegistry.

Mirrors the TrendSource registry test patterns. Uses a tiny stub provider
to exercise register/get/has/available without pulling in real provider
clients (which would require network).
"""

from __future__ import annotations

import pytest

from src.services.visuals.providers.base import (
    ImageProvider,
    ImageRenderResult,
)
from src.services.visuals.registry import ImageProviderRegistry


class _StubProvider:
    """Minimal ImageProvider for registry tests."""

    def __init__(self, name: str, model: str = "stub-1") -> None:
        self._name = name
        self._model = model

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    async def render(
        self,
        *,
        prompt: str,
        aspect_ratio: str,
        size_hint: tuple[int, int] | None = None,
    ) -> ImageRenderResult:
        return ImageRenderResult(
            image_bytes=b"x",
            width=1,
            height=1,
            prompt_used=prompt,
            model=self._model,
            provider=self._name,
            cost_usd=0.0,
            latency_ms=0,
        )


def test_register_and_get() -> None:
    registry = ImageProviderRegistry()
    provider: ImageProvider = _StubProvider("gemini_flash")
    registry.register(provider)
    assert registry.get("gemini_flash") is provider


def test_get_missing_raises_keyerror() -> None:
    registry = ImageProviderRegistry()
    with pytest.raises(KeyError):
        registry.get("imagen_4")


def test_has_returns_correct_membership() -> None:
    registry = ImageProviderRegistry()
    registry.register(_StubProvider("dalle_3"))
    assert registry.has("dalle_3") is True
    assert registry.has("imagen_4") is False


def test_register_overwrites_existing_by_name() -> None:
    registry = ImageProviderRegistry()
    first = _StubProvider("gemini_flash", model="2.5-old")
    second = _StubProvider("gemini_flash", model="2.5-new")
    registry.register(first)
    registry.register(second)
    assert registry.get("gemini_flash") is second
    assert registry.get("gemini_flash").model == "2.5-new"


def test_available_providers_returns_sorted_names() -> None:
    registry = ImageProviderRegistry()
    registry.register(_StubProvider("imagen_4"))
    registry.register(_StubProvider("gemini_flash"))
    registry.register(_StubProvider("dalle_3"))
    assert registry.available_providers() == [
        "dalle_3",
        "gemini_flash",
        "imagen_4",
    ]


def test_get_all_returns_copy_not_internal_dict() -> None:
    registry = ImageProviderRegistry()
    registry.register(_StubProvider("gemini_flash"))
    snapshot = registry.get_all()
    snapshot["mutated"] = _StubProvider("mutated")  # type: ignore[assignment]
    assert "mutated" not in registry.available_providers()
