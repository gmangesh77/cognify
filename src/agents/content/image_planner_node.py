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


def make_image_planner_node(
    llm: BaseChatModel,
    *,
    enabled: bool = False,
    max_images_per_section: int = 4,
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

        logger.info(
            "image_planner_complete",
            spec_count=len(all_specs),
            section_count=len(section_drafts),
        )
        return {"image_specs": all_specs}

    return image_planner_node
