"""Per-role default prompt seeds (Phase 2 / VISUAL-005).

Python port of impactai's `defaultSectionVisualPrompts.ts`. Each entry
describes a *subject* — what to render — at a useful default abstraction
for a given `ImageRoleStyle`. The visual style fragment (medium, palette,
lighting) is layered in separately by `prompt_composer.build_prompt`, so
seeds intentionally avoid medium-specific verbiage.

Used by `image_planner._fallback_specs` when the LLM returns nothing
parseable, and as a starting suggestion for the Studio "Edit drawer"
prompt field on the frontend (Phase 5).
"""

from __future__ import annotations

from src.models.visual import ImageRoleStyle

DEFAULT_SECTION_VISUAL_PROMPTS: dict[str, str] = {
    "hero": (
        "An establishing scene that sets the mood for the article — a "
        "person quietly engaged with the topic, surrounded by physical "
        "objects that hint at the subject without spelling it out."
    ),
    "feature_card": (
        "A single object or small still-life that personifies the feature "
        "being described, placed on a clean surface with breathing room "
        "around it."
    ),
    "concept": (
        "An abstract metaphor for the underlying idea — interlocking "
        "shapes, flowing forms, or layered surfaces that imply structure "
        "without literal depiction."
    ),
    "process_step": (
        "A small ordered arrangement of physical objects suggesting "
        "movement from one state to the next, with a clear directional "
        "rhythm in the composition."
    ),
    "comparison_split": (
        "Two contrasting subjects rendered in the same frame on either "
        "side of an implicit divider, balanced in weight but distinct in "
        "tone or palette."
    ),
    "quote_card": (
        "A quiet portrait-mood scene with a single contemplative subject "
        "and considered negative space where the quote will sit, "
        "atmosphere over information."
    ),
    "stat_card": (
        "A visual metaphor for scale or magnitude — stacked materials, "
        "graduated containers, or a simple arrangement that reads as a "
        "quantity at a glance."
    ),
    "screenshot_mock": (
        "An abstracted device or interface scene with implied panels and "
        "regions but no actual copy or UI controls, framed as a clean "
        "product still."
    ),
    "editorial": (
        "An editorial-magazine composition: layered subjects with "
        "intentional crops, considered negative space, and a single "
        "emotional focal point."
    ),
    "background": (
        "A subtle textural backdrop — soft gradients, paper grain, or "
        "out-of-focus material that supports overlaid content without "
        "competing with it."
    ),
}


def default_prompt_for_role(role: ImageRoleStyle | str) -> str:
    """Return a default subject seed for `role`. Falls back to `hero`."""
    return DEFAULT_SECTION_VISUAL_PROMPTS.get(
        role, DEFAULT_SECTION_VISUAL_PROMPTS["hero"]
    )
