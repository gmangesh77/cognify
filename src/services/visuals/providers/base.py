"""Provider-agnostic image generation contract.

Every concrete provider (`gemini_flash`, `gemini_3_pro`, `imagen_4`, `dalle_3`)
implements `ImageProvider` and returns an `ImageRenderResult`. The result is
storage-agnostic — it carries raw bytes and metadata; the `object_storage`
service decides whether to upload to MinIO/S3 or fall back to base64.

The protocol intentionally lives in its own module so concrete providers can
import it without pulling in their siblings (which would create import cycles
during registry boot).
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class ImageRenderResult(BaseModel):
    """Output of a single image render call.

    Storage-agnostic: carries raw bytes plus the metadata downstream nodes need
    to (a) attribute cost, (b) audit prompt+model, and (c) link the rendered
    asset back to the spec that produced it. The `cost_usd` and `latency_ms`
    fields are surfaced by the `/visuals/cost` endpoint and the UsageBadge.
    """

    image_bytes: bytes
    mime_type: str = Field(default="image/png")
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    prompt_used: str
    model: str
    provider: str
    cost_usd: float | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)

    model_config = {"arbitrary_types_allowed": True}


class ImageProviderError(Exception):
    """Base error for all image provider failures.

    Subclasses raised by concrete providers MUST set `provider` so the registry
    and downstream renderers can surface a meaningful error.
    """

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ImageProviderQuotaError(ImageProviderError):
    """Provider rejected the request because the account/key is over quota."""


class ImageProviderTimeoutError(ImageProviderError):
    """Provider did not respond within the configured timeout."""


class ImageProviderInvalidRequestError(ImageProviderError):
    """Provider rejected the request as malformed (4xx other than quota)."""


class ImageProvider(Protocol):
    """Contract every concrete image-generation provider must satisfy.

    Implementations are registered in `src/services/visuals/__init__.py` via
    `ImageProviderRegistry.register()`. The registry mirrors the TrendSource
    pattern (ARCH-002) so adding a provider is one new file plus one register
    call — no edits to the planner, the agent nodes, or the API.
    """

    @property
    def name(self) -> str:
        """Lowercase snake_case provider key (e.g. 'gemini_flash')."""
        ...

    @property
    def model(self) -> str:
        """Resolved model identifier the provider will call."""
        ...

    async def render(
        self,
        *,
        prompt: str,
        aspect_ratio: str,
        size_hint: tuple[int, int] | None = None,
    ) -> ImageRenderResult:
        """Render an image from `prompt`. Raises `ImageProviderError` on failure.

        - `prompt` is the fully-composed text prompt (subject + style + page
          art direction + aspect-ratio sentence + banned-cliché block).
        - `aspect_ratio` is one of `16:9`, `1:1`, `4:3`, `3:4`, `4:5`. Providers
          that don't accept aspect natively (Gemini Flash) embed it in the
          prompt; providers that do (Imagen 4, DALL-E 3) honour the param.
        - `size_hint` is optional and advisory — providers may snap to their
          nearest supported size and return the actual `width`/`height` in the
          result.
        """
        ...
