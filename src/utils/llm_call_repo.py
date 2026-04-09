"""Repository protocol and in-memory implementation for LLM call records."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.models.llm_call import LlmCall


class LlmCallRepository(Protocol):
    """Protocol for persisting LLM call records."""

    async def create(self, call: LlmCall) -> LlmCall: ...

    async def list_by_session(self, session_id: UUID) -> list[LlmCall]: ...

    async def list_by_step(self, step_id: UUID) -> list[LlmCall]: ...


class InMemoryLlmCallRepository:
    """In-memory implementation for testing."""

    def __init__(self) -> None:
        self._calls: list[LlmCall] = []

    async def create(self, call: LlmCall) -> LlmCall:
        self._calls.append(call)
        return call

    async def list_by_session(self, session_id: UUID) -> list[LlmCall]:
        return [c for c in self._calls if c.session_id == session_id]

    async def list_by_step(self, step_id: UUID) -> list[LlmCall]:
        return [c for c in self._calls if c.step_id == step_id]
