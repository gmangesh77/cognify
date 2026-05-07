"""Imagen 4 provider — premium tier with native aspect support.

Aspect handling differs from Gemini: Imagen 4 honours the `aspect_ratio`
arg natively. The catalogue's `4:5` is snapped to `3:4` since Imagen 4
doesn't support 4:5 directly (`IMAGEN_ASPECT_MAP`).
"""

from __future__ import annotations

import asyncio
import time

from src.services.visuals.providers._google_base import (
    IMAGEN_ASPECT_MAP,
    import_google_genai,
    make_render_result,
)
from src.services.visuals.providers.base import (
    ImageProviderError,
    ImageRenderResult,
)

_IMAGEN_PRICE_USD_PER_IMAGE = 0.04
_DIMS_BY_ASPECT: dict[str, tuple[int, int]] = {
    "16:9": (1408, 768),
    "1:1": (1024, 1024),
    "4:3": (1280, 896),
    "3:4": (896, 1280),
}


class Imagen4Provider:
    """`imagen-4.0-generate-001` provider implementing `ImageProvider`."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "imagen-4.0-generate-001",
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ImageProviderError("imagen_4", "api_key is required")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "imagen_4"

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
        genai = import_google_genai()
        genai.configure(api_key=self._api_key)  # type: ignore[attr-defined]
        snapped_aspect = IMAGEN_ASPECT_MAP.get(aspect_ratio, "16:9")
        started = time.perf_counter()
        image_bytes = await asyncio.wait_for(
            asyncio.to_thread(self._call_imagen_sync, genai, prompt, snapped_aspect),
            timeout=self._timeout,
        )
        width, height = size_hint or _DIMS_BY_ASPECT.get(snapped_aspect, (1408, 768))
        return make_render_result(
            image_bytes=image_bytes,
            width=width,
            height=height,
            prompt_used=prompt,
            model=self._model,
            provider=self.name,
            cost_usd=_IMAGEN_PRICE_USD_PER_IMAGE,
            started=started,
        )

    def _call_imagen_sync(self, genai: object, prompt: str, aspect: str) -> bytes:
        try:
            generate = genai.generate_image  # type: ignore[attr-defined]
        except AttributeError as exc:
            raise ImageProviderError(
                "imagen_4",
                "google-generativeai SDK does not expose generate_image; "
                "Phase 6 must pin a compatible SDK version.",
            ) from exc
        try:
            response = generate(model=self._model, prompt=prompt, aspect_ratio=aspect)
        except Exception as exc:
            raise ImageProviderError("imagen_4", str(exc)) from exc
        image_bytes = _extract_image_bytes(response)
        if image_bytes is None:
            raise ImageProviderError("imagen_4", "response contained no image bytes")
        return image_bytes


def _extract_image_bytes(response: object) -> bytes | None:
    images = getattr(response, "images", None)
    if not images:
        return None
    first = images[0]
    data = getattr(first, "image_bytes", None) or getattr(first, "data", None)
    if isinstance(data, bytes) and data:
        return data
    return None


__all__ = ["Imagen4Provider"]
