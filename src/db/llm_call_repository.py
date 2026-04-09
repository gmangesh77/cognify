"""PostgreSQL repository for LLM call records."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables import LlmCallRow
from src.models.llm_call import LlmCall

logger = structlog.get_logger()


class PgLlmCallRepository:
    """PostgreSQL-backed LLM call repository."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, call: LlmCall) -> LlmCall:
        async with self._sf() as db:
            row = LlmCallRow(
                id=call.id,
                step_id=call.step_id,
                session_id=call.session_id,
                call_name=call.call_name,
                model_name=call.model_name,
                prompt_messages=call.prompt_messages,
                response_content=call.response_content,
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
                duration_ms=call.duration_ms,
                error=call.error,
                started_at=call.started_at,
                completed_at=call.completed_at,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    async def list_by_session(self, session_id: UUID) -> list[LlmCall]:
        async with self._sf() as db:
            query = (
                select(LlmCallRow)
                .where(LlmCallRow.session_id == session_id)
                .order_by(LlmCallRow.started_at)
            )
            result = await db.execute(query)
            return [self._to_model(r) for r in result.scalars().all()]

    async def list_by_step(self, step_id: UUID) -> list[LlmCall]:
        async with self._sf() as db:
            query = (
                select(LlmCallRow)
                .where(LlmCallRow.step_id == step_id)
                .order_by(LlmCallRow.started_at)
            )
            result = await db.execute(query)
            return [self._to_model(r) for r in result.scalars().all()]

    @staticmethod
    def _to_model(row: LlmCallRow) -> LlmCall:
        return LlmCall(
            id=row.id,
            step_id=row.step_id,
            session_id=row.session_id,
            call_name=row.call_name,
            model_name=row.model_name,
            prompt_messages=row.prompt_messages or [],
            response_content=row.response_content or "",
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            duration_ms=row.duration_ms,
            error=row.error,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
