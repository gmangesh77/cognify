"""Repository for `image_asset_tags` (Phase 7 / VISUAL-010).

Tags are user-curated labels on rendered image assets. Schema is
intentionally narrow — `(article_id, spec_id, tag)` with a unique
constraint so the same asset can carry multiple tags but the same tag
never duplicates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables import ImageAssetTagRow

logger = structlog.get_logger()


@dataclass(frozen=True)
class ImageAssetTag:
    """One row in the image_asset_tags table."""

    id: UUID
    article_id: UUID
    spec_id: str
    tag: str
    note: str | None
    created_at: datetime


class PgImageAssetTagRepository:
    """CRUD over `image_asset_tags`."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def add_tag(
        self,
        *,
        article_id: UUID,
        spec_id: str,
        tag: str,
        note: str | None = None,
    ) -> ImageAssetTag:
        """Add a tag. Returns the existing row if it already exists."""
        async with self._sf() as db:
            row = ImageAssetTagRow(
                article_id=article_id,
                spec_id=spec_id,
                tag=tag,
                note=note,
            )
            db.add(row)
            try:
                await db.commit()
                await db.refresh(row)
                logger.info(
                    "image_asset_tag_added",
                    article_id=str(article_id),
                    spec_id=spec_id,
                    tag=tag,
                )
                return self._to_model(row)
            except IntegrityError:
                await db.rollback()
                # Race / duplicate — return the existing row.
                existing_row = (
                    await db.execute(
                        select(ImageAssetTagRow).where(
                            ImageAssetTagRow.article_id == article_id,
                            ImageAssetTagRow.spec_id == spec_id,
                            ImageAssetTagRow.tag == tag,
                        )
                    )
                ).scalar_one()
                return self._to_model(existing_row)

    async def remove_tag(
        self,
        *,
        article_id: UUID,
        spec_id: str,
        tag: str,
    ) -> bool:
        """Remove a tag. Returns True when a row was deleted."""
        async with self._sf() as db:
            stmt = delete(ImageAssetTagRow).where(
                ImageAssetTagRow.article_id == article_id,
                ImageAssetTagRow.spec_id == spec_id,
                ImageAssetTagRow.tag == tag,
            )
            result = await db.execute(stmt)
            await db.commit()
            # `delete()` returns CursorResult at runtime, but mypy sees
            # the base `Result` (without `rowcount`); fall back via getattr.
            row_count = getattr(result, "rowcount", 0) or 0
            removed = row_count > 0
            if removed:
                logger.info(
                    "image_asset_tag_removed",
                    article_id=str(article_id),
                    spec_id=spec_id,
                    tag=tag,
                )
            return removed

    async def list_tags_for(
        self, *, article_id: UUID, spec_id: str
    ) -> list[ImageAssetTag]:
        """Return every tag attached to one (article_id, spec_id)."""
        async with self._sf() as db:
            stmt = select(ImageAssetTagRow).where(
                ImageAssetTagRow.article_id == article_id,
                ImageAssetTagRow.spec_id == spec_id,
            )
            rows = (await db.execute(stmt)).scalars().all()
            return [self._to_model(r) for r in rows]

    async def list_by_tag(self, *, tag: str) -> list[ImageAssetTag]:
        """Return every (article_id, spec_id) tagged with `tag`."""
        async with self._sf() as db:
            stmt = (
                select(ImageAssetTagRow)
                .where(ImageAssetTagRow.tag == tag)
                .order_by(ImageAssetTagRow.created_at.desc())
            )
            rows = (await db.execute(stmt)).scalars().all()
            return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(row: ImageAssetTagRow) -> ImageAssetTag:
        return ImageAssetTag(
            id=row.id,
            article_id=row.article_id,
            spec_id=row.spec_id,
            tag=row.tag,
            note=row.note,
            created_at=row.created_at,
        )
