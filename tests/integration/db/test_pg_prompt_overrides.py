"""Real-PostgreSQL round trip for PgPromptOverrideRepository (AUTHOR-012)."""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import tables  # noqa: F401
from src.db.base import Base
from src.db.engine import get_session_factory
from src.db.prompt_override_repository import PgPromptOverrideRepository

_DB_URL = "postgresql+asyncpg://cognify:cognify@localhost:5432/cognify"


@pytest_asyncio.fixture
async def sf() -> async_sessionmaker[AsyncSession]:  # type: ignore[misc]
    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = get_session_factory(engine)
    yield factory  # type: ignore[misc]
    async with factory() as db:
        await db.execute(text("DELETE FROM prompt_overrides WHERE key LIKE 'it.%'"))
        await db.commit()
    await engine.dispose()


@pytest.mark.integration
async def test_prompt_override_round_trip(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = PgPromptOverrideRepository(sf)
    await repo.upsert("it.system", template="A", updated_by="it-user")
    await repo.upsert("it.system", template="B", updated_by="it-user-2")
    assert (await repo.load_all()).get("it.system") == "B"
    got = await repo.get("it.system")
    assert got is not None and got.updated_by == "it-user-2"
    assert await repo.delete("it.system") is True
    assert await repo.delete("it.system") is False
