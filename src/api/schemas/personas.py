"""Request/response schemas for the persona voice API (AUTHOR-011)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.persona import VoiceFingerprint


class PersonaSummary(BaseModel):
    id: UUID
    name: str
    description: str | None
    sample_count: int
    ready: bool
    updated_at: datetime


class SampleView(BaseModel):
    id: UUID
    word_count: int
    preview: str
    created_at: datetime


class PersonaDetail(PersonaSummary):
    fingerprint: VoiceFingerprint | None
    samples: list[SampleView]


class PersonaListResponse(BaseModel):
    items: list[PersonaSummary]


class ScoreRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
