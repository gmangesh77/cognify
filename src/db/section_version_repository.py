"""Repository for `section_versions` (VISUAL-011 / Phase 8).

Append-only history sidecar — no updates, only inserts and reads. The
active section content stays on `canonical_articles.body_markdown`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables import SectionVersionRow

logger = structlog.get_logger()


VersionSource = str  # "manual" | "ai" | "tone_preset" | "restore"


@dataclass(frozen=True)
class SectionVersion:
    """One row in `section_versions`."""

    id: UUID
    article_id: UUID
    section_id: str
    section_index: int
    markdown: str
    source: VersionSource
    instruction: str | None
    model: str | None
    tokens_input: int | None
    tokens_output: int | None
    usd: float | None
    created_at: datetime
    created_by: str | None


class PgSectionVersionRepository:
    """CRUD over `section_versions`. Insert + read only."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def append(
        self,
        *,
        article_id: UUID,
        section_id: str,
        section_index: int,
        markdown: str,
        source: VersionSource,
        instruction: str | None = None,
        model: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        usd: float | None = None,
        created_by: str | None = None,
    ) -> SectionVersion:
        async with self._sf() as db:
            row = SectionVersionRow(
                article_id=article_id,
                section_id=section_id,
                section_index=section_index,
                markdown=markdown,
                source=source,
                instruction=instruction,
                model=model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                usd=usd,
                created_by=created_by,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            logger.info(
                "section_version_appended",
                article_id=str(article_id),
                section_id=section_id,
                source=source,
            )
            return self._to_model(row)

    async def list_for_section(
        self,
        *,
        article_id: UUID,
        section_id: str,
        limit: int = 50,
    ) -> list[SectionVersion]:
        async with self._sf() as db:
            stmt = (
                select(SectionVersionRow)
                .where(
                    SectionVersionRow.article_id == article_id,
                    SectionVersionRow.section_id == section_id,
                )
                .order_by(desc(SectionVersionRow.created_at))
                .limit(limit)
            )
            rows = (await db.execute(stmt)).scalars().all()
            return [self._to_model(r) for r in rows]

    async def get(self, version_id: UUID) -> SectionVersion | None:
        async with self._sf() as db:
            row = await db.get(SectionVersionRow, version_id)
            if row is None:
                return None
            return self._to_model(row)

    @staticmethod
    def _to_model(row: SectionVersionRow) -> SectionVersion:
        return SectionVersion(
            id=row.id,
            article_id=row.article_id,
            section_id=row.section_id,
            section_index=row.section_index,
            markdown=row.markdown,
            source=row.source,
            instruction=row.instruction,
            model=row.model,
            tokens_input=row.tokens_input,
            tokens_output=row.tokens_output,
            usd=row.usd,
            created_at=row.created_at,
            created_by=row.created_by,
        )


__all__ = ["PgSectionVersionRepository", "SectionVersion", "VersionSource"]
