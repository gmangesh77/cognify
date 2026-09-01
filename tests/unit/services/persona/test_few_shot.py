"""AUTHOR-011 — few-shot sample selection by cosine, cold fallback."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.models.persona import PersonaSample
from src.services.persona.few_shot import EXCERPT_WORDS, excerpt, pick_samples

_PID = uuid4()


def _sample(text: str, embedding: list[float] | None = None) -> PersonaSample:
    return PersonaSample(
        persona_id=_PID,
        text=text,
        word_count=len(text.split()),
        embedding=embedding,
        created_at=datetime.now(UTC),
    )


def _embed_axis(texts: list[str]) -> list[list[float]]:
    # deterministic: "kube" → x axis, "market" → y axis
    return [[1.0, 0.0] if "kube" in t else [0.0, 1.0] for t in texts]


class TestPickSamples:
    def test_picks_by_cosine_and_embeds_missing(self) -> None:
        s_kube = _sample("kube pods and nodes " * 5)
        s_mkt = _sample("market campaign funnel " * 5, embedding=[0.0, 1.0])
        result = pick_samples("kube networking", [s_mkt, s_kube], _embed_axis, k=1)
        assert [s.id for s in result.chosen] == [s_kube.id]
        assert set(result.new_embeddings) == {s_kube.id}

    def test_cold_model_falls_back_to_longest(self) -> None:
        short = _sample("a b c")
        long_ = _sample("w " * 50)
        result = pick_samples("anything", [short, long_], lambda _t: None, k=1)
        assert [s.id for s in result.chosen] == [long_.id]
        assert result.new_embeddings == {}

    def test_k_bounds_result(self) -> None:
        samples = [_sample(f"kube {i} " * 5) for i in range(5)]
        assert len(pick_samples("kube", samples, _embed_axis, k=3).chosen) == 3


class TestExcerpt:
    def test_trims_at_sentence_boundary(self) -> None:
        text = " ".join(f"Sentence number {i} here." for i in range(60))
        out = excerpt(text)
        assert len(out.split()) <= EXCERPT_WORDS
        assert out.endswith(".")

    def test_short_text_unchanged(self) -> None:
        assert excerpt("Short one. Two.") == "Short one. Two."
