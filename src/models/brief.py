"""Brief — the authoring *input* contract (ADR-007).

A Brief is everything a human tells the pipeline before it runs. Sessions
copy its values at start (denormalised); the brief row is never read by
the pipeline afterwards, so editing a brief never alters a past session.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.content import ContentType
from src.models.tones import VALID_TONES
from src.services.visuals.persona_directions import PERSONA_VISUAL_DIRECTIONS

LengthTarget = Literal["short", "medium", "long", "pillar"]
DiagramMode = Literal["illustration", "mermaid"]


def check_tone(value: str | None) -> str | None:
    if value is not None and value not in VALID_TONES:
        raise ValueError(f"content_tone must be one of {VALID_TONES}")
    return value


def check_persona(value: str | None) -> str | None:
    if value is not None and value not in PERSONA_VISUAL_DIRECTIONS:
        raise ValueError("unknown audience_persona")
    return value


class BriefFields(BaseModel):
    """Fields shared by create / read shapes."""

    name: str = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=4000)
    target_audience: str | None = Field(default=None, max_length=500)
    content_tone: str | None = None
    preferred_angle: str | None = Field(default=None, max_length=500)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    content_type: ContentType = ContentType.ARTICLE
    length_target: LengthTarget = "medium"
    structural_diagram_mode: DiagramMode = "illustration"
    audience_persona: str | None = None
    require_outline_approval: bool = False

    _tone = field_validator("content_tone")(check_tone)
    _persona = field_validator("audience_persona")(check_persona)


class BriefCreate(BriefFields):
    """POST /briefs body."""


class BriefUpdate(BaseModel):
    """PATCH /briefs/{id} body — partial; at least one field required."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=4000)
    target_audience: str | None = Field(default=None, max_length=500)
    content_tone: str | None = None
    preferred_angle: str | None = Field(default=None, max_length=500)
    keywords: list[str] | None = Field(default=None, max_length=20)
    content_type: ContentType | None = None
    length_target: LengthTarget | None = None
    structural_diagram_mode: DiagramMode | None = None
    audience_persona: str | None = None
    require_outline_approval: bool | None = None

    _tone = field_validator("content_tone")(check_tone)
    _persona = field_validator("audience_persona")(check_persona)

    @model_validator(mode="after")
    def _at_least_one(self) -> "BriefUpdate":
        if not self.model_dump(exclude_none=True):
            raise ValueError("at least one field must be provided")
        return self


class Brief(BriefFields):
    """Persisted brief."""

    id: UUID
    owner_id: str
    created_at: datetime
    updated_at: datetime
