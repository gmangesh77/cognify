"""Tests for the anchor-preservation validator."""

from __future__ import annotations

from src.models.visual import ImagePlacement, ImageSpec
from src.services.content.section_anchors import validate_anchors


def _spec(
    *,
    spec_id: str,
    section_index: int,
    anchor: str = "before_heading",
    heading_text: str | None = None,
) -> ImageSpec:
    return ImageSpec(
        id=spec_id,
        role_style="hero",
        prompt="placeholder",
        placement=ImagePlacement(
            anchor=anchor,  # type: ignore[arg-type]
            heading_text=heading_text,
            section_index=section_index,
        ),
    )


class TestValidateAnchorsSpecIds:
    def test_no_violations_when_all_spec_ids_preserved(self) -> None:
        original = '<img data-spec-id="hero-01"> body'
        new = 'updated body <img data-spec-id="hero-01">'
        violations = validate_anchors(
            original_markdown=original,
            new_markdown=new,
            image_specs=[],
            section_index=0,
        )
        assert violations == []

    def test_violation_when_spec_id_dropped(self) -> None:
        original = '<img data-spec-id="hero-01"> body'
        new = "edited body without the marker"
        violations = validate_anchors(
            original_markdown=original,
            new_markdown=new,
            image_specs=[],
            section_index=0,
        )
        assert len(violations) == 1
        assert violations[0].kind == "spec_id"
        assert violations[0].value == "hero-01"

    def test_no_violation_when_new_id_added(self) -> None:
        original = '<img data-spec-id="hero-01">'
        new = '<img data-spec-id="hero-01"> <img data-spec-id="extra-02">'
        violations = validate_anchors(
            original_markdown=original,
            new_markdown=new,
            image_specs=[],
            section_index=0,
        )
        assert violations == []


class TestValidateAnchorsHeadings:
    def test_no_violation_when_heading_present(self) -> None:
        spec = _spec(
            spec_id="img-01",
            section_index=2,
            heading_text="Why Small Steps Win",
        )
        violations = validate_anchors(
            original_markdown="## Why Small Steps Win\nintro",
            new_markdown="## Why Small Steps Win\nupdated intro",
            image_specs=[spec],
            section_index=2,
        )
        assert violations == []

    def test_violation_when_heading_dropped(self) -> None:
        spec = _spec(
            spec_id="img-01",
            section_index=2,
            heading_text="Why Small Steps Win",
        )
        violations = validate_anchors(
            original_markdown="## Why Small Steps Win\nintro",
            new_markdown="## Renamed Heading\nupdated intro",
            image_specs=[spec],
            section_index=2,
        )
        assert len(violations) == 1
        assert violations[0].kind == "heading_text"
        assert violations[0].spec_id == "img-01"

    def test_ignores_specs_for_other_sections(self) -> None:
        spec = _spec(
            spec_id="img-01",
            section_index=99,
            heading_text="Distant Heading",
        )
        violations = validate_anchors(
            original_markdown="## Section 1\n",
            new_markdown="## Section 1 — Renamed\n",
            image_specs=[spec],
            section_index=2,
        )
        assert violations == []

    def test_ignores_non_before_heading_anchors(self) -> None:
        spec = _spec(
            spec_id="img-01",
            section_index=2,
            anchor="top",
            heading_text="Should Not Block",
        )
        violations = validate_anchors(
            original_markdown="## Should Not Block\n",
            new_markdown="## Renamed\n",
            image_specs=[spec],
            section_index=2,
        )
        assert violations == []
