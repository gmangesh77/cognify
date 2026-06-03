"""Tests for the LangGraph image render node (Phase 2 / VISUAL-005)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import structlog

from src.agents.content.image_render_node import make_image_render_node
from src.models.content import ImageAsset
from src.models.visual import ImagePlacement, ImageSpec
from src.services.visuals.object_storage import LocalDiskObjectStorage
from src.services.visuals.registry import ImageProviderRegistry
from tests.stubs.stub_image_provider import StubImageProvider


def _spec(spec_id: str = "spec_1", **overrides: object) -> ImageSpec:
    base: dict[str, object] = {
        "id": spec_id,
        "role_style": "hero",
        "visual_style": "lifestyle_photo",
        "prompt": "A founder reading at a kitchen table.",
        "aspect_ratio": "16:9",
        "placement": ImagePlacement(anchor="cover", section_index=-1),
    }
    base.update(overrides)
    return ImageSpec(**base)  # type: ignore[arg-type]


def _state(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "session_id": uuid4(),
        "image_specs": [],
        "visuals": [],
    }
    base.update(overrides)
    return base


def _build_registry() -> tuple[ImageProviderRegistry, StubImageProvider]:
    stub = StubImageProvider()
    reg = ImageProviderRegistry()
    reg.register(stub)
    return reg, stub


@pytest.mark.asyncio
class TestImageRenderNode:
    async def test_returns_existing_visuals_when_no_specs(self) -> None:
        reg, _ = _build_registry()
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            existing = [ImageAsset(url="/charts/foo.png", caption="bar")]
            node = make_image_render_node(
                registry=reg,
                storage=storage,
                default_provider="gemini_flash",
                concurrency=2,
            )
            result = await node(_state(visuals=existing))
            assert result == {"visuals": existing}

    async def test_renders_each_spec_and_writes_bytes(self) -> None:
        reg, stub = _build_registry()
        specs = [
            _spec(spec_id="cover"),
            _spec(spec_id="card", role_style="feature_card"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg,
                storage=storage,
                default_provider="gemini_flash",
                concurrency=2,
            )
            result = await node(_state(image_specs=specs))
            visuals = result["visuals"]
            assert isinstance(visuals, list)
            assert len(visuals) == 2
            for asset in visuals:
                assert isinstance(asset, ImageAsset)
                assert asset.metadata.get("spec_id") in {"cover", "card"}
                assert asset.metadata.get("provider") == "gemini_flash"
                assert asset.metadata.get("prompt_used")
                # File should exist on disk under the temp dir.
                assert Path(asset.url).exists()
            assert len(stub.calls) == 2

    async def test_metadata_extension_carries_all_required_fields(self) -> None:
        reg, _ = _build_registry()
        specs = [_spec(spec_id="hero1")]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg,
                storage=storage,
                default_provider="gemini_flash",
                concurrency=1,
            )
            result = await node(_state(image_specs=specs))
            visuals = result["visuals"]
            asset = visuals[0]
            for key in (
                "spec_id",
                "role_style",
                "visual_style",
                "aspect_ratio",
                "placement_anchor",
                "provider",
                "model",
                "prompt_used",
                "cost_usd",
                "generation_ms",
            ):
                assert key in asset.metadata, f"missing {key} in render metadata"

    async def test_existing_visuals_preserved_alongside_new(self) -> None:
        reg, _ = _build_registry()
        specs = [_spec(spec_id="hero1")]
        existing = [ImageAsset(url="/charts/foo.png", caption="chart")]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg,
                storage=storage,
                default_provider="gemini_flash",
                concurrency=1,
            )
            result = await node(_state(image_specs=specs, visuals=existing))
            visuals = result["visuals"]
            assert len(visuals) == 2
            urls = [v.url for v in visuals]
            assert "/charts/foo.png" in urls

    async def test_unknown_provider_falls_back_to_default(self) -> None:
        reg, stub = _build_registry()
        # Spec asks for `imagen_4` but only `gemini_flash` is registered.
        specs = [_spec(spec_id="hero1", provider="imagen_4")]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg,
                storage=storage,
                default_provider="gemini_flash",
                concurrency=1,
            )
            result = await node(_state(image_specs=specs))
            visuals = result["visuals"]
            assert len(visuals) == 1
            assert visuals[0].metadata.get("provider") == "gemini_flash"

    async def test_caption_uses_spec_caption_for_non_hero(self) -> None:
        reg, _ = _build_registry()
        specs = [
            _spec(
                spec_id="diag",
                role_style="concept",
                placement=ImagePlacement(anchor="top", section_index=1),
                caption="Pod DNS Query Flow",
                rationale="internal: gives readers a mental model of resolution",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg, storage=storage, default_provider="gemini_flash"
            )
            asset = (await node(_state(image_specs=specs)))["visuals"][0]
            assert asset.caption == "Pod DNS Query Flow"
            # The internal rationale must never leak into the caption.
            assert "readers" not in (asset.caption or "")

    async def test_hero_gets_no_caption(self) -> None:
        reg, _ = _build_registry()
        specs = [_spec(spec_id="cover", role_style="hero", caption="Some Title")]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg, storage=storage, default_provider="gemini_flash"
            )
            asset = (await node(_state(image_specs=specs)))["visuals"][0]
            assert asset.caption is None

    async def test_caption_never_falls_back_to_rationale(self) -> None:
        reg, _ = _build_registry()
        specs = [
            _spec(
                spec_id="diag",
                role_style="concept",
                placement=ImagePlacement(anchor="top", section_index=1),
                caption=None,
                rationale="Fallback synthesised when LLM did not return a plan.",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg, storage=storage, default_provider="gemini_flash"
            )
            asset = (await node(_state(image_specs=specs)))["visuals"][0]
            assert asset.caption is None

    async def test_mermaid_spec_renders_diagram_metadata(self) -> None:
        """A spec carrying mermaid_syntax skips the provider and emits a
        diagram ImageAsset (mermaid_syntax + diagram_type in metadata)."""
        reg, stub = _build_registry()
        specs = [
            _spec(
                spec_id="diag",
                role_style="concept",
                placement=ImagePlacement(anchor="top", section_index=1),
                caption="Sharding Flow",
                mermaid_syntax="flowchart TD; A-->B",
                diagram_type="flowchart",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg, storage=storage, default_provider="gemini_flash"
            )
            asset = (await node(_state(image_specs=specs)))["visuals"][0]
            assert asset.metadata.get("mermaid_syntax") == "flowchart TD; A-->B"
            assert asset.metadata.get("diagram_type") == "flowchart"
            assert asset.metadata.get("provider") == "mermaid"
            assert asset.metadata.get("section_index") == 1
            assert asset.caption == "Sharding Flow"
            # The diffusion provider must NOT be called for a mermaid spec.
            assert len(stub.calls) == 0

    async def test_mermaid_render_failure_logs_rendered_false(self) -> None:
        """When mmdc fails the asset still ships (client-side syntax
        fallback), but mermaid_asset_complete must report rendered=False —
        the URL fallback key must not be conflated with a real PNG."""
        reg, _ = _build_registry()
        specs = [
            _spec(
                spec_id="diag",
                role_style="concept",
                placement=ImagePlacement(anchor="top", section_index=1),
                mermaid_syntax="flowchart TD; A-->B",
                diagram_type="flowchart",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg, storage=storage, default_provider="gemini_flash"
            )
            with (
                patch(
                    "src.agents.content.diagram_generator.render_mermaid",
                    new=AsyncMock(return_value=False),
                ),
                structlog.testing.capture_logs() as logs,
            ):
                asset = (await node(_state(image_specs=specs)))["visuals"][0]

        completion = [e for e in logs if e["event"] == "mermaid_asset_complete"]
        assert len(completion) == 1
        assert completion[0]["rendered"] is False
        # The asset is still emitted with the fallback URL for client render.
        assert asset.url
        assert asset.metadata.get("mermaid_syntax") == "flowchart TD; A-->B"

    async def test_mermaid_render_success_logs_rendered_true(self) -> None:
        """When mmdc produces a PNG, mermaid_asset_complete reports
        rendered=True."""
        reg, _ = _build_registry()
        specs = [
            _spec(
                spec_id="diag",
                role_style="concept",
                placement=ImagePlacement(anchor="top", section_index=1),
                mermaid_syntax="flowchart TD; A-->B",
                diagram_type="flowchart",
            )
        ]

        async def _fake_render(syntax: str, output_path: Path) -> bool:
            Path(output_path).write_bytes(b"PNGDATA")
            return True

        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg, storage=storage, default_provider="gemini_flash"
            )
            with (
                patch(
                    "src.agents.content.diagram_generator.render_mermaid",
                    new=_fake_render,
                ),
                structlog.testing.capture_logs() as logs,
            ):
                await node(_state(image_specs=specs))

        completion = [e for e in logs if e["event"] == "mermaid_asset_complete"]
        assert len(completion) == 1
        assert completion[0]["rendered"] is True

    async def test_provider_failure_skips_spec(self) -> None:
        class ExplodingProvider:
            @property
            def name(self) -> str:
                return "gemini_flash"

            @property
            def model(self) -> str:
                return "boom"

            async def render(self, **kwargs: object) -> object:
                raise RuntimeError("provider down")

        reg = ImageProviderRegistry()
        reg.register(ExplodingProvider())  # type: ignore[arg-type]
        specs = [_spec(spec_id="hero1")]
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            node = make_image_render_node(
                registry=reg,
                storage=storage,
                default_provider="gemini_flash",
                concurrency=1,
            )
            result = await node(_state(image_specs=specs))
            assert result["visuals"] == []
