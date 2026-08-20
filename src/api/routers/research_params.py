"""Resolve a session-create request (+ optional Brief) into SessionParams.

Precedence per field: inline value (not None) > brief value > default.
The brief is copied, never referenced again (ADR-007 invariant).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from src.api.schemas.research import CreateResearchSessionRequest
from src.models.brief import Brief, BriefCreate, LengthTarget
from src.models.content import ContentType
from src.models.session_params import SessionParams

_INLINE_FIELDS = (
    "target_audience",
    "content_tone",
    "preferred_angle",
    "keywords",
    "topic_description_override",
    "structural_diagram_mode",
    "require_outline_approval",
    "content_type",
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
    overrides = {
        name: getattr(src.body, name)
        for name in _INLINE_FIELDS
        if getattr(src.body, name) is not None
    }
    return base.model_copy(update=overrides)


def inline_brief_create(
    body: CreateResearchSessionRequest, topic_title: str
) -> BriefCreate:
    """Build a BriefCreate from the inline request fields ("save as brief")."""
    return BriefCreate(
        name=body.brief_name or topic_title[:200],
        title=topic_title,
        description=body.topic_description_override,
        target_audience=body.target_audience,
        content_tone=body.content_tone,
        preferred_angle=body.preferred_angle,
        keywords=body.keywords or [],
        content_type=ContentType(body.content_type or "article"),
        length_target=cast(LengthTarget, body.length_target or "medium"),
        structural_diagram_mode=body.structural_diagram_mode or "illustration",
        audience_persona=body.audience_persona,
        require_outline_approval=bool(body.require_outline_approval),
    )
