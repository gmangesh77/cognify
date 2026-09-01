"""Few-shot sample selection — in-process cosine (spec §4.3)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

import numpy as np

from src.models.persona import PersonaSample

FEW_SHOT_K = 3
EXCERPT_WORDS = 120
EmbedFn = Callable[[list[str]], list[list[float]] | None]
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class PickResult:
    chosen: list[PersonaSample]
    new_embeddings: dict[UUID, list[float]] = field(default_factory=dict)


def excerpt(text: str, max_words: int = EXCERPT_WORDS) -> str:
    """First sentences of `text` up to `max_words`, never mid-sentence."""
    out: list[str] = []
    count = 0
    for sentence in _SENTENCE_RE.split(text.strip()):
        words = len(sentence.split())
        if out and count + words > max_words:
            break
        out.append(sentence)
        count += words
    return " ".join(out)


def _longest(samples: list[PersonaSample], k: int) -> PickResult:
    ordered = sorted(samples, key=lambda s: s.word_count, reverse=True)
    return PickResult(chosen=ordered[:k])


def _ensure_embeddings(
    samples: list[PersonaSample], embed: EmbedFn
) -> tuple[dict[UUID, list[float]], dict[UUID, list[float]]] | None:
    missing = [s for s in samples if s.embedding is None]
    fresh = embed([s.text for s in missing]) if missing else []
    if fresh is None:
        return None
    new = {s.id: vec for s, vec in zip(missing, fresh, strict=True)}
    known = {s.id: s.embedding for s in samples if s.embedding is not None}
    return {**known, **new}, new


def pick_samples(
    query: str, samples: list[PersonaSample], embed: EmbedFn, *, k: int = FEW_SHOT_K
) -> PickResult:
    """Top-`k` samples by cosine to `query`; longest-`k` when the model is cold."""
    if not samples:
        return PickResult(chosen=[])
    query_vec = embed([query])
    ensured = _ensure_embeddings(samples, embed)
    if query_vec is None or ensured is None:
        return _longest(samples, k)
    vectors, new = ensured
    q = np.array(query_vec[0])
    scored = sorted(samples, key=lambda s: -float(np.dot(q, np.array(vectors[s.id]))))
    return PickResult(chosen=scored[:k], new_embeddings=new)
