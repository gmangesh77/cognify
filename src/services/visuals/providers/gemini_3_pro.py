"""Gemini 3 Pro Image Preview provider.

Same shape as `GeminiFlashProvider` but targets the higher-quality
`gemini-3-pro-image-preview` model and uses a different cost estimate.
The model is gated behind `gemini_3_pro_enabled` in settings.
"""

from __future__ import annotations

import asyncio
import time

from src.services.visuals.providers._google_base import (
    aspect_instruction,
    import_google_genai,
    make_render_result,
)
from src.services.visuals.providers.base import (
    ImageProviderError,
    ImageRenderResult,
)

_PRO_PRICE_USD_PER_IMAGE = 0.01
_DEFAULT_DIMS: dict[str, tuple[int, int]] = {
    "16:9": (1600, 900),
    "1:1": (1024, 1024),
    "4:3": (1280, 960),
    "3:4": (960, 1280),
    "4:5": (1024, 1280),
}


class Gemini3ProProvider:
    """`gemini-3-pro-image-preview` provider implementing `ImageProvider`."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-3-pro-image-preview",
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ImageProviderError("gemini_3_pro", "api_key is required")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "gemini_3_pro"

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
        injected_prompt = f"{prompt}\n\n{aspect_instruction(aspect_ratio)}"
        started = time.perf_counter()
        image_bytes = await asyncio.wait_for(
            asyncio.to_thread(self._call_genai_sync, genai, injected_prompt),
            timeout=self._timeout,
        )
        width, height = size_hint or _DEFAULT_DIMS.get(aspect_ratio, (1600, 900))
        return make_render_result(
            image_bytes=image_bytes,
            width=width,
            height=height,
            prompt_used=injected_prompt,
            model=self._model,
            provider=self.name,
            cost_usd=_PRO_PRICE_USD_PER_IMAGE,
            started=started,
        )

    def _call_genai_sync(self, genai: object, prompt: str) -> bytes:
        try:
            model = genai.GenerativeModel(self._model)  # type: ignore[attr-defined]
            response = model.generate_content(prompt)
        except Exception as exc:
            raise ImageProviderError("gemini_3_pro", str(exc)) from exc
        image_bytes = _extract_image_bytes(response)
        if image_bytes is None:
            raise ImageProviderError(
                "gemini_3_pro", "response contained no inline image data"
            )
        return image_bytes


def _extract_image_bytes(response: object) -> bytes | None:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", []) if content is not None else []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline is not None else None
            if isinstance(data, bytes) and data:
                return data
    return None


__all__ = ["Gemini3ProProvider"]
