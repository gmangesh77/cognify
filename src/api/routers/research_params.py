"""Resolve a session-create request (+ optional Brief) into SessionParams.

Precedence per field: inline value (not None) > brief value > default.
The brief is copied, never referenced again (ADR-007 invariant).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.api.schemas.research import CreateResearchSessionRequest
from src.models.brief import Brief, BriefCreate
from src.models.content import ContentType
from src.models.session_params import SessionParams

# content_type is handled separately in resolve_session_params: the request
# validates it as ContentType (an enum) but SessionParams.content_type is a
# plain str, and model_copy(update=...) skips validation/coercion.
_INLINE_FIELDS = (
    "target_audience",
    "content_tone",
    "preferred_angle",
    "keywords",
    "topic_description_override",
    "structural_diagram_mode",
    "require_outline_approval",
    "length_target",
    "audience_persona",
)


@dataclass(frozen=True)
class ParamSources:
    body: CreateResearchSessionRequest
    brief: Brief | None
    default_gate: bool


def resolve_session_params(src: ParamSources) -> SessionParams:
    base = SessionParams.from_brief(src.brief) if src.brief else SessionParams()
    if src.brief is None:
        base = base.model_copy(update={"require_outline_approval": src.default_gate})
    overrides: dict[str, object] = {
        name: getattr(src.body, name)
        for name in _INLINE_FIELDS
        if getattr(src.body, name) is not None
    }
    if src.body.content_type is not None:
        overrides["content_type"] = str(src.body.content_type)
    return base.model_copy(update=overrides)


def inline_brief_create(
    body: CreateResearchSessionRequest, topic_title: str, default_gate: bool = False
) -> BriefCreate:
    """Build a BriefCreate from the inline request fields ("save as brief").

    `default_gate` is the settings default for the outline gate; it applies
    only when the request omits `require_outline_approval`, so the saved brief
    records the same value the plain inline path would have used.
    """
    gate = body.require_outline_approval
    return BriefCreate(
        name=body.brief_name or topic_title[:200],
        title=topic_title,
        description=body.topic_description_override,
        target_audience=body.target_audience,
        content_tone=body.content_tone,
        preferred_angle=body.preferred_angle,
        keywords=body.keywords or [],
        content_type=body.content_type or ContentType.ARTICLE,
        length_target=body.length_target or "medium",
        structural_diagram_mode=body.structural_diagram_mode or "illustration",
        audience_persona=body.audience_persona,
        require_outline_approval=default_gate if gate is None else gate,
    )
