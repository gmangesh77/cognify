"""AUTHOR-011 — stdlib stylometric fingerprint."""

from __future__ import annotations

import pytest

from src.services.persona.fingerprint import (
    CONFIDENCE_FULL_N,
    DIMENSIONS,
    MIN_SAMPLES,
    InsufficientSamples,
    build_fingerprint,
    text_features,
)

SHORT = "We ship small. It works. Teams win."  # 3 sentences, 7 words
LONG_SENTENCES = (
    "When a platform team decides to rebuild its deployment pipeline from scratch "
    "without first measuring where the current one actually loses time, the result "
    "is usually a beautiful system that solves yesterday's problem. "
    "Measurement before architecture is not glamorous, but it is the only way to "
    "know whether the rebuild was worth the quarter it consumed."
)


def _sample(seed: int, words: int = 160) -> str:
    base = [
        "I think the honest answer is that we don't know yet.",
        "Small steps compound; big rewrites stall.",
        "Perhaps the team could try it for a week?",
        "Clearly the data supports a slower rollout.",
    ]
    out: list[str] = []
    i = seed
    while sum(len(s.split()) for s in out) < words:
        out.append(base[i % len(base)])
        i += 1
    return "\n\n".join(" ".join(out[j : j + 3]) for j in range(0, len(out), 3))


class TestTextFeatures:
    def test_returns_every_dimension(self) -> None:
        feats = text_features(SHORT)
        assert set(feats) == set(DIMENSIONS)

    def test_sentence_length_mean_and_std(self) -> None:
        feats = text_features(SHORT)
        assert feats["sentence_len_mean"] == pytest.approx(7 / 3, abs=0.01)
        assert feats["sentence_len_std"] > 0

    def test_longer_sentences_raise_fk_grade(self) -> None:
        assert (
            text_features(LONG_SENTENCES)["fk_grade"] > text_features(SHORT)["fk_grade"]
        )

    def test_contractions_hedges_boosters_first_person(self) -> None:
        feats = text_features("I don't think so. Perhaps we'll see. Clearly I'm right.")
        assert feats["contraction_rate"] > 0
        assert feats["hedge_rate"] > 0
        assert feats["booster_rate"] > 0
        assert feats["first_person_rate"] > 0

    def test_punctuation_per_1k_words(self) -> None:
        feats = text_features("One, two; three — four? Five.")
        assert feats["punct_comma_per_1k"] == pytest.approx(200.0)
        assert feats["punct_semicolon_per_1k"] == pytest.approx(200.0)
        assert feats["punct_dash_per_1k"] == pytest.approx(200.0)
        assert feats["punct_question_per_1k"] == pytest.approx(200.0)

    def test_markdown_structure_is_ignored(self) -> None:
        md = (
            "## Heading\n\n```python\nx = 1; y = 2; z = 3\n```\n\n"
            "Plain prose here. More prose."
        )
        feats = text_features(md)
        assert feats["punct_semicolon_per_1k"] == 0.0

    def test_empty_text_is_all_zero(self) -> None:
        assert all(v == 0.0 for v in text_features("").values())


class TestBuildFingerprint:
    def test_requires_min_samples_of_min_words(self) -> None:
        with pytest.raises(InsufficientSamples):
            build_fingerprint([_sample(i) for i in range(MIN_SAMPLES - 1)])
        with pytest.raises(InsufficientSamples):
            build_fingerprint([SHORT] * MIN_SAMPLES)

    def test_fingerprint_has_stats_per_dimension(self) -> None:
        fp = build_fingerprint([_sample(i) for i in range(MIN_SAMPLES)])
        assert fp.sample_count == MIN_SAMPLES
        assert set(fp.dims) == set(DIMENSIONS)
        stat = fp.dims["sentence_len_mean"]
        assert stat.mean > 0 and stat.stddev >= 0 and 0 <= stat.confidence <= 1

    def test_confidence_grows_with_sample_count(self) -> None:
        few = build_fingerprint([_sample(i) for i in range(MIN_SAMPLES)])
        many = build_fingerprint([_sample(i) for i in range(CONFIDENCE_FULL_N)])
        assert (
            many.dims["sentence_len_mean"].confidence
            > few.dims["sentence_len_mean"].confidence
        )

    def test_confidence_falls_with_spread(self) -> None:
        tight = build_fingerprint([_sample(0)] * MIN_SAMPLES)
        wild = build_fingerprint(
            [_sample(i) for i in range(MIN_SAMPLES - 1)] + [LONG_SENTENCES * 12]
        )
        assert (
            tight.dims["sentence_len_mean"].confidence
            >= wild.dims["sentence_len_mean"].confidence
        )
