"""Response schemas for pipeline debug endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LlmCallResponse(BaseModel):
    """Single LLM invocation record."""

    id: UUID
    step_id: UUID | None
    call_name: str
    model_name: str
    prompt_messages: list[dict[str, str]]
    response_content: str
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: int | None
    error: str | None
    started_at: datetime
    completed_at: datetime | None


class DebugStepResponse(BaseModel):
    """Agent step with full input/output data and LLM calls."""

    id: UUID
    step_name: str
    status: str
    input_data: dict[str, object]
    output_data: dict[str, object]
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None
    llm_calls: list[LlmCallResponse]


class PipelineDebugResponse(BaseModel):
    """Full pipeline trace for a research session."""

    session_id: UUID
    topic_title: str
    topic_domain: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    target_audience: str | None
    content_tone: str | None
    preferred_angle: str | None
    steps: list[DebugStepResponse]
    total_llm_calls: int
    total_input_tokens: int
    total_output_tokens: int


class DebugSessionSummary(BaseModel):
    """Compact session summary for the session list."""

    session_id: UUID
    topic_title: str
    status: str
    started_at: datetime
    duration_seconds: float | None
    step_count: int
    llm_call_count: int


class PaginatedDebugSessions(BaseModel):
    """Paginated list of debug session summaries."""

    items: list[DebugSessionSummary]
    total: int
    page: int
    size: int
