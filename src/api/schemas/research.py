"""Request/response schemas for the research sessions API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateResearchSessionRequest(BaseModel):
    topic_id: UUID


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


class ResearchSessionResponse(BaseModel):
    session_id: UUID
    status: str
    round_count: int
    findings_count: int
    duration_seconds: float | None
    started_at: datetime
    completed_at: datetime | None
    steps: list[AgentStepResponse]


class ResearchSessionSummary(BaseModel):
    session_id: UUID
    topic_id: UUID
    status: str
    round_count: int
    findings_count: int
    started_at: datetime


class PaginatedResearchSessions(BaseModel):
    items: list[ResearchSessionSummary]
    total: int
    page: int
    size: int
