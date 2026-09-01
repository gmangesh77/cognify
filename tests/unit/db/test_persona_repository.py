"""AUTHOR-011 — persona repository contract (in-memory twin)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.db.persona_repository import InMemoryPersonaRepository
from src.models.persona import (
    DimStat,
    PersonaCreate,
    PersonaUpdate,
    SampleCreate,
    VoiceFingerprint,
)


def _fp() -> VoiceFingerprint:
    return VoiceFingerprint(
        dims={"ttr": DimStat(mean=0.5, stddev=0.1, confidence=0.7)}, sample_count=5
    )


@pytest.mark.asyncio
class TestInMemoryPersonaRepository:
    async def test_crud_round_trip(self) -> None:
        repo = InMemoryPersonaRepository()
        p = await repo.create("user-1", PersonaCreate(name="Ada", description="d"))
        assert p.fingerprint is None and p.sample_count == 0
        assert (await repo.get(p.id)) == p
        assert [x.id for x in await repo.list()] == [p.id]
        updated = await repo.update(p.id, PersonaUpdate(name="Ada L."))
        assert updated is not None and updated.name == "Ada L."
        assert await repo.delete(p.id) is True
        assert await repo.get(p.id) is None and await repo.delete(p.id) is False

    async def test_samples_and_fingerprint(self) -> None:
        repo = InMemoryPersonaRepository()
        p = await repo.create("user-1", PersonaCreate(name="Ada"))
        s = await repo.add_sample(p.id, SampleCreate(text="one two three"))
        assert s.word_count == 3 and s.embedding is None
        assert [x.id for x in await repo.list_samples(p.id)] == [s.id]
        await repo.set_sample_embedding(s.id, [0.1, 0.2])
        assert (await repo.list_samples(p.id))[0].embedding == [0.1, 0.2]
        with_fp = await repo.set_fingerprint(p.id, _fp())
        assert with_fp is not None
        assert with_fp.fingerprint == _fp()
        assert with_fp.sample_count == 1
        assert await repo.delete_sample(p.id, s.id) is True
        assert await repo.list_samples(p.id) == []

    async def test_unknown_persona(self) -> None:
        repo = InMemoryPersonaRepository()
        assert await repo.update(uuid4(), PersonaUpdate(name="x")) is None
        assert await repo.set_fingerprint(uuid4(), _fp()) is None
