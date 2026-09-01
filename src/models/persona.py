"""Persona voice engine models (AUTHOR-011)."""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

VoiceBand = Literal["match", "close", "off_voice"]


class DimStat(BaseModel, frozen=True):
    mean: float
    stddev: float
    confidence: float = Field(ge=0.0, le=1.0)


class VoiceFingerprint(BaseModel, frozen=True):
    dims: dict[str, DimStat]
    sample_count: int


class DimScore(BaseModel, frozen=True):
    value: float
    z: float
    confidence: float


class VoiceDeviation(BaseModel, frozen=True):
    dim: str
    observed: float
    target: float
    message: str


class VoiceScore(BaseModel, frozen=True):
    score: int = Field(ge=0, le=100)
    band: VoiceBand
    per_dim: dict[str, DimScore]
    deviations: list[VoiceDeviation]


class PersonaSample(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    persona_id: UUID
    text: str
    word_count: int
    embedding: list[float] | None = None
    created_at: datetime


class SampleCreate(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


class PersonaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class PersonaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class Persona(BaseModel):
    id: UUID
    owner_id: str
    name: str
    description: str | None
    fingerprint: VoiceFingerprint | None
    sample_count: int
    created_at: datetime
    updated_at: datetime
