"""Twelve-entry visual-style catalogue for the image planner.

Single source of truth — exposed via `GET /api/v1/visuals/styles` so the
frontend boots, fetches, and caches. There is no mirrored TypeScript
catalogue (eliminates the drift class of bug by design — see ADR-005).

Every style is layered separately from the prompt subject. The composer
joins art direction, page-wide direction, section override, and refine
note into a single block that is appended to the subject prompt by the
prompt composer (Phase 2).
"""

from __future__ import annotations

_STYLE_ENTRIES: tuple[dict[str, str], ...] = (
    {
        "key": "lifestyle_photo",
        "label": "Lifestyle Photo",
        "category": "photo",
        "default_aspect": "16:9",
        "short_desc": "Editorial DSLR photography, natural light, candid composition",
        "prompt_fragment": (
            "Render as editorial-grade DSLR photography. Natural side light, "
            "soft shadows, candid composition with considered negative space. "
            "Warm slate neutrals as the dominant palette with a single warm "
            "coral accent. No identifiable faces. Magazine-cover framing."
        ),
    },
    {
        "key": "isometric_3d",
        "label": "Isometric 3D",
        "category": "illustration",
        "default_aspect": "16:9",
        "short_desc": "Clean isometric vector 3D, soft shadows, slate base",
        "prompt_fragment": (
            "Render as a clean isometric vector 3D illustration. Soft cast "
            "shadows, considered depth from layered geometry, no skeuomorphic "
            "textures. Warm slate base palette with a warm coral accent. "
            "No baked-in text or labels."
        ),
    },
    {
        "key": "editorial",
        "label": "Editorial",
        "category": "editorial",
        "default_aspect": "16:9",
        "short_desc": "Magazine-cover composition with rich negative space",
        "prompt_fragment": (
            "Render as a deliberate magazine-cover composition. Layered "
            "subject, considered negative space, rhythm that supports "
            "typographic overlay. Warm slate neutrals with a single warm "
            "coral accent. No text in the image."
        ),
    },
    {
        "key": "abstract",
        "label": "Abstract",
        "category": "illustration",
        "default_aspect": "1:1",
        "short_desc": "Abstract geometric shapes with slate gradients",
        "prompt_fragment": (
            "Render as an abstract geometric/organic composition. Slate "
            "gradient base with depth from overlapping translucent layers, "
            "occasional warm coral highlight. No literal subjects, no text."
        ),
    },
    {
        "key": "sketch",
        "label": "Sketch",
        "category": "illustration",
        "default_aspect": "4:3",
        "short_desc": "Hand-drawn ink sketch on off-white paper",
        "prompt_fragment": (
            "Render as a hand-drawn ink sketch. Expressive linework, hatching "
            "for shadow, off-white paper feel. Single accent in warm coral "
            "where it serves the composition. No baked-in text."
        ),
    },
    {
        "key": "blueprint",
        "label": "Blueprint",
        "category": "technical",
        "default_aspect": "16:9",
        "short_desc": "White technical line drawing on slate background",
        "prompt_fragment": (
            "Render as a technical blueprint: white line drawing on a slate "
            "background. Schematic, geometric, no decoration. No baked-in "
            "labels or callout text — leave space for typographic overlay."
        ),
    },
    {
        "key": "watercolor",
        "label": "Watercolor",
        "category": "illustration",
        "default_aspect": "4:3",
        "short_desc": "Translucent watercolor wash, slate and coral",
        "prompt_fragment": (
            "Render as a translucent watercolor wash. Slate and warm coral "
            "palette, soft organic edges, paper grain visible. No baked-in "
            "text or sharp digital lines."
        ),
    },
    {
        "key": "cinematic",
        "label": "Cinematic",
        "category": "photo",
        "default_aspect": "16:9",
        "short_desc": "Deep contrast cinematic still, dark slate + warm orange",
        "prompt_fragment": (
            "Render as a cinematic still: deep contrast, considered depth of "
            "field, slow-shutter motion blur acceptable. Dark slate with "
            "warm orange highlight. No identifiable faces. Magazine quality."
        ),
    },
    {
        "key": "neon_synthwave",
        "label": "Neon Synthwave",
        "category": "illustration",
        "default_aspect": "16:9",
        "short_desc": "Retro neon grid, slate + warm coral (no pure cyan)",
        "prompt_fragment": (
            "Render as a retro neon synthwave illustration. Perspective "
            "horizon grid, layered glow. Adjust palette: slate base with "
            "warm coral accent — avoid pure cyan and Miami pinks. No text."
        ),
    },
    {
        "key": "pulp",
        "label": "Pulp",
        "category": "illustration",
        "default_aspect": "4:5",
        "short_desc": "High-contrast pulp-magazine cover with halftone",
        "prompt_fragment": (
            "Render as a high-contrast pulp-magazine cover. Bold composition, "
            "halftone texture, dramatic foreground subject. Warm coral and "
            "slate. No baked-in text — leave space for an editorial title."
        ),
    },
    {
        "key": "paper_collage",
        "label": "Paper Collage",
        "category": "illustration",
        "default_aspect": "1:1",
        "short_desc": "Torn-paper collage, layered cutouts",
        "prompt_fragment": (
            "Render as a torn-paper collage. Layered cutouts with visible "
            "fibre edges, slate and warm coral palette, considered drop "
            "shadows. No baked-in text."
        ),
    },
    {
        "key": "technical_diagram",
        "label": "Technical Diagram",
        "category": "technical",
        "default_aspect": "4:3",
        "short_desc": "Minimal technical diagram with implied callouts",
        "prompt_fragment": (
            "Render as a minimal technical diagram. Geometric shapes with "
            "implied callouts (no actual text), neutral slate palette with a "
            "single warm coral accent. Leave room for typographic labels."
        ),
    },
)

