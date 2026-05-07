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
from typing import Any
from uuid import UUID

import structlog

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
) -> Any:  # noqa: ANN401
    """Factory returning the LangGraph render node fn."""
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _render_one(
        spec: ImageSpec,
        page_direction: str | None,
        session_id: UUID | None,
    ) -> ImageAsset | None:
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

        return _build_asset(
            spec=spec,
            result=result,
            stored=stored,
            generation_ms=elapsed_ms,
        )

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
        "provider": result.provider,
        "model": result.model,
        "prompt_used": result.prompt_used,
        "cost_usd": result.cost_usd,
        "generation_ms": generation_ms,
        "width": result.width,
        "height": result.height,
    }
    return ImageAsset(
        url=url,
        caption=spec.rationale,
        alt_text=spec.alt_text or None,
        metadata=metadata,
    )
