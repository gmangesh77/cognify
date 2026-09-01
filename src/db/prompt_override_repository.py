"""Repositories for `prompt_overrides` (AUTHOR-012). One row per key."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables_prompt_overrides import PromptOverrideRow
from src.models.prompt_override import PromptOverride

logger = structlog.get_logger()


class PromptOverrideRepository(Protocol):
    async def load_all(self) -> dict[str, str]: ...
    async def get(self, key: str) -> PromptOverride | None: ...
    async def upsert(
        self, key: str, *, template: str, updated_by: str
    ) -> PromptOverride: ...
    async def delete(self, key: str) -> bool: ...


def _row_to_model(row: PromptOverrideRow) -> PromptOverride:
    return PromptOverride(
        key=row.key,
        template=row.template,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


class PgPromptOverrideRepository:
    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def load_all(self) -> dict[str, str]:
        async with self._sf() as db:
            rows = (await db.execute(select(PromptOverrideRow))).scalars().all()
            return {r.key: r.template for r in rows}

    async def get(self, key: str) -> PromptOverride | None:
        async with self._sf() as db:
            row = await self._find(db, key)
            return _row_to_model(row) if row else None

    async def upsert(
        self, key: str, *, template: str, updated_by: str
    ) -> PromptOverride:
        async with self._sf() as db:
            row = await self._find(db, key)
            if row is None:
                row = PromptOverrideRow(
                    key=key, template=template, updated_by=updated_by
                )
                db.add(row)
            else:
                row.template, row.updated_by = template, updated_by
            await db.commit()
            await db.refresh(row)
            logger.info("prompt_override_saved", key=key, updated_by=updated_by)
            return _row_to_model(row)

    async def delete(self, key: str) -> bool:
        async with self._sf() as db:
            result = await db.execute(
                delete(PromptOverrideRow).where(PromptOverrideRow.key == key)
            )
            await db.commit()
            existed = bool(getattr(result, "rowcount", 0))
            logger.info("prompt_override_reset", key=key, existed=existed)
            return existed

    @staticmethod
    async def _find(db: AsyncSession, key: str) -> PromptOverrideRow | None:
        stmt = select(PromptOverrideRow).where(PromptOverrideRow.key == key)
        return (await db.execute(stmt)).scalar_one_or_none()


class InMemoryPromptOverrideRepository:
    """Unit tests + no-DB lifespan branch."""

    def __init__(self) -> None:
        self._rows: dict[str, PromptOverride] = {}

    async def load_all(self) -> dict[str, str]:
        return {k: v.template for k, v in self._rows.items()}

    async def get(self, key: str) -> PromptOverride | None:
        return self._rows.get(key)

    async def upsert(
        self, key: str, *, template: str, updated_by: str
    ) -> PromptOverride:
        row = PromptOverride(
            key=key,
            template=template,
            updated_by=updated_by,
            updated_at=datetime.now(UTC),
        )
        self._rows[key] = row
        return row

    async def delete(self, key: str) -> bool:
        return self._rows.pop(key, None) is not None
