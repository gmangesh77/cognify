"""Shared scaffolding for Google AI image providers.

Houses the lazy import of `google.generativeai`, the aspect-instruction
helper used by Gemini Flash (which ignores the aspect arg), and the
Imagen aspect-snap map. Concrete providers (`gemini_flash`,
`gemini_3_pro`, `imagen_4`) inherit nothing structurally — Python's
duck typing makes that pointless — but they all share these helpers.
"""

from __future__ import annotations

import importlib
import time

from src.services.visuals.providers.base import (
    ImageProviderError,
    ImageProviderTimeoutError,
    ImageRenderResult,
)

# Imagen 4 native aspect support; map non-native aspects to nearest neighbour.
IMAGEN_ASPECT_MAP: dict[str, str] = {
    "16:9": "16:9",
    "4:3": "4:3",
    "1:1": "1:1",
    "3:4": "3:4",
    "4:5": "3:4",  # snap 4:5 → 3:4
}


def aspect_instruction(aspect: str) -> str:
    """Sentence injected into the prompt for providers without a native aspect arg."""
    return (
        f"Render in {aspect} aspect ratio. "
        f"The composition must fit a {aspect} canvas exactly."
    )


def import_google_genai() -> object:
    """Lazy-load `google.generativeai`; raise a clear error if missing."""
    try:
        return importlib.import_module("google.generativeai")
    except ImportError as exc:
        raise ImageProviderError(
            "google_ai",
            "The 'google-generativeai' package is not installed. "
            "Add it via `uv add google-generativeai` to enable Gemini/Imagen "
            "providers (Phase 2 wiring depends on it).",
        ) from exc


def make_render_result(
    *,
    image_bytes: bytes,
    width: int,
    height: int,
    prompt_used: str,
    model: str,
    provider: str,
    cost_usd: float | None,
    started: float,
) -> ImageRenderResult:
    """Convenience: wrap raw bytes + metadata into an `ImageRenderResult`."""
    return ImageRenderResult(
        image_bytes=image_bytes,
        mime_type="image/png",
        width=width,
        height=height,
        prompt_used=prompt_used,
        model=model,
        provider=provider,
        cost_usd=cost_usd,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )


__all__ = [
    "IMAGEN_ASPECT_MAP",
    "ImageProviderError",
    "ImageProviderTimeoutError",
    "aspect_instruction",
    "import_google_genai",
    "make_render_result",
]
