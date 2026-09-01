"""AUTHOR-011 Task 9 — resolve a session's voice persona into run state."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import structlog.testing

from src.db.persona_repository_memory import InMemoryPersonaRepository
from src.models.persona import PersonaCreate, SampleCreate, VoiceFingerprint
from src.services.persona.fingerprint import DIM_LABELS, build_fingerprint
from src.services.persona.voice_context import VoiceContextInput, build_voice_state

_QUERY = "Kubernetes Networking\nHow pods talk to each other."


def _long_sample(seed: int) -> str:
    """~160 words of varied prose so `build_fingerprint` accepts it."""
    base = (
        f"Sample {seed} explores how distributed systems behave under load, "
        "and it walks through the tradeoffs engineers face daily. "
        "Sometimes the answer is obvious; often it is not, and that is "
        "exactly where careful reasoning earns its keep. "
        "We look at retries, backoff, and the quiet cost of coupling "
        "services too tightly to one another. "
        "A good design tolerates failure gracefully instead of pretending "
        "it will never happen. "
        "Consider a queue that backs up during a spike, or a cache that "
        "goes cold at the worst possible moment. "
        "These are not edge cases; they are Tuesday. "
        "Plan for them, measure them, and revisit the plan once real "
        "traffic proves the assumptions wrong. "
    )
    return (base * 2).strip()


async def _ready_persona(repo: InMemoryPersonaRepository) -> UUID:
    persona = await repo.create("owner-1", PersonaCreate(name="Voice"))
    for i in range(5):
        await repo.add_sample(persona.id, SampleCreate(text=_long_sample(i)))
    samples = await repo.list_samples(persona.id)
    fp = build_fingerprint([s.text for s in samples])
    await repo.set_fingerprint(persona.id, fp)
    return persona.id


def _no_embed(_texts: list[str]) -> list[list[float]] | None:
    return None


class TestDegradedCases:
    @pytest.mark.asyncio
    async def test_no_persona_id_returns_empty(self) -> None:
        repo = InMemoryPersonaRepository()
        ctx = VoiceContextInput(voice_persona_id=None, query=_QUERY)
        assert await build_voice_state(repo, _no_embed, ctx) == {}

    @pytest.mark.asyncio
    async def test_no_repo_returns_empty(self) -> None:
        ctx = VoiceContextInput(voice_persona_id=uuid4(), query=_QUERY)
        assert await build_voice_state(None, _no_embed, ctx) == {}

    @pytest.mark.asyncio
    async def test_persona_missing_returns_empty(self) -> None:
        repo = InMemoryPersonaRepository()
        ctx = VoiceContextInput(voice_persona_id=uuid4(), query=_QUERY)
        assert await build_voice_state(repo, _no_embed, ctx) == {}

    @pytest.mark.asyncio
    async def test_persona_without_fingerprint_returns_empty(self) -> None:
        repo = InMemoryPersonaRepository()
        persona = await repo.create("owner-1", PersonaCreate(name="No FP"))
        ctx = VoiceContextInput(voice_persona_id=persona.id, query=_QUERY)
        assert await build_voice_state(repo, _no_embed, ctx) == {}

    @pytest.mark.asyncio
    async def test_repo_raising_returns_empty_and_logs(self) -> None:
        class _BoomRepo:
            async def get(self, persona_id: UUID) -> None:
                raise RuntimeError("db down")

        persona_id = uuid4()
        ctx = VoiceContextInput(voice_persona_id=persona_id, query=_QUERY)
        with structlog.testing.capture_logs() as logs:
            result = await build_voice_state(_BoomRepo(), _no_embed, ctx)  # type: ignore[arg-type]
        assert result == {}
        failures = [log for log in logs if log["event"] == "voice_context_failed"]
        assert len(failures) == 1
        assert failures[0]["persona_id"] == str(persona_id)

    @pytest.mark.asyncio
    async def test_embed_none_falls_back_to_cold_path(self) -> None:
        """`embed=None` (no EmbeddingService configured) must not raise."""
        repo = InMemoryPersonaRepository()
        persona_id = await _ready_persona(repo)
        ctx = VoiceContextInput(voice_persona_id=persona_id, query=_QUERY)
        result = await build_voice_state(repo, None, ctx)
        assert isinstance(result["voice_fingerprint"], VoiceFingerprint)
        assert result["voice_block"]
        assert len(result["few_shot_sample_ids"]) > 0  # type: ignore[arg-type]


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_returns_typed_state_and_persists_new_embeddings(self) -> None:
        repo = InMemoryPersonaRepository()
        persona_id = await _ready_persona(repo)
        embedded_calls: list[list[str]] = []

        def _embed(texts: list[str]) -> list[list[float]] | None:
            embedded_calls.append(texts)
            return [[float(i), 0.0] for i in range(len(texts))]

        ctx = VoiceContextInput(voice_persona_id=persona_id, query=_QUERY)
        result = await build_voice_state(repo, _embed, ctx)

        fp = result["voice_fingerprint"]
        assert isinstance(fp, VoiceFingerprint)
        block = result["voice_block"]
        assert isinstance(block, str) and "Voice" in block
        sample_ids = result["few_shot_sample_ids"]
        assert isinstance(sample_ids, list)
        assert all(isinstance(i, UUID) for i in sample_ids)

        # every sample lacked an embedding, so `pick_samples` embedded and
        # persisted them all.
        samples = await repo.list_samples(persona_id)
        assert all(s.embedding is not None for s in samples)
        assert embedded_calls  # embed was actually invoked, not just skipped

    @pytest.mark.asyncio
    async def test_block_contains_a_confident_dimension_label(self) -> None:
        repo = InMemoryPersonaRepository()
        persona_id = await _ready_persona(repo)

        def _embed(texts: list[str]) -> list[list[float]] | None:
            return [[1.0, 0.0] for _ in texts]

        ctx = VoiceContextInput(voice_persona_id=persona_id, query=_QUERY)
        result = await build_voice_state(repo, _embed, ctx)
        block = result["voice_block"]
        assert isinstance(block, str)
        persona = await repo.get(persona_id)
        assert persona is not None and persona.fingerprint is not None
        confident_dims = [
            d for d, s in persona.fingerprint.dims.items() if s.confidence >= 0.5
        ]
        assert confident_dims, "fixture fingerprint should have >=1 confident dim"
        assert any(DIM_LABELS.get(d, d) in block for d in confident_dims)
