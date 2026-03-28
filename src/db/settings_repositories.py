"""PostgreSQL repository implementations for settings entities.

Split into two modules:
- settings_repositories.py — domain config and API key repos (CRUD)
- settings_singleton_repositories.py — LLM, SEO, General repos (singleton)
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables import ApiKeyRow, DomainConfigRow
from src.models.settings import ApiKeyConfig, DomainConfig

logger = structlog.get_logger()


class PgDomainConfigRepository:
    """CRUD repository for domain configurations."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, domain: DomainConfig) -> DomainConfig:
        async with self._sf() as db:
            row = DomainConfigRow(
                id=domain.id,
                name=domain.name,
                status=domain.status,
                trend_sources=domain.trend_sources,
                keywords=domain.keywords,
                article_count=domain.article_count,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            domain_model = self._to_model(row)
            logger.debug(
                "domain_config_created",
                domain_id=str(domain_model.id),
                name=domain_model.name,
            )
            return domain_model

    async def get(self, domain_id: UUID) -> DomainConfig | None:
        async with self._sf() as db:
            row = await db.get(DomainConfigRow, domain_id)
            return self._to_model(row) if row else None

    async def update(self, domain: DomainConfig) -> DomainConfig:
        async with self._sf() as db:
            row = await db.get(DomainConfigRow, domain.id)
            if row is None:
                logger.warning("domain_config_not_found", domain_id=str(domain.id))
                raise ValueError(f"DomainConfig {domain.id} not found")
            row.name = domain.name
            row.status = domain.status
            row.trend_sources = domain.trend_sources
            row.keywords = domain.keywords
            row.article_count = domain.article_count
            await db.commit()
            await db.refresh(row)
            updated_domain = self._to_model(row)
            logger.debug("domain_config_updated", domain_id=str(updated_domain.id))
            return updated_domain

    async def delete(self, domain_id: UUID) -> None:
        async with self._sf() as db:
            row = await db.get(DomainConfigRow, domain_id)
            if row is not None:
                await db.delete(row)
                await db.commit()
                logger.debug("domain_config_deleted", domain_id=str(domain_id))

    async def list_all(self) -> list[DomainConfig]:
        async with self._sf() as db:
            result = await db.execute(select(DomainConfigRow))
            items = [self._to_model(r) for r in result.scalars().all()]
            logger.debug("domain_configs_listed", count=len(items))
            return items

    @staticmethod
    def _to_model(row: DomainConfigRow) -> DomainConfig:
        return DomainConfig(
            id=row.id,
            name=row.name,
            status=row.status,
            trend_sources=row.trend_sources or [],
            keywords=row.keywords or [],
            article_count=row.article_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class PgApiKeyRepository:
    """CRUD repository for API key configurations."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, key: ApiKeyConfig, encrypted_key: str) -> ApiKeyConfig:
        async with self._sf() as db:
            row = ApiKeyRow(
                id=key.id,
                service=key.service,
                encrypted_key=encrypted_key,
                masked_key=key.masked_key,
                status=key.status,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            key_model = self._to_model(row)
            logger.debug(
                "api_key_created",
                key_id=str(key_model.id),
                service=key_model.service,
            )
            return key_model

    async def get(self, key_id: UUID) -> ApiKeyConfig | None:
        async with self._sf() as db:
            row = await db.get(ApiKeyRow, key_id)
            return self._to_model(row) if row else None

    async def rotate(
        self,
        key_id: UUID,
        encrypted_key: str,
        masked_key: str,
    ) -> ApiKeyConfig:
        async with self._sf() as db:
            row = await db.get(ApiKeyRow, key_id)
            if row is None:
                logger.warning("api_key_not_found", key_id=str(key_id))
                raise ValueError(f"ApiKey {key_id} not found")
            row.encrypted_key = encrypted_key
            row.masked_key = masked_key
            await db.commit()
            await db.refresh(row)
            logger.debug("api_key_rotated", key_id=str(key_id))
            return self._to_model(row)

    async def delete(self, key_id: UUID) -> None:
        async with self._sf() as db:
            row = await db.get(ApiKeyRow, key_id)
            if row is not None:
                await db.delete(row)
                await db.commit()
                logger.debug("api_key_deleted", key_id=str(key_id))

    async def list_all(self) -> list[ApiKeyConfig]:
        async with self._sf() as db:
            result = await db.execute(select(ApiKeyRow))
            items = [self._to_model(r) for r in result.scalars().all()]
            logger.debug("api_keys_listed", count=len(items))
            return items

    async def get_encrypted_key_by_service(self, service: str) -> str | None:
        """Return the encrypted key for an active service, or None."""
        async with self._sf() as db:
            stmt = (
                select(ApiKeyRow.encrypted_key)
                .where(ApiKeyRow.service == service, ApiKeyRow.status == "active")
                .order_by(ApiKeyRow.created_at.desc())
                .limit(1)
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    def _to_model(row: ApiKeyRow) -> ApiKeyConfig:
        return ApiKeyConfig(
            id=row.id,
            service=row.service,
            masked_key=row.masked_key,
            status=row.status,
            created_at=row.created_at,
        )
