"""LangGraph node — renders planned ImageSpecs into ImageAssets.

Sits immediately after `image_planner_node` (Phase 2 / VISUAL-005). Fans
out concurrent provider calls bounded by an asyncio.Semaphore, persists
the bytes via the configured `ObjectStorage`, and emits one
`ImageAsset` per successfully rendered spec. Failures are logged and
swallowed — a single broken render never crashes the pipeline.

Boundary invariants (ADR-005):
- No imports from `src/services/publishing/`.
- Each emitted ImageAsset.metadata carries `spec_id` linking it back to
  the originating ImageSpec — content-layer only.
- prompt composition lives in `src/services/visuals/prompt_composer.py`;
  this node merely orchestrates and writes.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog

from src.agents.content.diagram_generator import MERMAID_RENDER_TIMEOUT_SECONDS
from src.models.content import ImageAsset
from src.models.visual import ImageSpec
from src.services.visuals.object_storage import (
    ObjectStorage,
    StoredObject,
    make_object_key,
)
from src.services.visuals.prompt_composer import build_prompt
from src.services.visuals.providers.base import (
    ImageProvider,
    ImageProviderError,
    ImageRenderResult,
)
from src.services.visuals.registry import ImageProviderRegistry

logger = structlog.get_logger()


def make_image_render_node(
    *,
    registry: ImageProviderRegistry,
    storage: ObjectStorage,
    default_provider: str = "gemini_flash",
    concurrency: int = 3,
    mermaid_timeout: float = MERMAID_RENDER_TIMEOUT_SECONDS,
) -> Any:  # noqa: ANN401
    """Factory returning the LangGraph render node fn."""
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _render_one(
        spec: ImageSpec,
        page_direction: str | None,
        session_id: UUID | None,
    ) -> ImageAsset | None:
        # VISUAL-012 — Mermaid path: when the planner attached mermaid_syntax
        # (structural role + mermaid mode), render it deterministically via
        # mermaid-cli instead of calling a diffusion provider. Runs under the
        # same semaphore — each render launches a Chromium, and unbounded
        # concurrent cold launches are what pushed renders past the timeout.
        if spec.mermaid_syntax:
            async with sem:
                return await _render_mermaid_asset(
                    spec, storage, session_id, timeout_seconds=mermaid_timeout
                )

        provider = _resolve_provider(spec, registry, default_provider)
        if provider is None:
            logger.warning(
                "image_render_no_provider",
                spec_id=spec.id,
                requested=spec.provider,
            )
            return None

        prompt = build_prompt(spec=spec, page_direction=page_direction)
        async with sem:
            started = time.perf_counter()
            try:
                result: ImageRenderResult = await provider.render(
                    prompt=prompt,
                    aspect_ratio=spec.aspect_ratio,
                )
            except (ImageProviderError, RuntimeError, ValueError) as exc:
                logger.warning(
                    "image_render_provider_error",
                    spec_id=spec.id,
                    provider=provider.name,
                    error=str(exc),
                )
                return None
            except Exception as exc:  # noqa: BLE001 — never crash pipeline
                logger.warning(
                    "image_render_unexpected_error",
                    spec_id=spec.id,
                    provider=provider.name,
                    error=str(exc),
                )
                return None
            elapsed_ms = int((time.perf_counter() - started) * 1000)

        canonicalized = False
        if spec.role_style == "hero" or spec.placement.anchor == "cover":
            normalized = await canonicalize_hero_render(result, spec_id=spec.id)
            canonicalized = normalized is not result
            result = normalized

        try:
            stored = await _persist(
                storage=storage,
                spec=spec,
                result=result,
                session_id=session_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "image_render_persist_failed",
                spec_id=spec.id,
                error=str(exc),
            )
            return None

        asset = _build_asset(
            spec=spec,
            result=result,
            stored=stored,
            generation_ms=elapsed_ms,
        )
        if canonicalized:
            # The stored pixels are 1600x900 regardless of what the spec
            # requested — keep the persisted metadata truthful.
            asset.metadata["aspect_ratio"] = "16:9"
        return asset

    async def image_render_node(state: dict[str, Any]) -> dict[str, Any]:
        existing = list(state.get("visuals") or [])
        specs: list[ImageSpec] = list(state.get("image_specs") or [])
        if not specs:
            return {"visuals": existing}

        page_direction = state.get("page_art_direction")
        session_id = state.get("session_id")

        rendered = await asyncio.gather(
            *[_render_one(s, page_direction, session_id) for s in specs],
            return_exceptions=False,
        )
        new_assets = [a for a in rendered if isinstance(a, ImageAsset)]
        logger.info(
            "image_render_complete",
            requested=len(specs),
            succeeded=len(new_assets),
        )
        return {"visuals": existing + new_assets}

    return image_render_node


def _resolve_provider(
    spec: ImageSpec,
    registry: ImageProviderRegistry,
    default_provider: str,
) -> ImageProvider | None:
    """Return the provider for `spec`, falling back to default if not registered."""
    if spec.provider and registry.has(spec.provider):
        return registry.get(spec.provider)
    if registry.has(default_provider):
        return registry.get(default_provider)
    return None


async def canonicalize_hero_render(
    result: ImageRenderResult, *, spec_id: str
) -> ImageRenderResult:
    """Center-crop + resize hero/cover renders to the 1600x900 canonical.

    Providers return their native shapes (gpt-image-1: 1536x1024, 3:2) which
    render oversized in Ghost's 16:9 feature-image slot. Best-effort: on any
    failure the original render is kept — never crash the pipeline.
    """
    from src.agents.content.illustration_generator import (
        HERO_CANONICAL_HEIGHT,
        HERO_CANONICAL_WIDTH,
        normalize_hero_image,
    )

    try:
        normalized = await asyncio.to_thread(normalize_hero_image, result.image_bytes)
    except Exception as exc:  # noqa: BLE001 — keep the un-normalized render
        logger.warning("hero_normalize_failed", spec_id=spec_id, error=str(exc))
        return result
    return result.model_copy(
        update={
            "image_bytes": normalized,
            "mime_type": "image/png",
            "width": HERO_CANONICAL_WIDTH,
            "height": HERO_CANONICAL_HEIGHT,
        }
    )


async def _persist(
    *,
    storage: ObjectStorage,
    spec: ImageSpec,
    result: ImageRenderResult,
    session_id: UUID | None,
) -> StoredObject:
    """Write the rendered bytes via the configured object storage."""
    ext = "png" if result.mime_type == "image/png" else "jpg"
    base_key = make_object_key(spec_id=spec.id, ext=ext)
    key = f"sessions/{session_id}/{base_key}" if session_id else base_key
    return await storage.put(
        key=key,
        content=result.image_bytes,
        content_type=result.mime_type,
    )


async def _render_mermaid_asset(
    spec: ImageSpec,
    storage: ObjectStorage,
    session_id: UUID | None,
    *,
    timeout_seconds: float = MERMAID_RENDER_TIMEOUT_SECONDS,
) -> ImageAsset | None:
    """Render a planner Mermaid spec to a PNG and emit a diagram ImageAsset.

    If the mermaid-cli render fails (e.g. mmdc not installed) the asset is
    still emitted — the dashboard `MermaidDiagram` component renders
    client-side from `mermaid_syntax` and ignores the URL. The URL falls
    back to the object key so the (publishing) consumer has a stable path
    once a PNG is produced. The syntax travels in metadata either way.
    """
    import tempfile

    from src.agents.content.diagram_generator import render_mermaid

    syntax = spec.mermaid_syntax or ""
    base_key = make_object_key(spec_id=spec.id, ext="png")
    key = f"sessions/{session_id}/{base_key}" if session_id else base_key
    # Non-empty fallback so ImageAsset.url validates even when mmdc is
    # unavailable; the dashboard renders from mermaid_syntax regardless.
    url = key
    # Tracks whether a real PNG was produced and stored — distinct from the
    # URL (which always falls back to `key`). Drives the completion log so it
    # reports actual render success, not mere URL presence.
    png_rendered = False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "diagram.png"
            if await render_mermaid(syntax, png, timeout_seconds) and png.exists():
                stored = await storage.put(
                    key=key,
                    content=png.read_bytes(),
                    content_type="image/png",
                )
                url = stored.url or stored.local_path or stored.key
                png_rendered = True
    except Exception as exc:  # noqa: BLE001 — never crash the pipeline
        logger.warning("mermaid_asset_render_failed", spec_id=spec.id, error=str(exc))

    caption = None if spec.role_style in ("hero", "background") else spec.caption
    metadata: dict[str, str | int | float | None] = {
        "spec_id": spec.id,
        "role_style": spec.role_style,
        "section_index": spec.placement.section_index,
        "placement_anchor": spec.placement.anchor,
        "paragraph_index": spec.placement.paragraph_index,
        "heading_text": spec.placement.heading_text,
        "diagram_type": spec.diagram_type or "flowchart",
        "mermaid_syntax": syntax,
        "provider": "mermaid",
        # 1 when a real PNG was stored, 0 when the URL is only the fallback
        # key — the publish-time injector keys its skip decision off this
        # (int, not bool: ImageAsset.metadata values are str|int|float|None).
        "png_rendered": 1 if png_rendered else 0,
    }
    logger.info(
        "mermaid_asset_complete",
        spec_id=spec.id,
        rendered=png_rendered,
        fallback=not png_rendered,
    )
    return ImageAsset(
        url=url,
        caption=caption,
        alt_text=spec.alt_text or None,
        metadata=metadata,
    )


def _build_asset(
    *,
    spec: ImageSpec,
    result: ImageRenderResult,
    stored: StoredObject,
    generation_ms: int,
) -> ImageAsset:
    """Compose an ImageAsset with the metadata extension from §4.2 of the plan."""
    url = stored.url or stored.local_path or stored.key
    metadata: dict[str, str | int | float | None] = {
        "spec_id": spec.id,
        "role_style": spec.role_style,
        "visual_style": spec.visual_style or "",
        "aspect_ratio": spec.aspect_ratio,
        "placement_anchor": spec.placement.anchor,
        "section_index": spec.placement.section_index,
        "paragraph_index": spec.placement.paragraph_index,
        "heading_text": spec.placement.heading_text,
        "provider": result.provider,
        "model": result.model,
        "prompt_used": result.prompt_used,
        "cost_usd": result.cost_usd,
        "generation_ms": generation_ms,
        "width": result.width,
        "height": result.height,
    }
    # Reader-facing caption is the planner's short title (spec.caption).
    # Hero / background visuals are decorative and get no caption. We never
    # use spec.rationale here — that is internal planning meta-commentary.
    caption = None if spec.role_style in ("hero", "background") else spec.caption
    return ImageAsset(
        url=url,
        caption=caption,
        alt_text=spec.alt_text or None,
        metadata=metadata,
    )
