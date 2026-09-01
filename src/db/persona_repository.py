"""Repositories for personas + samples (AUTHOR-011)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.persona_repository_memory import InMemoryPersonaRepository  # noqa: F401
from src.db.tables_personas import PersonaRow, PersonaSampleRow
from src.models.persona import (
    Persona,
    PersonaCreate,
    PersonaSample,
    PersonaUpdate,
    SampleCreate,
    VoiceFingerprint,
)

logger = structlog.get_logger()


class PersonaRepository(Protocol):
    async def create(self, owner_id: str, data: PersonaCreate) -> Persona: ...
    async def get(self, persona_id: UUID) -> Persona | None: ...
    async def update(self, persona_id: UUID, data: PersonaUpdate) -> Persona | None: ...
    async def delete(self, persona_id: UUID) -> bool: ...
    async def add_sample(
        self, persona_id: UUID, data: SampleCreate
    ) -> PersonaSample: ...
    async def delete_sample(self, persona_id: UUID, sample_id: UUID) -> bool: ...
    async def list_samples(self, persona_id: UUID) -> list[PersonaSample]: ...
    async def set_fingerprint(
        self, persona_id: UUID, fp: VoiceFingerprint | None
    ) -> Persona | None: ...
    async def set_sample_embedding(self, sample_id: UUID, vec: list[float]) -> None: ...
    # Declared last: naming a method `list` shadows the builtin generic for
    # any `list[...]` annotation appearing after it in this class body.
    async def list(self) -> list[Persona]: ...


def _word_count(text: str) -> int:
    return len(text.split())


def row_to_persona(row: PersonaRow) -> Persona:
    fp = VoiceFingerprint.model_validate(row.fingerprint) if row.fingerprint else None
    return Persona(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        description=row.description,
        fingerprint=fp,
        sample_count=row.sample_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def row_to_sample(row: PersonaSampleRow) -> PersonaSample:
    return PersonaSample(
        id=row.id,
        persona_id=row.persona_id,
        text=row.text,
        word_count=row.word_count,
        embedding=list(row.embedding) if row.embedding else None,
        created_at=row.created_at,
    )


class PgPersonaRepository:
    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, owner_id: str, data: PersonaCreate) -> Persona:
        async with self._sf() as db:
            row = PersonaRow(owner_id=owner_id, **data.model_dump(mode="json"))
            db.add(row)
            await db.commit()
            await db.refresh(row)
            logger.info("persona_created", persona_id=str(row.id), owner_id=owner_id)
            return row_to_persona(row)

    async def get(self, persona_id: UUID) -> Persona | None:
        async with self._sf() as db:
            row = await db.get(PersonaRow, persona_id)
            return row_to_persona(row) if row else None

    async def update(self, persona_id: UUID, data: PersonaUpdate) -> Persona | None:
        async with self._sf() as db:
            row = await db.get(PersonaRow, persona_id)
            if row is None:
                return None
            for key, value in data.model_dump(exclude_none=True).items():
                setattr(row, key, value)
            await db.commit()
            await db.refresh(row)
            return row_to_persona(row)

    async def delete(self, persona_id: UUID) -> bool:
        async with self._sf() as db:
            result = await db.execute(
                delete(PersonaRow).where(PersonaRow.id == persona_id)
            )
            await db.commit()
            return bool(getattr(result, "rowcount", 0))

    async def add_sample(self, persona_id: UUID, data: SampleCreate) -> PersonaSample:
        async with self._sf() as db:
            row = PersonaSampleRow(
                persona_id=persona_id, text=data.text, word_count=_word_count(data.text)
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return row_to_sample(row)

    async def delete_sample(self, persona_id: UUID, sample_id: UUID) -> bool:
        async with self._sf() as db:
            stmt = delete(PersonaSampleRow).where(
                PersonaSampleRow.id == sample_id,
                PersonaSampleRow.persona_id == persona_id,
            )
            result = await db.execute(stmt)
            await db.commit()
            return bool(getattr(result, "rowcount", 0))

    async def list_samples(self, persona_id: UUID) -> list[PersonaSample]:
        async with self._sf() as db:
            stmt = (
                select(PersonaSampleRow)
                .where(PersonaSampleRow.persona_id == persona_id)
                .order_by(PersonaSampleRow.created_at)
            )
            rows = (await db.execute(stmt)).scalars().all()
            return [row_to_sample(r) for r in rows]

    async def set_fingerprint(
        self, persona_id: UUID, fp: VoiceFingerprint | None
    ) -> Persona | None:
        async with self._sf() as db:
            row = await db.get(PersonaRow, persona_id)
            if row is None:
                return None
            row.fingerprint = fp.model_dump(mode="json") if fp else None
            count_stmt = (
                select(func.count())
                .select_from(PersonaSampleRow)
                .where(PersonaSampleRow.persona_id == persona_id)
            )
            row.sample_count = (await db.execute(count_stmt)).scalar_one()
            await db.commit()
            await db.refresh(row)
            return row_to_persona(row)

    async def set_sample_embedding(self, sample_id: UUID, vec: list[float]) -> None:
        async with self._sf() as db:
            row = await db.get(PersonaSampleRow, sample_id)
            if row is None:
                return
            row.embedding = list(vec)
            await db.commit()

    # Declared last: naming a method `list` shadows the builtin generic for
    # any `list[...]` annotation appearing after it in this class body.
    async def list(self) -> list[Persona]:
        async with self._sf() as db:
            stmt = select(PersonaRow).order_by(PersonaRow.updated_at.desc())
            rows = (await db.execute(stmt)).scalars().all()
            return [row_to_persona(r) for r in rows]
