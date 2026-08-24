"""Response schemas for the usage endpoints (AUTHOR-005)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from src.services.usage import SessionUsage


class OperationUsageResponse(BaseModel):
    """Cost roll-up for one pipeline operation."""

    op: str
    llm_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class SessionUsageResponse(BaseModel):
    """Total usage for one research session (or the article it produced)."""

    session_id: UUID
    llm_calls: int
    input_tokens: int
    output_tokens: int
    images: int
    cost_usd: float
    by_operation: list[OperationUsageResponse]


def to_usage_response(session_id: UUID, usage: SessionUsage) -> SessionUsageResponse:
    return SessionUsageResponse(
        session_id=session_id,
        llm_calls=usage.llm_calls,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        images=usage.images,
        cost_usd=usage.cost_usd,
        by_operation=[
            OperationUsageResponse(
                op=o.op,
                llm_calls=o.llm_calls,
                input_tokens=o.input_tokens,
                output_tokens=o.output_tokens,
                cost_usd=o.cost_usd,
            )
            for o in usage.by_operation
        ],
    )


__all__ = ["OperationUsageResponse", "SessionUsageResponse", "to_usage_response"]
