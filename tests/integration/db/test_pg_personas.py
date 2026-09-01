"""Real-PostgreSQL round trip for PgPersonaRepository (AUTHOR-011)."""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import tables  # noqa: F401
from src.db.base import Base
from src.db.engine import get_session_factory
from src.db.persona_repository import PgPersonaRepository
from src.models.persona import DimStat, PersonaCreate, SampleCreate, VoiceFingerprint

_DB_URL = "postgresql+asyncpg://cognify:cognify@localhost:5432/cognify"


@pytest_asyncio.fixture
async def sf() -> async_sessionmaker[AsyncSession]:  # type: ignore[misc]
    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = get_session_factory(engine)
    yield factory  # type: ignore[misc]
    async with factory() as db:
        # persona_samples cascade on delete
        await db.execute(text("DELETE FROM personas WHERE owner_id = 'it-user'"))
        await db.commit()
    await engine.dispose()


def _fp() -> VoiceFingerprint:
    return VoiceFingerprint(
        dims={"ttr": DimStat(mean=0.5, stddev=0.1, confidence=0.7)}, sample_count=2
    )


@pytest.mark.integration
async def test_persona_round_trip(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = PgPersonaRepository(sf)
    persona = await repo.create("it-user", PersonaCreate(name="Ada", description="d"))

    s1 = await repo.add_sample(persona.id, SampleCreate(text="one two three"))
    s2 = await repo.add_sample(persona.id, SampleCreate(text="four five six seven"))
    assert s1.word_count == 3 and s2.word_count == 4

    await repo.set_sample_embedding(s1.id, [0.1, 0.2, 0.3])
    with_fp = await repo.set_fingerprint(persona.id, _fp())
    assert with_fp is not None
    assert with_fp.fingerprint == _fp()
    assert with_fp.sample_count == 2

    samples = await repo.list_samples(persona.id)
    by_id = {s.id: s for s in samples}
    assert by_id[s1.id].embedding == [0.1, 0.2, 0.3]
    assert by_id[s2.id].embedding is None

    assert await repo.delete(persona.id) is True
    assert await repo.list_samples(persona.id) == []
