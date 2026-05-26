"""LangGraph node — plans article cover + per-section ImageSpecs.

Sits between `seo_optimize` and `generate_charts` (Phase 2 / VISUAL-005).
Disabled by default (see `settings.enable_image_planner`); when enabled
it runs one Claude call for the article cover plus one Claude call per
section. Output is `state["image_specs"]: list[ImageSpec]` which the
companion render node consumes.

Boundary invariants (ADR-005):
- Pure planning: no I/O outside the LLM call.
- The node never imports from `src/services/publishing/`.
- Persona key is read from state (`audience_persona`) or falls back to
  `general_business`. Reads `target_audience` and `content_tone` from
  the same state slot already populated by CONTENT-006.
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

from src.models.research import TopicInput
from src.models.visual import ImageSpec
from src.services.visuals.image_planner import (
    plan_article_cover,
    plan_section_images,
)

logger = structlog.get_logger()


_ROLE_PRIORITY: dict[str, int] = {
    # Lower number = higher priority when truncating to the global cap.
    "concept": 0,
    "diagram": 1,
    "process_step": 2,
    "comparison_split": 3,
    "stat_card": 4,
    "editorial": 5,
}


def _truncate_to_total(specs: list[ImageSpec], max_total: int) -> list[ImageSpec]:
    """Trim `specs` to at most `max_total` while keeping cover + variety.

    Strategy:
      1. Always keep the article cover (anchor == "cover") if present.
      2. Drop per-section heroes — the article cover is the only hero.
      3. From the remaining specs, keep one per section before allowing
         a second image in any single section (prefer section variety).
      4. Within a section's queue, prefer information-bearing roles
         (concept/diagram/process_step) over editorial/stat.
    """
    if max_total <= 0:
        return []

    cover = next(
        (s for s in specs if s.placement.anchor == "cover"),
        None,
    )
    kept: list[ImageSpec] = []
    if cover is not None:
        kept.append(cover)

    # Drop per-section heroes — only the article cover may be a hero.
    inline = [s for s in specs if s is not cover and s.role_style != "hero"]
    # Sort inline candidates: section_index then role priority then spec id.
    inline.sort(
        key=lambda s: (
            s.placement.section_index,
            _ROLE_PRIORITY.get(s.role_style, 99),
            s.id,
        )
    )
    # Round-robin one per section first, then second pass for any leftovers.
    by_section: dict[int, list[ImageSpec]] = {}
    for spec in inline:
        by_section.setdefault(spec.placement.section_index, []).append(spec)
    rounds: list[ImageSpec] = []
    while by_section and len(kept) + len(rounds) < max_total:
        for idx in sorted(by_section.keys()):
            if not by_section[idx]:
                continue
            rounds.append(by_section[idx].pop(0))
            if len(kept) + len(rounds) >= max_total:
                break
        by_section = {k: v for k, v in by_section.items() if v}
    return kept + rounds


def make_image_planner_node(
    llm: BaseChatModel,
    *,
    enabled: bool = False,
    max_images_per_section: int = 1,
    max_total_images: int = 3,
) -> Any:  # noqa: ANN401
    """Factory returning a LangGraph node fn for image planning."""

    async def image_planner_node(state: dict[str, Any]) -> dict[str, Any]:
        if not enabled:
            return {}

        section_drafts = state.get("section_drafts") or []
        if not section_drafts:
            return {}

        topic: TopicInput = state["topic"]
        page_art_direction = state.get("page_art_direction")
        audience_persona = state.get("audience_persona")
        target_audience = state.get("target_audience")
        seo_result = state.get("seo_result")
        article_summary = (
            seo_result.summary if seo_result is not None else topic.description
        )
        article_title = topic.title
        article_domain = topic.domain

        all_specs: list[ImageSpec] = []

        try:
            cover = await plan_article_cover(
                article_title=article_title,
                article_summary=article_summary,
                article_domain=article_domain,
                page_art_direction=page_art_direction,
                audience_persona=audience_persona,
                llm=llm,
            )
            all_specs.append(cover)
        except Exception as exc:  # noqa: BLE001 — planner must never crash pipeline
            logger.warning("image_planner_cover_failed", error=str(exc))

        for section in section_drafts:
            try:
                section_specs = await plan_section_images(
                    section=section,
                    article_topic=topic,
                    page_art_direction=page_art_direction,
                    brand_context=None,
                    audience_persona=audience_persona,
                    target_audience=target_audience,
                    max_images=max_images_per_section,
                    llm=llm,
                )
                all_specs.extend(section_specs)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "image_planner_section_failed",
                    section_index=section.section_index,
                    error=str(exc),
                )

        kept = _truncate_to_total(all_specs, max_total_images)
        logger.info(
            "image_planner_complete",
            planned=len(all_specs),
            kept=len(kept),
            section_count=len(section_drafts),
            max_total=max_total_images,
        )
        return {"image_specs": kept}

    return image_planner_node
