"""PostgreSQL singleton repositories for LLM config, SEO defaults, and general config.

Covers: PgLlmConfigRepository, PgSeoDefaultsRepository, PgGeneralConfigRepository.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables import GeneralConfigRow, LlmConfigRow, SeoDefaultsRow
from src.models.settings import GeneralConfig, LlmConfig, SeoDefaults

logger = structlog.get_logger()


class PgLlmConfigRepository:
    """Singleton LLM config repository (get_or_create + update)."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def get_or_create(self) -> LlmConfig:
        async with self._sf() as db:
            result = await db.execute(select(LlmConfigRow).limit(1))
            row = result.scalar_one_or_none()
            if row is None:
                defaults = LlmConfig()
                row = LlmConfigRow(
                    primary_model=defaults.primary_model,
                    drafting_model=defaults.drafting_model,
                    image_generation=defaults.image_generation,
                )
                db.add(row)
                await db.commit()
                await db.refresh(row)
                logger.debug("llm_config_loaded", created_default=True)
            else:
                logger.debug("llm_config_loaded", created_default=False)
            return self._to_model(row)

    async def update(self, config: LlmConfig) -> LlmConfig:
        async with self._sf() as db:
            result = await db.execute(select(LlmConfigRow).limit(1))
            row = result.scalar_one_or_none()
            if row is None:
                row = LlmConfigRow(
                    primary_model=config.primary_model,
                    drafting_model=config.drafting_model,
                    image_generation=config.image_generation,
                )
                db.add(row)
            else:
                row.primary_model = config.primary_model
                row.drafting_model = config.drafting_model
                row.image_generation = config.image_generation
            await db.commit()
            await db.refresh(row)
            logger.debug("llm_config_updated")
            return self._to_model(row)

    @staticmethod
    def _to_model(row: LlmConfigRow) -> LlmConfig:
        return LlmConfig(
            primary_model=row.primary_model,
            drafting_model=row.drafting_model,
            image_generation=row.image_generation,
        )


class PgSeoDefaultsRepository:
    """Singleton SEO defaults repository (get_or_create + update)."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def get_or_create(self) -> SeoDefaults:
        async with self._sf() as db:
            result = await db.execute(select(SeoDefaultsRow).limit(1))
            row = result.scalar_one_or_none()
            if row is None:
                defaults = SeoDefaults()
                row = SeoDefaultsRow(
                    auto_meta_tags=defaults.auto_meta_tags,
                    keyword_optimization=defaults.keyword_optimization,
                    auto_cover_images=defaults.auto_cover_images,
                    include_citations=defaults.include_citations,
                    human_review_before_publish=defaults.human_review_before_publish,
                )
                db.add(row)
                await db.commit()
                await db.refresh(row)
                logger.debug("seo_defaults_loaded", created_default=True)
            else:
                logger.debug("seo_defaults_loaded", created_default=False)
            return self._to_model(row)

    async def update(self, config: SeoDefaults) -> SeoDefaults:
        async with self._sf() as db:
            result = await db.execute(select(SeoDefaultsRow).limit(1))
            row = result.scalar_one_or_none()
            if row is None:
                row = SeoDefaultsRow(
                    auto_meta_tags=config.auto_meta_tags,
                    keyword_optimization=config.keyword_optimization,
                    auto_cover_images=config.auto_cover_images,
                    include_citations=config.include_citations,
                    human_review_before_publish=config.human_review_before_publish,
                )
                db.add(row)
            else:
                row.auto_meta_tags = config.auto_meta_tags
                row.keyword_optimization = config.keyword_optimization
                row.auto_cover_images = config.auto_cover_images
                row.include_citations = config.include_citations
                row.human_review_before_publish = config.human_review_before_publish
            await db.commit()
            await db.refresh(row)
            logger.debug("seo_defaults_updated")
            return self._to_model(row)

    @staticmethod
    def _to_model(row: SeoDefaultsRow) -> SeoDefaults:
        return SeoDefaults(
            auto_meta_tags=row.auto_meta_tags,
            keyword_optimization=row.keyword_optimization,
            auto_cover_images=row.auto_cover_images,
            include_citations=row.include_citations,
            human_review_before_publish=row.human_review_before_publish,
        )


class PgGeneralConfigRepository:
    """Singleton general config repository (get_or_create + update)."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def get_or_create(self) -> GeneralConfig:
        async with self._sf() as db:
            result = await db.execute(select(GeneralConfigRow).limit(1))
            row = result.scalar_one_or_none()
            if row is None:
                defaults = GeneralConfig()
                row = GeneralConfigRow(
                    article_length_target=defaults.article_length_target,
                    content_tone=defaults.content_tone,
                )
                db.add(row)
                await db.commit()
                await db.refresh(row)
                logger.debug("general_config_loaded", created_default=True)
            else:
                logger.debug("general_config_loaded", created_default=False)
            return self._to_model(row)

    async def update(self, config: GeneralConfig) -> GeneralConfig:
        async with self._sf() as db:
            result = await db.execute(select(GeneralConfigRow).limit(1))
            row = result.scalar_one_or_none()
            if row is None:
                row = GeneralConfigRow(
                    article_length_target=config.article_length_target,
                    content_tone=config.content_tone,
                )
                db.add(row)
            else:
                row.article_length_target = config.article_length_target
                row.content_tone = config.content_tone
            await db.commit()
            await db.refresh(row)
            logger.debug("general_config_updated")
            return self._to_model(row)

    @staticmethod
    def _to_model(row: GeneralConfigRow) -> GeneralConfig:
        return GeneralConfig(
            article_length_target=row.article_length_target,
            content_tone=row.content_tone,
        )
