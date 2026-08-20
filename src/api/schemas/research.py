"""Request/response schemas for the research sessions API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.models.brief import LengthTarget, check_persona, check_tone
from src.models.content import ContentType


class CreateResearchSessionRequest(BaseModel):
    topic_id: UUID
    target_audience: str | None = None
    content_tone: str | None = None
    preferred_angle: str | None = None
    keywords: list[str] | None = None
    topic_description_override: str | None = None
    # How structural diagrams (concept / process_step / comparison_split)
    # are rendered: "illustration" (gpt-image-1) or "mermaid".
    # None = "not given" so a brief's value (or the default) applies.
    structural_diagram_mode: Literal["illustration", "mermaid"] | None = None
    # Outline approval gate (AUTHOR-002). None = fall back to
    # settings.require_outline_approval (resolved by the router).
    require_outline_approval: bool | None = None
    # AUTHOR-003 (ADR-007): pick a saved brief and/or save the inline
    # fields as a new one. Typed against the same Brief field types
    # (ContentType / LengthTarget / VALID_TONES / known personas) so
    # FastAPI returns 422 for a bad value instead of the "save as brief"
    # path raising a bare ValidationError deep inside the router (500).
    brief_id: UUID | None = None
    save_as_brief: bool = False
    brief_name: str | None = Field(default=None, max_length=200)
    content_type: ContentType | None = None
    length_target: LengthTarget | None = None
    audience_persona: str | None = None

    _tone = field_validator("content_tone")(check_tone)
    _persona = field_validator("audience_persona")(check_persona)


class CreateResearchSessionResponse(BaseModel):
    session_id: UUID
    status: str
    started_at: datetime


class AgentStepResponse(BaseModel):
    step_name: str
    status: str
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None
    output_summary: str | None = None


class ResearchSessionResponse(BaseModel):
    session_id: UUID
    topic_id: UUID
    topic_title: str = ""
    status: str
    round_count: int
    findings_count: int
    sources_count: int = 0
    embeddings_count: int = 0
    duration_seconds: float | None
    started_at: datetime
    completed_at: datetime | None
    steps: list[AgentStepResponse]
    require_outline_approval: bool = False
    brief_id: UUID | None = None
    content_type: str | None = None
    length_target: str | None = None


class ResearchSessionSummary(BaseModel):
    session_id: UUID
    topic_id: UUID
    status: str
    round_count: int
    findings_count: int
    sources_count: int = 0
    embeddings_count: int = 0
    topic_title: str = ""
    duration_seconds: float | None = None
    started_at: datetime


class PaginatedResearchSessions(BaseModel):
    items: list[ResearchSessionSummary]
    total: int
    page: int
    size: int
