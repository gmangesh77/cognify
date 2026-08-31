"""Persona-aware image planner (Phase 2 / VISUAL-005).

One Claude call per (section, article-cover). Returns a list of
`ImageSpec` describing the images we want to render. Falls back to a
single role-default spec when the LLM returns garbage or empty for a
section that needs a cover.

Boundary invariants (ADR-005):
- Pure planning: no I/O, no provider calls. Provider routing and disk
  writes happen in `image_render_node`.
- Single source of truth for the catalogue, persona register, and
  banned-cliche list — all imported from neighbouring `src/services/
  visuals/` modules.
- `parse_llm_json` for every LLM response (L-002).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.content_pipeline import SectionDraft
from src.models.research import TopicInput
from src.models.visual import (
    ImagePlacement,
    ImageRoleStyle,
    ImageSpec,
)
from src.services.visuals.banned_cliches import cliche_block_for_style
from src.services.visuals.default_prompts import default_prompt_for_role
from src.services.visuals.persona_directions import (
    DEFAULT_PERSONA,
    get_persona_register,
)
from src.services.visuals.visual_styles import (
    ROLE_STYLE_DEFAULTS,
    get_style,
    planner_catalogue_block,
)
from src.utils.llm_json import parse_llm_json

logger = structlog.get_logger()

_PLANNER_SYSTEM_INTRO: str = (
    "You are an art director planning the visual layout for a long-form "
    "editorial article. Pick from the catalogued visual styles below. "
    "Each spec describes one image to render: its role, style, subject, "
    "aspect ratio, and where it sits in the section. Vary visual style "
    "across specs in the same section so the page does not feel "
    "monotonous. Return JSON only — no commentary, no markdown fences."
)

_PLANNER_OUTPUT_SHAPE: str = (
    "Return a JSON array of objects (zero or more). Each object MUST have:\n"
    '  - "id": short string identifier (e.g. "intro_hero", "deep_concept_1")\n'
    '  - "role_style": one of hero | feature_card | concept | process_step | '
    "comparison_split | quote_card | stat_card | screenshot_mock | editorial "
    "| background\n"
    '  - "visual_style": one of the catalogue keys below (or null)\n'
    '  - "prompt": subject-only sentence describing what to render. NO style '
    "verbiage, NO text-on-image instructions.\n"
    '  - "alt_text": short accessible alt text\n'
    '  - "caption": a SHORT plain title for the figure, max 8 words, e.g. '
    '"Pod DNS Query Flow" or "RPA vs Agentic Automation". This is shown to '
    "readers as the figure caption. Write it as a neutral title ONLY — do "
    "NOT describe the reader, the prose, the article, or why the image was "
    'chosen, and do not start with phrases like "A diagram showing". For '
    "purely decorative hero/background images, use null.\n"
    '  - "aspect_ratio": one of 16:9 | 1:1 | 4:3 | 3:4 | 4:5\n'
    '  - "placement": object with "anchor" (top | before_heading | '
    "between_paragraphs | bottom_grid | background | column_split), "
    'optional "heading_text", optional "paragraph_index", and "section_index" '
    "(integer; pass the supplied section index)\n"
    '  - "rationale": one internal sentence on why this spec belongs here '
    "(optional; NOT shown to readers — never put reader-facing text here)"
)

# The cover shape MUST repeat the full field list (`_PLANNER_OUTPUT_SHAPE`)
# in its message. Before VISUAL-013 it only said "fields are the same as a
# section spec" without including that spec — so the model invented its own
# field name for the subject ("description") and every cover silently fell
# back to the generic default hero.
_COVER_OUTPUT_SHAPE: str = (
    "Return a JSON OBJECT (not an array) describing exactly one cover "
    "image. Use exactly the fields listed above — the subject sentence "
    'goes in "prompt". "placement.anchor" MUST be "cover" and '
    '"placement.section_index" MUST be -1. The role_style should typically '
    'be "hero" unless the article asks for something else.'
)


def build_planner_messages(
    *,
    section: SectionDraft,
    article_topic: TopicInput,
    page_art_direction: str | None,
    brand_context: str | None,
    audience_persona: str | None,
    target_audience: str | None,
    max_images: int,
) -> list[SystemMessage | HumanMessage]:
    """Assemble the planner messages for a single section."""
    persona_key = audience_persona or DEFAULT_PERSONA
    persona_register = get_persona_register(persona_key)
    cliches = cliche_block_for_style(None)
    catalogue = planner_catalogue_block()

    system = (
        f"{_PLANNER_SYSTEM_INTRO}\n\n"
        f"Audience persona: {persona_key}.\n"
        f"Persona visual register:\n{persona_register}\n\n"
        f"{catalogue}\n\n"
        f"{cliches}\n\n"
        f"{_PLANNER_OUTPUT_SHAPE}\n\n"
        f"Plan AT MOST {max_images} images for this section. Returning fewer "
        "(or zero) is encouraged when the section is filler or the visuals "
        "would not add value."
    )

    page_dir_line = (
        f"Page art direction (applies to the whole article): {page_art_direction}\n"
        if page_art_direction
        else ""
    )
    brand_line = f"Brand context: {brand_context}\n" if brand_context else ""
    audience_line = (
        f"Target audience (free text): {target_audience}\n" if target_audience else ""
    )

    human = (
        f"Article topic: {article_topic.title}\n"
        f"Domain: {article_topic.domain}\n"
        f"Description: {article_topic.description}\n"
        f"{page_dir_line}{brand_line}{audience_line}"
        f"\nSection index: {section.section_index}\n"
        f"Section heading: {section.title}\n"
        f"Section body:\n{section.body_markdown}\n"
    )

    return [SystemMessage(content=system), HumanMessage(content=human)]


def build_cover_messages(
    *,
    article_title: str,
    article_summary: str,
    article_domain: str,
    page_art_direction: str | None,
    audience_persona: str | None,
) -> list[SystemMessage | HumanMessage]:
    """Assemble the planner messages for a single article-level cover."""
    persona_key = audience_persona or DEFAULT_PERSONA
    persona_register = get_persona_register(persona_key)
    cliches = cliche_block_for_style(None)
    catalogue = planner_catalogue_block()

    system = (
        f"{_PLANNER_SYSTEM_INTRO}\n\n"
        f"Audience persona: {persona_key}.\n"
        f"Persona visual register:\n{persona_register}\n\n"
        f"{catalogue}\n\n"
        f"{cliches}\n\n"
        f"{_PLANNER_OUTPUT_SHAPE}\n\n"
        f"{_COVER_OUTPUT_SHAPE}"
    )

    page_dir_line = (
        f"Page art direction: {page_art_direction}\n" if page_art_direction else ""
    )
    human = (
        f"Article title: {article_title}\n"
        f"Domain: {article_domain}\n"
        f"Summary: {article_summary}\n"
        f"{page_dir_line}"
        "\nPlan the single hero/cover image for this article."
    )
    return [SystemMessage(content=system), HumanMessage(content=human)]


async def plan_section_images(
    *,
    section: SectionDraft,
    article_topic: TopicInput,
    page_art_direction: str | None,
    brand_context: str | None,
    audience_persona: str | None,
    target_audience: str | None,
    max_images: int,
    llm: BaseChatModel,
) -> list[ImageSpec]:
    """Plan zero-to-`max_images` ImageSpecs for one section.

    Falls back to one synthesised spec when parsing fails (never empty
    on parse failure) but DOES respect a legitimately empty array
    response from the LLM (filler sections may have no visuals).
    """
    messages = build_planner_messages(
        section=section,
        article_topic=article_topic,
        page_art_direction=page_art_direction,
        brand_context=brand_context,
        audience_persona=audience_persona,
        target_audience=target_audience,
        max_images=max_images,
    )
    response = await llm.ainvoke(messages)
    raw = str(response.content)
    try:
        data = parse_llm_json(raw)
    except json.JSONDecodeError:
        logger.warning(
            "image_planner_section_unparseable",
            section_index=section.section_index,
            raw_preview=raw[:120],
        )
        return [_fallback_section_spec(section)]

    if not isinstance(data, list):
        logger.warning(
            "image_planner_section_unexpected_shape",
            section_index=section.section_index,
            actual_type=type(data).__name__,
        )
        return [_fallback_section_spec(section)]

    specs: list[ImageSpec] = []
    for entry in data[:max_images]:
        spec = _coerce_spec(entry, fallback_section_index=section.section_index)
        if spec is not None:
            specs.append(spec)
    return specs


async def plan_article_cover(
    *,
    article_title: str,
    article_summary: str,
    article_domain: str,
    page_art_direction: str | None,
    audience_persona: str | None,
    llm: BaseChatModel,
) -> ImageSpec:
    """Plan the single article-level cover. Always returns a spec."""
    messages = build_cover_messages(
        article_title=article_title,
        article_summary=article_summary,
        article_domain=article_domain,
        page_art_direction=page_art_direction,
        audience_persona=audience_persona,
    )
    response = await llm.ainvoke(messages)
    raw = str(response.content)
    try:
        data = parse_llm_json(raw)
    except json.JSONDecodeError:
        logger.warning("image_planner_cover_unparseable", raw_preview=raw[:120])
        return _fallback_cover_spec()

    if isinstance(data, list):
        # Tolerate planner returning a one-element array.
        data = data[0] if data else None

    if not isinstance(data, dict):
        return _fallback_cover_spec()

    spec = _coerce_spec(data, fallback_section_index=-1, force_cover=True)
    return spec if spec is not None else _fallback_cover_spec()


def _coerce_spec(
    raw: object,
    *,
    fallback_section_index: int,
    force_cover: bool = False,
) -> ImageSpec | None:
    """Validate one raw dict into an ImageSpec, or return None on failure."""
    if not isinstance(raw, dict):
        return None
    raw_dict: dict[str, Any] = dict(raw)

    placement_raw = raw_dict.get("placement")
    if isinstance(placement_raw, dict):
        placement_dict = dict(placement_raw)
        # Always override section_index — the caller knows which section
        # is being planned; the LLM is free to hallucinate.
        placement_dict["section_index"] = fallback_section_index
        if force_cover:
            placement_dict["anchor"] = "cover"
            placement_dict["section_index"] = -1
    elif force_cover:
        placement_dict = {"anchor": "cover", "section_index": -1}
    else:
        placement_dict = {"section_index": fallback_section_index}
    raw_dict["placement"] = placement_dict

    raw_dict.setdefault("id", f"spec_{uuid.uuid4().hex[:8]}")
    if not raw_dict.get("prompt"):
        # Models sometimes put the subject sentence under a different key
        # (observed live: covers came back with "description"). Accept the
        # common aliases rather than silently dropping the whole spec.
        for alias in ("description", "subject"):
            value = raw_dict.get(alias)
            if isinstance(value, str) and value.strip():
                raw_dict["prompt"] = value.strip()[:2000]
                break
    if not raw_dict.get("prompt"):
        # This was a silent `return None` — the only unlogged failure path
        # in the planner, which hid the all-fallback-heroes bug for months.
        logger.warning(
            "image_planner_spec_missing_prompt",
            id=raw_dict.get("id"),
            keys=sorted(raw_dict.keys()),
        )
        return None

    try:
        return ImageSpec.model_validate(raw_dict)
    except ValidationError as exc:
        logger.warning(
            "image_planner_spec_invalid",
            error=str(exc),
            id=raw_dict.get("id"),
        )
        return None


def _fallback_section_spec(section: SectionDraft) -> ImageSpec:
    """Synthesise one role-default spec when the planner returns garbage."""
    role: ImageRoleStyle = "feature_card"
    style_key = ROLE_STYLE_DEFAULTS.get(role)
    style_entry = get_style(style_key) if style_key else None
    aspect_raw = style_entry.get("default_aspect", "16:9") if style_entry else "16:9"
    valid_aspects = {"16:9", "1:1", "4:3", "3:4", "4:5"}
    aspect = aspect_raw if aspect_raw in valid_aspects else "16:9"
    return ImageSpec(
        id=f"fallback_{uuid.uuid4().hex[:8]}",
        role_style=role,
        visual_style=style_key,
        prompt=default_prompt_for_role(role),
        alt_text=section.title,
        aspect_ratio=aspect,  # type: ignore[arg-type]
        placement=ImagePlacement(anchor="top", section_index=section.section_index),
        rationale="Fallback synthesised when LLM did not return a parseable plan.",
    )


def _fallback_cover_spec() -> ImageSpec:
    """Synthesise a hero cover when the planner returns garbage."""
    role: ImageRoleStyle = "hero"
    style_key = ROLE_STYLE_DEFAULTS.get(role)
    return ImageSpec(
        id=f"fallback_{uuid.uuid4().hex[:8]}",
        role_style=role,
        visual_style=style_key,
        prompt=default_prompt_for_role(role),
        alt_text="",
        aspect_ratio="16:9",
        placement=ImagePlacement(anchor="cover", section_index=-1),
        rationale="Fallback hero cover.",
    )
