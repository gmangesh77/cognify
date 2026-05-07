"""Anchor-preservation validator for VISUAL-011 prose edits.

Edits to a section's prose must not silently drop the anchors that
Visual Studio uses to attach images:

- `data-spec-id="X"` markers carried inline in the markdown after image
  injection.
- `ImagePlacement.heading_text` values bound to `before_heading` placements
  for image specs attached to this section. Renaming the heading would
  detach the image at publish time.

The validator stays regex-cheap by design (per handoff brief gotcha 4):
no markdown AST parser unless these heuristics start misfiring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.models.visual import ImageSpec

AnchorKind = Literal["spec_id", "heading_text"]

_SPEC_ID_RE = re.compile(r'data-spec-id="([^"]+)"')


@dataclass(frozen=True)
class AnchorViolation:
    """One missing-anchor finding."""

    kind: AnchorKind
    value: str
    spec_id: str | None
    message: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "kind": self.kind,
            "value": self.value,
            "spec_id": self.spec_id,
            "message": self.message,
        }


def validate_anchors(
    *,
    original_markdown: str,
    new_markdown: str,
    image_specs: list[ImageSpec],
    section_index: int,
) -> list[AnchorViolation]:
    """Return any anchors lost in the transition `original_markdown → new_markdown`.

    Empty list means the edit is safe.
    """
    violations: list[AnchorViolation] = []
    violations.extend(_check_spec_ids(original_markdown, new_markdown))
    violations.extend(_check_headings(new_markdown, image_specs, section_index))
    return violations


def _check_spec_ids(original: str, new: str) -> list[AnchorViolation]:
    original_ids = set(_SPEC_ID_RE.findall(original))
    new_ids = set(_SPEC_ID_RE.findall(new))
    missing = sorted(original_ids - new_ids)
    return [
        AnchorViolation(
            kind="spec_id",
            value=spec_id,
            spec_id=spec_id,
            message=(
                f"Edit dropped image anchor data-spec-id='{spec_id}'. "
                "Restore the marker or remove the image spec from the "
                "Visual Studio panel before saving."
            ),
        )
        for spec_id in missing
    ]


def _check_headings(
    new_markdown: str,
    image_specs: list[ImageSpec],
    section_index: int,
) -> list[AnchorViolation]:
    violations: list[AnchorViolation] = []
    for spec in image_specs:
        placement = spec.placement
        if placement.anchor != "before_heading":
            continue
        if placement.section_index != section_index:
            continue
        heading = placement.heading_text
        if not heading:
            continue
        if heading not in new_markdown:
            violations.append(
                AnchorViolation(
                    kind="heading_text",
                    value=heading,
                    spec_id=spec.id,
                    message=(
                        f"Edit dropped or renamed heading "
                        f"'{heading}' that image spec '{spec.id}' is "
                        "anchored to. Keep the heading text intact or "
                        "re-anchor the image first."
                    ),
                )
            )
    return violations


__all__ = ["AnchorKind", "AnchorViolation", "validate_anchors"]
