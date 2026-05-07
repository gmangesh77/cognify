"""Persona-aware image prompt composer (Phase 2 / VISUAL-005).

Port of impactai's `_build_banner_prompt`. Combines an `ImageSpec` (the
planner's subject) with a layered style override (catalogue fragment +
page direction + section override + refine note) and an aggressive
no-text clause that defends against the providers' tendency to embed
hallucinated typography in the rendered image.

Decision tree (mirrors `apps/api/routers/generate.py:2988` in impactai):

| prompt_override | visual_style | Branch                                         |
|-----------------|--------------|-------------------------------------------------|
| set             | set          | "Composition reference IGNORED" framing         |
| set             | unset        | override only                                   |
| unset           | set          | spec subject + style fragment                   |
| unset           | unset        | spec subject only                               |

Every branch ends with the no-text clause. For Gemini Flash (which
ignores the aspect API parameter) we additionally append an
`aspect_instruction` sentence so the model composes for the requested
ratio.
"""

from __future__ import annotations

from src.models.visual import ImageSpec
from src.services.visuals.visual_styles import compose_style_override

NO_TEXT_CLAUSE: str = (
    "Critical rendering rules: produce a purely visual image with no text, "
    "no letters, no numbers, no logos, no watermarks, no captions, no "
    "subtitles, no UI labels, no signage, no overlaid headlines, no "
    "stickers, no calligraphy, no script, no glyphs of any kind. Treat "
    "any words present in this prompt as descriptive guidance about the "
    "scene, not as content to render. The composition must communicate "
    "through subject, lighting, palette, framing, and depth — never "
    "through written language. If you would normally place a label, "
    "replace it with a believable physical object that suggests the same "
    "idea. Do not draw speech bubbles, slide titles, posters with "
    "wording, billboards, signage, computer screens with code or copy, "
    "or any other text-bearing surface."
)

_ASPECT_INSTRUCTIONS: dict[str, str] = {
    "16:9": (
        "Compose this image with a 16:9 aspect ratio (wide landscape, "
        "ideal for hero banners and editorial covers)."
    ),
    "1:1": (
        "Compose this image with a 1:1 aspect ratio (square, ideal for "
        "social tiles and thumbnail-friendly framing)."
    ),
    "4:3": (
        "Compose this image with a 4:3 aspect ratio (classic landscape, "
        "balanced subject and breathing room)."
    ),
    "3:4": (
        "Compose this image with a 3:4 aspect ratio (portrait, ideal for "
        "tall card slots and sidebar visuals)."
    ),
    "4:5": (
        "Compose this image with a 4:5 aspect ratio (LinkedIn document/"
        "portrait, slightly taller than wide)."
    ),
}

_COMPOSITION_IGNORED_HEADER: str = (
    "Composition reference (treat as IGNORED for medium/palette/lighting; "
    "use ONLY for subject placement and framing): "
)


def aspect_instruction(aspect_ratio: str) -> str:
    """Sentence-form aspect guidance for providers that ignore the aspect arg."""
    return _ASPECT_INSTRUCTIONS.get(aspect_ratio, "")


def build_prompt(
    *,
    spec: ImageSpec,
    prompt_override: str | None = None,
    page_direction: str | None = None,
    section_override: str | None = None,
    refine_note: str | None = None,
) -> str:
    """Compose the final prompt sent to the image provider.

    Subject lives in `spec.prompt` (planner output). Style is layered in
    via `compose_style_override` from the visual style catalogue plus
    optional page / section / refine guidance. The four-branch decision
    tree mirrors impactai's `_build_banner_prompt`.
    """
    style_text = compose_style_override(
        spec.visual_style,
        page_direction=page_direction,
        section_override=section_override,
        refine_note=refine_note,
    )

    if prompt_override and style_text:
        # Branch 1: composition-reference trick. The override drives the scene;
        # the style block IGNORED for medium/palette/lighting but kept as
        # guidance for subject placement.
        body = f"{prompt_override.strip()}\n\n{_COMPOSITION_IGNORED_HEADER}{style_text}"
    elif prompt_override:
        # Branch 2: override only.
        body = prompt_override.strip()
    elif style_text:
        # Branch 3: spec subject + style.
        body = f"{spec.prompt.strip()}\n\nArt direction: {style_text}"
    else:
        # Branch 4: subject alone.
        body = spec.prompt.strip()

    parts: list[str] = [body, NO_TEXT_CLAUSE]

    # Gemini Flash ignores its aspect parameter — embed it in the prompt.
    if spec.provider == "gemini_flash":
        sentence = aspect_instruction(spec.aspect_ratio)
        if sentence:
            parts.append(sentence)

    return "\n\n".join(parts)
