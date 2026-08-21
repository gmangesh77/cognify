"""Content-pipeline initial graph state construction.

Extracted from `ContentService.generate_full_article` so both the
outline-only run and the full pipeline run build the exact same
starting `ContentState` dict. See `docs/LEARNINGS.md` L-006/L-007 for
why the pipeline is a single graph invocation, not separate steps.
"""

from __future__ import annotations

from src.models.research import FacetFindings, TopicInput
from src.models.research_db import ResearchSession


def build_topic_input(session: ResearchSession) -> TopicInput:
    """Build a TopicInput from a ResearchSession's stored topic fields."""
    description = session.topic_description_override or session.topic_description
    return TopicInput(
        id=session.topic_id,
        title=session.topic_title or f"Topic {session.topic_id}",
        description=description,
        domain=session.topic_domain,
    )


def build_initial_state(
    session: ResearchSession,
    topic: TopicInput,
    findings: list[FacetFindings],
) -> dict[str, object]:
    """Build the initial ContentState dict for a fresh pipeline run."""
    return {
        "topic": topic,
        "research_plan": None,
        "findings": findings,
        "session_id": topic.id,
        "outline": None,
        "status": "outline_generating",
        "error": None,
        "target_audience": session.target_audience,
        "content_tone": session.content_tone,
        "preferred_angle": session.preferred_angle,
        "keywords": session.keywords,
        "structural_diagram_mode": session.structural_diagram_mode,
        # VISUAL-005 / Phase 2 — image planner inputs. Phase 7 will
        # surface these via the Settings UI; until then they default to
        # None and the planner falls back to general_business.
        "audience_persona": session.audience_persona,
        "brief_id": session.brief_id,
        "page_art_direction": None,
        "image_specs": [],
    }
