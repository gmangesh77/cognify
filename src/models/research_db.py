"""Research session and agent step models for business state persistence.

These are Pydantic models (not SQLAlchemy) backed by in-memory repositories
for RESEARCH-001. Real DB migration comes in a future ticket.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ResearchSession(BaseModel):
    """Business state for a research session (visible to API)."""

    id: UUID = Field(default_factory=uuid4)
    topic_id: UUID
    status: str = "planning"
    agent_plan: dict[str, object] = Field(default_factory=dict)
    round_count: int = 0
    findings_count: int = 0
    indexed_count: int = 0
    findings_data: list[dict[str, object]] = Field(default_factory=list)
    topic_title: str = ""
    topic_description: str = ""
    topic_domain: str = ""
    duration_seconds: float | None = None
    started_at: datetime
    completed_at: datetime | None = None


class AgentStep(BaseModel):
    """Tracks an individual step within a research session."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    step_name: str
    status: str = "running"
    input_data: dict[str, object] = Field(default_factory=dict)
    output_data: dict[str, object] = Field(default_factory=dict)
    duration_ms: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
