"""Everything a research session copies from a Brief / inline request.

Bundles the per-session authoring inputs so `ResearchService.start_session`
takes one object (≤3-param rule) and so the brief → session denormalisation
(ADR-007) lives in exactly one place.
"""

from uuid import UUID

from pydantic import BaseModel

from src.models.brief import Brief


class SessionParams(BaseModel):
    target_audience: str | None = None
    content_tone: str | None = None
    preferred_angle: str | None = None
    keywords: list[str] | None = None
    topic_description_override: str | None = None
    structural_diagram_mode: str = "illustration"
    require_outline_approval: bool = False
    brief_id: UUID | None = None
    content_type: str | None = None
    length_target: str | None = None
    audience_persona: str | None = None

    @classmethod
    def from_brief(cls, brief: Brief) -> "SessionParams":
        return cls(
            target_audience=brief.target_audience,
            content_tone=brief.content_tone,
            preferred_angle=brief.preferred_angle,
            keywords=list(brief.keywords) or None,
            topic_description_override=brief.description,
            structural_diagram_mode=brief.structural_diagram_mode,
            require_outline_approval=brief.require_outline_approval,
            brief_id=brief.id,
            content_type=str(brief.content_type),
            length_target=brief.length_target,
            audience_persona=brief.audience_persona,
        )
