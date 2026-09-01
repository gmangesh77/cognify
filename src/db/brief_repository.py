"""Repository for `briefs` (AUTHOR-003 / ADR-007). Plain CRUD keyed by id;
owner scoping is the service's job."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables_briefs import BriefRow
from src.models.brief import Brief, BriefCreate, BriefUpdate

logger = structlog.get_logger()


def row_to_brief(row: BriefRow) -> Brief:
    # Validate (not just construct) so the DB's plain strings are coerced into
    # the ContentType enum / Literal fields exactly as API input would be.
    return Brief.model_validate(_row_fields(row))


def _row_fields(row: BriefRow) -> dict[str, object]:
    return dict(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        title=row.title,
        description=row.description,
        target_audience=row.target_audience,
        content_tone=row.content_tone,
        preferred_angle=row.preferred_angle,
        keywords=list(row.keywords or []),
        content_type=row.content_type,
        length_target=row.length_target,
        structural_diagram_mode=row.structural_diagram_mode,
        audience_persona=row.audience_persona,
        voice_persona_id=row.voice_persona_id,
        require_outline_approval=row.require_outline_approval,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def brief_create_to_row(owner_id: str, data: BriefCreate) -> BriefRow:
    return BriefRow(owner_id=owner_id, **data.model_dump(mode="json"))


class PgBriefRepository:
    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, owner_id: str, data: BriefCreate) -> Brief:
        async with self._sf() as db:
            row = brief_create_to_row(owner_id, data)
            db.add(row)
            await db.commit()
            await db.refresh(row)
            logger.info("brief_created", brief_id=str(row.id), owner_id=owner_id)
            return row_to_brief(row)

    async def get(self, brief_id: UUID) -> Brief | None:
        async with self._sf() as db:
            row = await db.get(BriefRow, brief_id)
            return row_to_brief(row) if row else None

    async def list_by_owner(self, owner_id: str) -> list[Brief]:
        async with self._sf() as db:
            stmt = (
                select(BriefRow)
                .where(BriefRow.owner_id == owner_id)
                .order_by(BriefRow.updated_at.desc())
            )
            rows = (await db.execute(stmt)).scalars().all()
            return [row_to_brief(r) for r in rows]

    async def update(self, brief_id: UUID, data: BriefUpdate) -> Brief | None:
        async with self._sf() as db:
            row = await db.get(BriefRow, brief_id)
            if row is None:
                return None
            for key, value in data.model_dump(mode="json", exclude_none=True).items():
                setattr(row, key, value)
            await db.commit()
            await db.refresh(row)
            return row_to_brief(row)

    async def delete(self, brief_id: UUID) -> bool:
        async with self._sf() as db:
            result = await db.execute(delete(BriefRow).where(BriefRow.id == brief_id))
            await db.commit()
            return bool(getattr(result, "rowcount", 0))
