"""Tests for the visual style catalogue.

Covers: catalogue completeness and shape, role defaults, prompt-fragment
lookup, copy semantics on `get_style`, the four branches of
`compose_style_override` (including 800-char truncation), and the
planner catalogue block format.
"""

from __future__ import annotations

import pytest

from src.services.visuals.visual_styles import (
    ROLE_STYLE_DEFAULTS,
    VISUAL_STYLES,
    compose_style_override,
    default_visual_style_for_role,
    get_style,
    planner_catalogue_block,
    style_prompt_fragment,
)

EXPECTED_KEYS = {
    "lifestyle_photo",
    "isometric_3d",
    "editorial",
    "abstract",
    "sketch",
    "blueprint",
    "watercolor",
    "cinematic",
    "neon_synthwave",
    "pulp",
    "paper_collage",
    "technical_diagram",
}

ALLOWED_ASPECTS = {"16:9", "1:1", "4:3", "3:4", "4:5"}
ALLOWED_CATEGORIES = {"photo", "illustration", "editorial", "technical"}
REQUIRED_FIELDS = {
    "key",
    "label",
    "category",
    "default_aspect",
    "short_desc",
    "prompt_fragment",
}


def test_catalogue_has_exactly_twelve_styles() -> None:
    assert set(VISUAL_STYLES.keys()) == EXPECTED_KEYS
    assert len(VISUAL_STYLES) == 12


@pytest.mark.parametrize("key", sorted(EXPECTED_KEYS))
def test_each_entry_has_required_fields_and_valid_values(key: str) -> None:
    entry = VISUAL_STYLES[key]
    assert REQUIRED_FIELDS.issubset(entry.keys())
    assert entry["key"] == key
    assert entry["category"] in ALLOWED_CATEGORIES
    assert entry["default_aspect"] in ALLOWED_ASPECTS
    assert entry["short_desc"]
    assert len(entry["prompt_fragment"]) >= 40  # non-trivial guidance


def test_role_style_defaults_cover_all_canonical_roles() -> None:
    expected_roles = {
        "hero",
        "feature_card",
        "concept",
        "process_step",
        "comparison_split",
        "quote_card",
        "stat_card",
        "screenshot_mock",
        "editorial",
        "background",
    }
    assert set(ROLE_STYLE_DEFAULTS.keys()) == expected_roles
    for role, style_key in ROLE_STYLE_DEFAULTS.items():
        assert style_key in VISUAL_STYLES, (
            f"role {role} maps to unknown style {style_key}"
        )


def test_default_visual_style_for_role_lookups() -> None:
    assert default_visual_style_for_role("hero") == "lifestyle_photo"
    assert default_visual_style_for_role("feature_card") == "isometric_3d"
    assert default_visual_style_for_role("screenshot_mock") == "blueprint"


def test_default_visual_style_for_role_unknown_returns_none() -> None:
    assert default_visual_style_for_role("not_a_role") is None
    assert default_visual_style_for_role("") is None


def test_style_prompt_fragment_known_returns_string() -> None:
    fragment = style_prompt_fragment("lifestyle_photo")
    assert fragment is not None
    assert "DSLR" in fragment or "photography" in fragment


def test_style_prompt_fragment_unknown_returns_none() -> None:
    assert style_prompt_fragment("does_not_exist") is None


def test_get_style_returns_copy_not_reference() -> None:
    entry = get_style("editorial")
    assert entry is not None
    entry["label"] = "Mutated"
    assert VISUAL_STYLES["editorial"]["label"] != "Mutated"


def test_get_style_unknown_returns_none() -> None:
    assert get_style("nope") is None


def test_compose_style_override_all_none_returns_none() -> None:
    assert compose_style_override(None) is None
    assert compose_style_override("") is None  # falsy treated as none


def test_compose_style_override_only_style() -> None:
    composed = compose_style_override("lifestyle_photo")
    assert composed is not None
    assert "DSLR" in composed or "photography" in composed


def test_compose_style_override_joins_all_inputs() -> None:
    composed = compose_style_override(
        "lifestyle_photo",
        page_direction="soft natural light, slate palette",
        section_override="hero shot for the open of the article",
        refine_note="more whitespace",
    )
    assert composed is not None
    assert "Page art direction:" in composed
    assert "Section override:" in composed
    assert "Refine:" in composed
    assert "soft natural light" in composed


def test_compose_style_override_skips_whitespace_only() -> None:
    composed = compose_style_override(
        "abstract", page_direction="   ", section_override="  ", refine_note=""
    )
    assert composed is not None
    assert "Page art direction:" not in composed
    assert "Section override:" not in composed
    assert "Refine:" not in composed


def test_compose_style_override_truncates_to_800_chars() -> None:
    huge_direction = "x " * 1000  # ~2000 chars
    composed = compose_style_override("lifestyle_photo", page_direction=huge_direction)
    assert composed is not None
    assert len(composed) == 800
    assert composed.endswith("…")


def test_planner_catalogue_block_lists_every_key() -> None:
    block = planner_catalogue_block()
    assert block.startswith("Available visual styles:")
    for key in EXPECTED_KEYS:
        assert key in block, f"catalogue block missing {key}"


def test_planner_catalogue_block_format_uses_label_and_aspect() -> None:
    block = planner_catalogue_block()
    # format: `- key — Label (category, default 16:9): short_desc`
    assert "Lifestyle Photo (photo, default 16:9)" in block
    assert "Blueprint (technical, default 16:9)" in block
