"""Resolve a session's voice persona into pipeline run state (spec §4.5, §5).

`ContentService._voice_state` builds the `VoiceContextInput` and calls
`build_voice_state`, which is then merged into the initial graph state
(`state.update(...)`) so the drafter's system prompt and the score/fix
nodes (Task 8) all read the same `voice_fingerprint` / `voice_block` /
`few_shot_sample_ids` keys. Never raises — a broken persona lookup must
never fail a pipeline run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.services.persona.few_shot import FEW_SHOT_K, EmbedFn, pick_samples
from src.services.persona.prompt_block import build_voice_block

if TYPE_CHECKING:
    from src.db.persona_repository import PersonaRepository

logger = structlog.get_logger()


@dataclass(frozen=True)
class VoiceContextInput:
    """Selection input for `build_voice_state` (spec §5 — inline > brief > none)."""

    voice_persona_id: UUID | None
    query: str


def _no_embed(_texts: list[str]) -> list[list[float]] | None:
    return None


async def build_voice_state(
    repo: PersonaRepository | None,
    embed: EmbedFn | None,
    ctx: VoiceContextInput,
) -> dict[str, object]:
    """Resolve `ctx.voice_persona_id` into voice state, or `{}` when degraded.

    Degraded cases (all return `{}`): no persona selected, no repo, the
    persona doesn't exist, or it has no fingerprint yet. A repo/embedding
    failure logs `voice_context_failed` and also returns `{}`.
    """
    if repo is None or ctx.voice_persona_id is None:
        return {}
    try:
        return await _resolve(repo, embed or _no_embed, ctx)
    except Exception as exc:  # noqa: BLE001 — voice lookup must never fail a run
        logger.warning(
            "voice_context_failed",
            persona_id=str(ctx.voice_persona_id),
            error=str(exc),
        )
        return {}


async def _resolve(
    repo: PersonaRepository, embed: EmbedFn, ctx: VoiceContextInput
) -> dict[str, object]:
    assert ctx.voice_persona_id is not None  # noqa: S101 — checked by the caller
    persona = await repo.get(ctx.voice_persona_id)
    if persona is None or persona.fingerprint is None:
        return {}
    samples = await repo.list_samples(ctx.voice_persona_id)
    picked = pick_samples(ctx.query, samples, embed, k=FEW_SHOT_K)
    for sample_id, vec in picked.new_embeddings.items():
        await repo.set_sample_embedding(sample_id, vec)
    block = build_voice_block(persona.fingerprint, picked.chosen)
    return {
        "voice_fingerprint": persona.fingerprint,
        "voice_block": block,
        "few_shot_sample_ids": [s.id for s in picked.chosen],
    }


__all__ = ["VoiceContextInput", "build_voice_state"]
