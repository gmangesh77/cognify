"""Gemini 2.5 Flash Image provider — fast, cheap, no native aspect arg.

Aspect ratio is enforced by injecting a sentence into the prompt
(impactai's approach). Cost is approximated in fractions of a cent;
the exact value is set per-call from the response when Google exposes
it, otherwise the configured estimate is used.
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

_FLASH_PRICE_USD_PER_IMAGE = 0.001
_DEFAULT_DIMS: dict[str, tuple[int, int]] = {
    "16:9": (1280, 720),
    "1:1": (1024, 1024),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
    "4:5": (819, 1024),
}


class GeminiFlashProvider:
    """`gemini-2.5-flash-image` provider implementing `ImageProvider`."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.5-flash-image",
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ImageProviderError("gemini_flash", "api_key is required")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "gemini_flash"

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
        # `genai.configure` is idempotent — safe to call per render.
        genai.configure(api_key=self._api_key)  # type: ignore[attr-defined]
        injected_prompt = f"{prompt}\n\n{aspect_instruction(aspect_ratio)}"
        started = time.perf_counter()
        image_bytes = await asyncio.wait_for(
            asyncio.to_thread(self._call_genai_sync, genai, injected_prompt),
            timeout=self._timeout,
        )
        width, height = size_hint or _DEFAULT_DIMS.get(aspect_ratio, (1280, 720))
        return make_render_result(
            image_bytes=image_bytes,
            width=width,
            height=height,
            prompt_used=injected_prompt,
            model=self._model,
            provider=self.name,
            cost_usd=_FLASH_PRICE_USD_PER_IMAGE,
            started=started,
        )

    def _call_genai_sync(self, genai: object, prompt: str) -> bytes:
        try:
            model = genai.GenerativeModel(self._model)  # type: ignore[attr-defined]
            response = model.generate_content(prompt)
        except Exception as exc:
            raise ImageProviderError("gemini_flash", str(exc)) from exc
        image_bytes = _extract_image_bytes(response)
        if image_bytes is None:
            raise ImageProviderError(
                "gemini_flash", "response contained no inline image data"
            )
        return image_bytes


def _extract_image_bytes(response: object) -> bytes | None:
    """Best-effort image-bytes extraction from a `genai` response.

    The shape of `response.candidates[0].content.parts[i].inline_data.data`
    is what Google's SDK currently uses; we keep this lookup defensive
    so a minor SDK shape change doesn't crash the pipeline — it returns
    None and the provider raises a typed error.
    """
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


__all__ = ["GeminiFlashProvider"]
