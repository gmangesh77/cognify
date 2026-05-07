"""Tests for the persona-aware ImageSpec data model (Phase 2 / VISUAL-005)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.visual import (
    ImagePlacement,
    ImageSpec,
)


class TestImagePlacement:
    def test_defaults(self) -> None:
        placement = ImagePlacement()
        assert placement.anchor == "top"
        assert placement.heading_text is None
        assert placement.paragraph_index is None
        assert placement.section_index == -1

    def test_anchors_accepted(self) -> None:
        for anchor in (
            "cover",
            "top",
            "before_heading",
            "between_paragraphs",
            "bottom_grid",
            "background",
            "column_split",
        ):
            placement = ImagePlacement(anchor=anchor)  # type: ignore[arg-type]
            assert placement.anchor == anchor

    def test_invalid_anchor_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ImagePlacement(anchor="middle_left")  # type: ignore[arg-type]

    def test_before_heading_carries_heading_text(self) -> None:
        placement = ImagePlacement(
            anchor="before_heading", heading_text="Why this matters", section_index=2
        )
        assert placement.heading_text == "Why this matters"

    def test_between_paragraphs_carries_paragraph_index(self) -> None:
        placement = ImagePlacement(
            anchor="between_paragraphs", paragraph_index=3, section_index=0
        )
        assert placement.paragraph_index == 3


class TestImageSpec:
    def _valid_kwargs(self) -> dict[str, object]:
        return {
            "id": "spec_123",
            "role_style": "hero",
            "visual_style": "lifestyle_photo",
            "prompt": "A relaxed founder working in a sunlit loft.",
            "alt_text": "Founder at desk",
            "aspect_ratio": "16:9",
        }

    def test_minimal_valid_spec(self) -> None:
        spec = ImageSpec(**self._valid_kwargs())  # type: ignore[arg-type]
        assert spec.id == "spec_123"
        assert spec.role_style == "hero"
        assert spec.visual_style == "lifestyle_photo"
        assert spec.aspect_ratio == "16:9"
        assert spec.placement.anchor == "top"  # default

    def test_default_placement_is_factory_isolated(self) -> None:
        a = ImageSpec(**self._valid_kwargs())  # type: ignore[arg-type]
        b = ImageSpec(**self._valid_kwargs())  # type: ignore[arg-type]
        assert a.placement is not b.placement, "Default placement must not be shared"

    def test_invalid_role_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["role_style"] = "ascii_art"
        with pytest.raises(ValidationError):
            ImageSpec(**kwargs)  # type: ignore[arg-type]

    def test_invalid_aspect_ratio_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["aspect_ratio"] = "21:9"
        with pytest.raises(ValidationError):
            ImageSpec(**kwargs)  # type: ignore[arg-type]

    def test_provider_optional_when_omitted(self) -> None:
        spec = ImageSpec(**self._valid_kwargs())  # type: ignore[arg-type]
        assert spec.provider is None

    def test_provider_accepts_valid_keys(self) -> None:
        for provider in ("gemini_flash", "gemini_3_pro", "imagen_4", "dalle_3"):
            kwargs = self._valid_kwargs()
            kwargs["provider"] = provider
            spec = ImageSpec(**kwargs)  # type: ignore[arg-type]
            assert spec.provider == provider

    def test_invalid_provider_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["provider"] = "midjourney_v8"
        with pytest.raises(ValidationError):
            ImageSpec(**kwargs)  # type: ignore[arg-type]

    def test_visual_style_optional(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["visual_style"] = None
        spec = ImageSpec(**kwargs)  # type: ignore[arg-type]
        assert spec.visual_style is None

    def test_alt_text_default_empty(self) -> None:
        kwargs = self._valid_kwargs()
        del kwargs["alt_text"]
        spec = ImageSpec(**kwargs)  # type: ignore[arg-type]
        assert spec.alt_text == ""

    def test_explicit_placement_carried(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["placement"] = ImagePlacement(
            anchor="between_paragraphs", paragraph_index=2, section_index=1
        )
        spec = ImageSpec(**kwargs)  # type: ignore[arg-type]
        assert spec.placement.anchor == "between_paragraphs"
        assert spec.placement.paragraph_index == 2
        assert spec.placement.section_index == 1

    def test_rationale_optional(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["rationale"] = "Hero anchors article identity."
        spec = ImageSpec(**kwargs)  # type: ignore[arg-type]
        assert spec.rationale == "Hero anchors article identity."

    def test_dump_round_trip(self) -> None:
        spec = ImageSpec(**self._valid_kwargs())  # type: ignore[arg-type]
        dumped = spec.model_dump(mode="json")
        rebuilt = ImageSpec.model_validate(dumped)
        assert rebuilt == spec
