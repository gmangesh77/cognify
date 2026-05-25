"""Tests for DalleThreeProvider — wraps existing OpenAIDalleGenerator."""

from __future__ import annotations

import pytest

from src.services.visuals.providers.base import ImageProviderError
from src.services.visuals.providers.dalle_3 import DalleThreeProvider


class _StubGenerator:
    """Stub OpenAIDalleGenerator for tests — never hits the network."""

    def __init__(self, payload: bytes | None = b"\x89PNG-stub") -> None:
        self.payload = payload
        self.calls: list[tuple[str, tuple[int, int]]] = []

    async def generate(self, prompt: str, size: tuple[int, int]) -> bytes | None:
        self.calls.append((prompt, size))
        return self.payload


@pytest.mark.asyncio
async def test_render_returns_image_render_result() -> None:
    gen = _StubGenerator(payload=b"\x89PNG\r\n\x1a\n")
    provider = DalleThreeProvider(api_key="sk-test", generator=gen)  # type: ignore[arg-type]
    result = await provider.render(prompt="hero", aspect_ratio="16:9")
    assert provider.name == "dalle_3"
    assert provider.model == "dall-e-3"
    assert result.provider == "dalle_3"
    assert result.image_bytes == b"\x89PNG\r\n\x1a\n"
    assert result.cost_usd == 0.04
    # gpt-image-1 landscape size (the new default after OpenAI deprecated
    # dall-e-3's 1792x1024 dimensions on newer accounts).
    assert result.width == 1536
    assert result.height == 1024


@pytest.mark.asyncio
async def test_render_respects_size_hint() -> None:
    gen = _StubGenerator()
    provider = DalleThreeProvider(api_key="sk-test", generator=gen)  # type: ignore[arg-type]
    result = await provider.render(
        prompt="square hero", aspect_ratio="1:1", size_hint=(1024, 1024)
    )
    assert result.width == 1024
    assert result.height == 1024
    assert gen.calls[0][1] == (1024, 1024)


@pytest.mark.asyncio
async def test_render_maps_aspect_to_size() -> None:
    gen = _StubGenerator()
    provider = DalleThreeProvider(api_key="sk-test", generator=gen)  # type: ignore[arg-type]
    await provider.render(prompt="x", aspect_ratio="3:4")
    # Portrait gpt-image-1 size (replaces dall-e-3's 1024x1792).
    assert gen.calls[0][1] == (1024, 1536)


@pytest.mark.asyncio
async def test_render_raises_when_generator_returns_none() -> None:
    gen = _StubGenerator(payload=None)
    provider = DalleThreeProvider(api_key="sk-test", generator=gen)  # type: ignore[arg-type]
    with pytest.raises(ImageProviderError) as ei:
        await provider.render(prompt="x", aspect_ratio="16:9")
    assert ei.value.provider == "dalle_3"


def test_constructor_rejects_empty_api_key() -> None:
    with pytest.raises(ImageProviderError):
        DalleThreeProvider(api_key="")


@pytest.mark.asyncio
async def test_render_records_latency() -> None:
    gen = _StubGenerator()
    provider = DalleThreeProvider(api_key="sk-test", generator=gen)  # type: ignore[arg-type]
    result = await provider.render(prompt="x", aspect_ratio="16:9")
    assert result.latency_ms >= 0
