"""Real-PostgreSQL round trip for PgBriefRepository (AUTHOR-003).

Requires the docker-compose postgres. Cleans up its own rows (L-005).
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import tables  # noqa: F401
from src.db.base import Base
from src.db.brief_repository import PgBriefRepository
from src.db.engine import get_session_factory
from src.models.brief import BriefCreate, BriefUpdate

_DB_URL = "postgresql+asyncpg://cognify:cognify@localhost:5432/cognify"


@pytest_asyncio.fixture
async def sf() -> async_sessionmaker[AsyncSession]:  # type: ignore[misc]
    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = get_session_factory(engine)
    yield factory  # type: ignore[misc]
    async with factory() as db:
        await db.execute(text("DELETE FROM briefs WHERE owner_id = 'it-user'"))
        await db.commit()
    await engine.dispose()


@pytest.mark.integration
async def test_brief_crud_round_trip(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = PgBriefRepository(sf)
    created = await repo.create("it-user", BriefCreate(name="IT brief", keywords=["x"]))
    assert (await repo.get(created.id)) == created
    assert [b.id for b in await repo.list_by_owner("it-user")] == [created.id]
    updated = await repo.update(created.id, BriefUpdate(name="renamed"))
    assert updated is not None and updated.name == "renamed"
    assert await repo.delete(created.id) is True
    assert await repo.get(created.id) is None
