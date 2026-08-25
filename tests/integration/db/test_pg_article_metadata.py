"""Real-PostgreSQL round trip for PgArticleRepository.update_metadata
(AUTHOR-006).

Requires the docker-compose postgres. Cleans up its own rows (L-005).
Covers the L-001-sensitive seo JSONB reassignment plus the
subtitle-to-None branch that only the PG impl exercises.
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import tables  # noqa: F401
from src.db.base import Base
from src.db.engine import get_session_factory
from src.db.repositories import PgArticleRepository
from tests.unit.api.test_content_endpoints import _build_article

_DB_URL = "postgresql+asyncpg://cognify:cognify@localhost:5432/cognify"

_ARTICLE_ID = uuid4()


@pytest_asyncio.fixture
async def sf() -> async_sessionmaker[AsyncSession]:  # type: ignore[misc]
    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = get_session_factory(engine)
    yield factory  # type: ignore[misc]
    async with factory() as db:
        await db.execute(
            text("DELETE FROM canonical_articles WHERE id = :id"),
            {"id": _ARTICLE_ID},
        )
        await db.commit()
    await engine.dispose()


@pytest.mark.integration
async def test_update_metadata_round_trip(
    sf: async_sessionmaker[AsyncSession],
) -> None:
    repo = PgArticleRepository(sf)
    article = _build_article(_ARTICLE_ID).model_copy(update={"subtitle": "Sub"})
    await repo.create(article)

    new_seo = article.seo.model_copy(
        update={"title": "PG round-trip SEO title", "keywords": ["pg", "it"]}
    )
    updated = await repo.update_metadata(
        _ARTICLE_ID,
        {"title": "PG round-trip title", "subtitle": None, "seo": new_seo},
    )
    assert updated is not None
    assert updated.title == "PG round-trip title"
    assert updated.subtitle is None
    assert updated.seo.title == "PG round-trip SEO title"
    assert updated.seo.keywords == ["pg", "it"]

    fresh = await repo.get(_ARTICLE_ID)
    assert fresh is not None
    assert fresh.title == "PG round-trip title"
    assert fresh.subtitle is None
    assert fresh.seo.keywords == ["pg", "it"]
    # untouched fields survive the partial update
    assert fresh.body_markdown == article.body_markdown

    assert await repo.update_metadata(uuid4(), {"title": "x"}) is None


@pytest.mark.integration
async def test_status_round_trip(sf: async_sessionmaker[AsyncSession]) -> None:
    from src.models.content import ArticleStatus

    repo = PgArticleRepository(sf)
    sid = uuid4()
    article = _build_article(sid)
    try:
        created = await repo.create(article)
        assert created.status is ArticleStatus.DRAFT
        updated = await repo.update_metadata(sid, {"status": ArticleStatus.IN_REVIEW})
        assert updated is not None and updated.status is ArticleStatus.IN_REVIEW
        in_review, total = await repo.list(status="in_review")
        assert sid in [a.id for a in in_review]
        drafts, _ = await repo.list(status="draft")
        assert sid not in [a.id for a in drafts]
    finally:
        async with sf() as db:
            await db.execute(
                text("DELETE FROM canonical_articles WHERE id = :id"), {"id": sid}
            )
            await db.commit()
