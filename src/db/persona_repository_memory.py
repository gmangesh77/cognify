"""In-memory `PersonaRepository` twin — unit tests + no-DB lifespan branch."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.models.persona import (
    Persona,
    PersonaCreate,
    PersonaSample,
    PersonaUpdate,
    SampleCreate,
    VoiceFingerprint,
)


def _word_count(text: str) -> int:
    return len(text.split())


class InMemoryPersonaRepository:
    def __init__(self) -> None:
        self._personas: dict[UUID, Persona] = {}
        self._samples: dict[UUID, PersonaSample] = {}

    async def create(self, owner_id: str, data: PersonaCreate) -> Persona:
        now = datetime.now(UTC)
        persona = Persona(
            id=uuid4(),
            owner_id=owner_id,
            name=data.name,
            description=data.description,
            fingerprint=None,
            sample_count=0,
            created_at=now,
            updated_at=now,
        )
        self._personas[persona.id] = persona
        return persona

    async def get(self, persona_id: UUID) -> Persona | None:
        return self._personas.get(persona_id)

    async def update(self, persona_id: UUID, data: PersonaUpdate) -> Persona | None:
        persona = self._personas.get(persona_id)
        if persona is None:
            return None
        updates: dict[str, object] = {
            **data.model_dump(exclude_none=True),
            "updated_at": datetime.now(UTC),
        }
        updated = persona.model_copy(update=updates)
        self._personas[persona_id] = updated
        return updated

    async def delete(self, persona_id: UUID) -> bool:
        if persona_id not in self._personas:
            return False
        del self._personas[persona_id]
        stale = [s.id for s in self._samples.values() if s.persona_id == persona_id]
        for sample_id in stale:
            del self._samples[sample_id]
        return True

    async def add_sample(self, persona_id: UUID, data: SampleCreate) -> PersonaSample:
        sample = PersonaSample(
            id=uuid4(),
            persona_id=persona_id,
            text=data.text,
            word_count=_word_count(data.text),
            embedding=None,
            created_at=datetime.now(UTC),
        )
        self._samples[sample.id] = sample
        return sample

    async def delete_sample(self, persona_id: UUID, sample_id: UUID) -> bool:
        sample = self._samples.get(sample_id)
        if sample is None or sample.persona_id != persona_id:
            return False
        del self._samples[sample_id]
        return True

    async def list_samples(self, persona_id: UUID) -> list[PersonaSample]:
        return [s for s in self._samples.values() if s.persona_id == persona_id]

    async def set_fingerprint(
        self, persona_id: UUID, fp: VoiceFingerprint | None
    ) -> Persona | None:
        persona = self._personas.get(persona_id)
        if persona is None:
            return None
        sample_count = len(await self.list_samples(persona_id))
        updated = persona.model_copy(
            update={
                "fingerprint": fp,
                "sample_count": sample_count,
                "updated_at": datetime.now(UTC),
            }
        )
        self._personas[persona_id] = updated
        return updated

    async def set_sample_embedding(self, sample_id: UUID, vec: list[float]) -> None:
        sample = self._samples.get(sample_id)
        if sample is None:
            return
        self._samples[sample_id] = sample.model_copy(update={"embedding": list(vec)})

    # Declared last: naming a method `list` shadows the builtin generic for
    # any `list[...]` annotation appearing after it in this class body.
    async def list(self) -> list[Persona]:
        return list(self._personas.values())
