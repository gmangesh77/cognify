"""Pydantic model for LLM call tracking."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LlmCall(BaseModel):
    """Record of a single LLM invocation within a pipeline step."""

    id: UUID = Field(default_factory=uuid4)
    step_id: UUID | None = None
    session_id: UUID
    call_name: str
    model_name: str
    prompt_messages: list[dict[str, str]] = Field(default_factory=list)
    response_content: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: int | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
