"""PersonaService — wraps the repo with fingerprint recompute, sample
embedding, and DTO mapping so router handlers stay under 20 lines
(AUTHOR-011, spec §6)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from src.api.schemas.personas import PersonaDetail, PersonaSummary, SampleView
from src.db.persona_repository import PersonaRepository
from src.models.persona import (
    Persona,
    PersonaCreate,
    PersonaSample,
    PersonaUpdate,
    SampleCreate,
    VoiceScore,
)
from src.services.persona.fingerprint import (
    MIN_SAMPLE_WORDS,
    InsufficientSamples,
    build_fingerprint,
)
from src.services.persona.scoring import score_text

EmbedFn = Callable[[list[str]], list[list[float]] | None]
PREVIEW_CHARS = 300


class SampleTooShort(ValueError):
    """Sample text is below `MIN_SAMPLE_WORDS`; carries the observed count."""

    def __init__(self, word_count: int) -> None:
        self.word_count = word_count
        super().__init__(
            f"sample needs at least {MIN_SAMPLE_WORDS} words (has {word_count})"
        )


class PersonaNotReady(ValueError):
    """Persona has no fingerprint yet (fewer than MIN_SAMPLES valid samples)."""

    def __init__(self) -> None:
        super().__init__("persona has no fingerprint yet")


def _summary(persona: Persona) -> PersonaSummary:
    return PersonaSummary(
        id=persona.id,
        name=persona.name,
        description=persona.description,
        sample_count=persona.sample_count,
        ready=persona.fingerprint is not None,
        updated_at=persona.updated_at,
    )


def _sample_view(sample: PersonaSample) -> SampleView:
    return SampleView(
        id=sample.id,
        word_count=sample.word_count,
        preview=sample.text[:PREVIEW_CHARS],
        created_at=sample.created_at,
    )


def _detail(persona: Persona, samples: list[PersonaSample]) -> PersonaDetail:
    return PersonaDetail(
        **_summary(persona).model_dump(),
        fingerprint=persona.fingerprint,
        samples=[_sample_view(s) for s in samples],
    )


class PersonaService:
    """Repo + fingerprint recompute + lazy sample embedding."""

    def __init__(self, repo: PersonaRepository, embed: EmbedFn | None = None) -> None:
        self._repo = repo
        self._embed = embed

    async def list_summaries(self) -> list[PersonaSummary]:
        return [_summary(p) for p in await self._repo.list()]

    async def create(self, owner_id: str, data: PersonaCreate) -> PersonaSummary:
        return _summary(await self._repo.create(owner_id, data))

    async def get_detail(self, persona_id: UUID) -> PersonaDetail | None:
        persona = await self._repo.get(persona_id)
        if persona is None:
            return None
        samples = await self._repo.list_samples(persona_id)
        return _detail(persona, samples)

    async def update(
        self, persona_id: UUID, data: PersonaUpdate
    ) -> PersonaSummary | None:
        persona = await self._repo.update(persona_id, data)
        return _summary(persona) if persona else None

    async def delete(self, persona_id: UUID) -> bool:
        return await self._repo.delete(persona_id)

    async def add_sample(
        self, persona_id: UUID, data: SampleCreate
    ) -> PersonaDetail | None:
        if await self._repo.get(persona_id) is None:
            return None
        word_count = len(data.text.split())
        if word_count < MIN_SAMPLE_WORDS:
            raise SampleTooShort(word_count)
        sample = await self._repo.add_sample(persona_id, data)
        await self._maybe_embed(sample)
        await self._recompute(persona_id)
        return await self.get_detail(persona_id)

    async def delete_sample(
        self, persona_id: UUID, sample_id: UUID
    ) -> PersonaDetail | None:
        if await self._repo.get(persona_id) is None:
            return None
        if not await self._repo.delete_sample(persona_id, sample_id):
            return None
        await self._recompute(persona_id)
        return await self.get_detail(persona_id)

    async def score(self, persona_id: UUID, text: str) -> VoiceScore | None:
        persona = await self._repo.get(persona_id)
        if persona is None:
            return None
        if persona.fingerprint is None:
            raise PersonaNotReady()
        return score_text(text, persona.fingerprint)

    async def _recompute(self, persona_id: UUID) -> None:
        samples = await self._repo.list_samples(persona_id)
        try:
            fp = build_fingerprint([s.text for s in samples])
        except InsufficientSamples:
            fp = None
        await self._repo.set_fingerprint(persona_id, fp)

    async def _maybe_embed(self, sample: PersonaSample) -> None:
        if self._embed is None:
            return
        vectors = self._embed([sample.text])
        if vectors:
            await self._repo.set_sample_embedding(sample.id, vectors[0])