VISUAL_STYLES: dict[str, dict[str, str]] = {
    entry["key"]: dict(entry) for entry in _STYLE_ENTRIES
}

# Map ImageRoleStyle literal values (see plan §4.1) to a default style key.
ROLE_STYLE_DEFAULTS: dict[str, str] = {
    "hero": "lifestyle_photo",
    "feature_card": "isometric_3d",
    "concept": "abstract",
    "process_step": "isometric_3d",
    "comparison_split": "editorial",
    "quote_card": "editorial",
    "stat_card": "editorial",
    "screenshot_mock": "blueprint",
    "editorial": "editorial",
    "background": "abstract",
}

_STYLE_BLOCK_MAX = 800
_STYLE_BLOCK_TRUNCATION_SUFFIX = "…"


def default_visual_style_for_role(role: str) -> str | None:
    """Default catalogue key for an `ImageRoleStyle`. None if unknown."""
    return ROLE_STYLE_DEFAULTS.get(role)


def style_prompt_fragment(key: str) -> str | None:
    """Return the verbose prompt fragment for `key`, or None if unknown."""
    entry = VISUAL_STYLES.get(key)
    return entry["prompt_fragment"] if entry else None


def get_style(key: str) -> dict[str, str] | None:
    """Return a copy of the full style entry, or None if `key` is unknown."""
    entry = VISUAL_STYLES.get(key)
    return dict(entry) if entry else None


def compose_style_override(
    visual_style: str | None,
    *,
    page_direction: str | None = None,
    section_override: str | None = None,
    refine_note: str | None = None,
) -> str | None:
    """Compose the final style block appended to a prompt subject.

    Joins the resolved style fragment with optional page-wide direction,
    per-section override, and refine note. Returns None when nothing is
    provided. Caps the result at 800 chars (truncated from the right with
    an ellipsis suffix).
    """
    parts: list[str] = []
    if visual_style:
        fragment = style_prompt_fragment(visual_style)
        if fragment:
            parts.append(fragment)
    if page_direction and page_direction.strip():
        parts.append(f"Page art direction: {page_direction.strip()}")
    if section_override and section_override.strip():
        parts.append(f"Section override: {section_override.strip()}")
    if refine_note and refine_note.strip():
        parts.append(f"Refine: {refine_note.strip()}")
    if not parts:
        return None
    composed = ". ".join(parts)
    if len(composed) > _STYLE_BLOCK_MAX:
        keep = _STYLE_BLOCK_MAX - len(_STYLE_BLOCK_TRUNCATION_SUFFIX)
        composed = composed[:keep] + _STYLE_BLOCK_TRUNCATION_SUFFIX
    return composed


def planner_catalogue_block() -> str:
    """Return a multi-line block listing every style for the planner prompt."""
    lines = ["Available visual styles:"]
    for entry in _STYLE_ENTRIES:
        lines.append(
            f"- {entry['key']} — {entry['label']} ({entry['category']}, "
            f"default {entry['default_aspect']}): {entry['short_desc']}"
        )
    return "\n".join(lines)
