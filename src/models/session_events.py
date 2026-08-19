"""Typed events streamed to the dashboard for a research/article session."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

EventType = Literal[
    "snapshot",
    "status_changed",
    "step_started",
    "step_progress",
    "step_done",
    "step_failed",
    "done",
    "error",
    "keepalive",
]

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"article_complete", "article_failed", "failed", "cancelled", "completed"}
)


class SessionEvent(BaseModel):
    type: EventType
    session_id: UUID
    status: str | None = None
    step: str | None = None
    data: dict[str, object] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_sse(self) -> str:
        """Serialize as one SSE frame (``event:`` + ``data:`` lines)."""
        return f"event: {self.type}\ndata: {self.model_dump_json()}\n\n"
