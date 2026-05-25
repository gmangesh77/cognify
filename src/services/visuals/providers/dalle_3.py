"""DALL-E 3 provider — adapter over the existing OpenAIDalleGenerator.

Implements `ImageProvider`. Maps the catalogue's aspect ratios onto
DALL-E 3's three supported sizes (1024x1024, 1024x1792, 1792x1024) and
returns the bytes alongside provenance metadata for cost auditing.
"""

from __future__ import annotations

import time

from src.agents.content.illustration_generator import OpenAIDalleGenerator
from src.services.visuals.providers.base import (
    ImageProviderError,
    ImageRenderResult,
)

_DALLE_PRICE_USD_PER_IMAGE = 0.04  # standard quality (approx; gpt-image-1 varies by quality tier)
# gpt-image-1 sizes: 1024x1024 | 1536x1024 | 1024x1536 (or "auto").
# dall-e-3 sizes (legacy): 1024x1024 | 1792x1024 | 1024x1792.
# We pick gpt-image-1 dimensions by default; dall-e-3 accepts the 1024
# square but not the 1536 dimensions, so legacy accounts should override.
_ASPECT_TO_SIZE: dict[str, tuple[int, int]] = {
    "16:9": (1536, 1024),
    "4:3": (1536, 1024),  # closest landscape
    "1:1": (1024, 1024),
    "3:4": (1024, 1536),  # closest portrait
    "4:5": (1024, 1536),
}


class DalleThreeProvider:
    """OpenAI DALL-E 3 image provider implementing `ImageProvider`."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "dall-e-3",
        timeout: float = 30.0,
        generator: OpenAIDalleGenerator | None = None,
    ) -> None:
        if not api_key:
            raise ImageProviderError("dalle_3", "api_key is required")
        self._model = model
        self._generator = generator or OpenAIDalleGenerator(
            api_key=api_key, model=model, timeout=timeout
        )

    @property
    def name(self) -> str:
        return "dalle_3"

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
        size = _ASPECT_TO_SIZE.get(aspect_ratio, (1792, 1024))
        if size_hint is not None:
            size = size_hint
        start = time.perf_counter()
        image_bytes = await self._generator.generate(prompt, size)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if image_bytes is None:
            raise ImageProviderError(
                "dalle_3", "generator returned None (see provider logs)"
            )
        return ImageRenderResult(
            image_bytes=image_bytes,
            mime_type="image/png",
            width=size[0],
            height=size[1],
            prompt_used=prompt,
            model=self._model,
            provider=self.name,
            cost_usd=_DALLE_PRICE_USD_PER_IMAGE,
            latency_ms=latency_ms,
        )


__all__ = ["DalleThreeProvider"]
