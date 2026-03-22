"""AI illustration generation for article hero images.

Defines ImageGenerator protocol and OpenAI DALL-E implementation.
Best-effort: failures are logged and skipped, never crash the pipeline.
"""

from __future__ import annotations

import base64
from typing import Protocol

import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger()


class ImageGenerator(Protocol):
    """Provider-agnostic image generation protocol."""

    async def generate(
        self, prompt: str, size: tuple[int, int]
    ) -> bytes | None: ...


class OpenAIDalleGenerator:
    """OpenAI DALL-E 3 image generator."""

    def __init__(self, api_key: str, model: str = "dall-e-3", timeout: float = 30.0) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model

    async def generate(
        self, prompt: str, size: tuple[int, int]
    ) -> bytes | None:
        """Generate an image. Returns bytes on success, None on failure."""
        size_str = f"{size[0]}x{size[1]}"
        try:
            response = await self._client.images.generate(
                model=self._model,
                prompt=prompt,
                size=size_str,
                response_format="b64_json",
                n=1,
            )
            if not response.data:
                logger.warning("dalle_empty_response")
                return None
            b64_data = response.data[0].b64_json
            if not b64_data:
                logger.warning("dalle_no_b64_data")
                return None
            return base64.b64decode(b64_data)
        except Exception as exc:
            logger.warning("dalle_generation_failed", error=str(exc))
            return None
