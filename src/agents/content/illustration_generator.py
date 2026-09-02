"""AI illustration generation for article hero images.

Defines ImageGenerator protocol and OpenAI DALL-E implementation.
Best-effort: failures are logged and skipped, never crash the pipeline.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Protocol

import structlog
from openai import AsyncOpenAI

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from src.models.research import TopicInput

logger = structlog.get_logger()

# Canonical hero image dimensions enforced on every generated hero/cover.
# Providers return their own shapes (DALL-E 3: 1792x1024; gpt-image-1:
# 1536x1024), which `normalize_hero_image` center-crops and resizes to
# exact 16:9 at 1600x900. Having a single fixed size guarantees consistent
# appearance across Ghost list cards, article detail pages, and any other
# consumer of the feature_image.
HERO_CANONICAL_WIDTH = 1600
HERO_CANONICAL_HEIGHT = 900
HERO_CANONICAL_SIZE = (HERO_CANONICAL_WIDTH, HERO_CANONICAL_HEIGHT)
# Source size requested from DALL-E 3 before cropping. DALL-E 3 only
# accepts 1024x1024, 1024x1792, or 1792x1024 — 1792x1024 is the widest
# landscape option and the closest to our 16:9 target.
DALLE_SOURCE_SIZE = (1792, 1024)


def normalize_hero_image(image_bytes: bytes) -> bytes:
    """Center-crop and resize to canonical 16:9 hero dimensions.

    Guarantees every hero.png is exactly HERO_CANONICAL_SIZE regardless of
    what the generator returned, so Ghost themes render consistently across
    list cards and article detail pages. CPU-bound — call via
    `asyncio.to_thread` from async code.
    """
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as img:
        src_w, src_h = img.size
        target_ratio = HERO_CANONICAL_WIDTH / HERO_CANONICAL_HEIGHT
        src_ratio = src_w / src_h
        # Center-crop to the target aspect ratio
        if src_ratio > target_ratio:
            # Source is wider than target — crop sides
            new_w = max(1, int(src_h * target_ratio))
            left = (src_w - new_w) // 2
            box = (left, 0, left + new_w, src_h)
        else:
            # Source is taller than target — crop top/bottom
            new_h = max(1, int(src_w / target_ratio))
            top = (src_h - new_h) // 2
            box = (0, top, src_w, top + new_h)
        cropped = img.crop(box)
        resized = cropped.resize(HERO_CANONICAL_SIZE, Image.Resampling.LANCZOS)
        out = BytesIO()
        resized.save(out, format="PNG")
        return out.getvalue()


class ImageGenerator(Protocol):
    """Provider-agnostic image generation protocol."""

    async def generate(self, prompt: str, size: tuple[int, int]) -> bytes | None: ...


class OpenAIDalleGenerator:
    """OpenAI DALL-E 3 image generator."""

    def __init__(
        self, api_key: str, model: str = "dall-e-3", timeout: float = 30.0
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model

    async def generate(self, prompt: str, size: tuple[int, int]) -> bytes | None:
        """Generate an image. Returns bytes on success, None on failure.

        The OpenAI Images API no longer accepts `response_format` on the
        unified surface (gpt-image-1 returns base64 by default; the param
        triggers 400 "Unknown parameter" even for legacy dall-e-3 accounts).
        Handle both b64_json (gpt-image-1) and url (dall-e-3) response shapes.
        """
        size_str = f"{size[0]}x{size[1]}"
        try:
            response = await self._client.images.generate(
                model=self._model,
                prompt=prompt,
                size=size_str,
                n=1,
            )
            if not response.data:
                logger.warning("dalle_empty_response")
                return None
            datum = response.data[0]
            b64_data = getattr(datum, "b64_json", None)
            if b64_data:
                return base64.b64decode(b64_data)
            url = getattr(datum, "url", None)
            if url:
                import httpx

                async with httpx.AsyncClient(timeout=30) as http:
                    resp = await http.get(url)
                    resp.raise_for_status()
                    return resp.content
            logger.warning("dalle_no_image_data")
            return None
        except Exception as exc:
            logger.warning("dalle_generation_failed", error=str(exc))
            return None


_PROMPT_TEMPLATE = (
    "You are an expert art director at a premium tech publication like Wired or "
    "The Verge. Write a detailed DALL-E prompt for a stunning article hero image.\n\n"
    "Article title: {title}\n"
    "Domain: {domain}\n"
    "Summary: {summary}\n\n"
    "Requirements:\n"
    "- Modern, visually striking digital illustration — NOT a stock photo\n"
    "- Abstract or conceptual representation of the topic\n"
    "- Rich color palette with depth, gradients, and lighting effects\n"
    "- Clean composition suitable for a 16:9 hero banner\n"
    "- Style: blend of 3D render and flat design, cinematic lighting\n"
    "- NO text, words, letters, or numbers in the image\n"
    "- NO photorealistic human faces\n"
    "- NO charts, graphs, diagrams, or data visualizations\n"
    "- Think: abstract tech art, futuristic, editorial quality\n\n"
    "Write ONLY the image prompt (100-200 words). No explanation."
)


async def generate_illustration_prompt(
    topic: TopicInput,
    summary: str,
    llm: BaseChatModel,
) -> str | None:
    """Generate a DALL-E prompt from article metadata. Returns None on failure."""
    prompt = _PROMPT_TEMPLATE.format(
        title=topic.title,
        domain=topic.domain,
        summary=summary or topic.description,
    )
    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip() if hasattr(response, "content") else ""
        if not content:
            logger.warning("illustration_prompt_empty")
            return None
        return content
    except Exception as exc:
        logger.warning("illustration_prompt_failed", error=str(exc))
        return None
