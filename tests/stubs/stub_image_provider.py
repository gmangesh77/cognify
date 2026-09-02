"""In-memory image provider for tests.

Returns a tiny valid PNG so the render pipeline runs end-to-end without
touching Google AI / OpenAI. The PNG is a 1x1 transparent pixel, which
is enough to satisfy MIME sniffs and downstream object-storage writes.

Usage:

    registry = ImageProviderRegistry()
    registry.register(StubImageProvider())
    # ... drive the render node
"""

from __future__ import annotations

from src.services.visuals.providers.base import ImageProvider, ImageRenderResult


def _make_png_1x1() -> bytes:
    """A real, PIL-decodable 1x1 transparent PNG (hero canonicalization
    re-encodes render bytes, so a merely structurally-valid PNG breaks)."""
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


_PNG_1X1: bytes = _make_png_1x1()


class StubImageProvider:
    """`ImageProvider`-compatible stub that records every render call."""

    def __init__(self, name: str = "gemini_flash", model: str = "stub-flash") -> None:
        self._name = name
        self._model = model
        self.calls: list[dict[str, object]] = []

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
        self.calls.append(
            {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "size_hint": size_hint,
            }
        )
        return ImageRenderResult(
            image_bytes=_PNG_1X1,
            mime_type="image/png",
            width=1,
            height=1,
            prompt_used=prompt,
            model=self._model,
            provider=self._name,
            cost_usd=0.0,
            latency_ms=1,
        )


# Keep mypy happy on Protocol assignment.
_proto_check: ImageProvider = StubImageProvider()
