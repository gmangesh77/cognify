"""AUTHOR-011 — z-score voice matching."""

from __future__ import annotations

from src.models.content_pipeline import SectionDraft
from src.models.persona import DimStat, VoiceFingerprint
from src.services.persona.fingerprint import DIMENSIONS, text_features
from src.services.persona.scoring import (
    MIN_CONFIDENCE,
    band_for,
    score_sections,
    score_text,
)

TEXT = "We ship small. It works. Teams win. Perhaps we'll try it again tomorrow."


def _fp(
    overrides: dict[str, DimStat] | None = None, confidence: float = 1.0
) -> VoiceFingerprint:
    feats = text_features(TEXT)
    dims = {
        name: DimStat(
            mean=feats[name],
            stddev=max(0.5, abs(feats[name]) * 0.2),
            confidence=confidence,
        )
        for name in DIMENSIONS
    }
    dims.update(overrides or {})
    return VoiceFingerprint(dims=dims, sample_count=8)


class TestScoreText:
    def test_text_matching_its_own_fingerprint_scores_100(self) -> None:
        result = score_text(TEXT, _fp())
        assert result.score == 100 and result.band == "match"
        assert result.deviations == []

    def test_far_off_dimension_lowers_score_and_names_deviation(self) -> None:
        fp = _fp({"sentence_len_mean": DimStat(mean=40.0, stddev=2.0, confidence=1.0)})
        result = score_text(TEXT, fp)
        assert result.score < 100
        dev = next(d for d in result.deviations if d.dim == "sentence_len_mean")
        assert "average sentence length" in dev.message and "40" in dev.message
        assert result.per_dim["sentence_len_mean"].z < -1.5

    def test_low_confidence_dimensions_are_ignored(self) -> None:
        fp = _fp(
            {
                "sentence_len_mean": DimStat(
                    mean=40.0, stddev=2.0, confidence=MIN_CONFIDENCE - 0.1
                )
            }
        )
        assert score_text(TEXT, fp).score == 100

    def test_penalty_is_capped_at_three_sigma(self) -> None:
        fp3 = _fp({"ttr": DimStat(mean=5.0, stddev=1.0, confidence=1.0)})
        fp9 = _fp({"ttr": DimStat(mean=50.0, stddev=1.0, confidence=1.0)})
        assert score_text(TEXT, fp3).score == score_text(TEXT, fp9).score

    def test_no_confident_dimensions_scores_100(self) -> None:
        assert score_text(TEXT, _fp(confidence=0.0)).score == 100


class TestBands:
    def test_bands(self) -> None:
        assert band_for(80) == "match" and band_for(79) == "close"
        assert band_for(60) == "close" and band_for(59) == "off_voice"


class TestScoreSections:
    def test_short_sections_excluded_from_article_mean(self) -> None:
        long_body = " ".join(["We ship small."] * 30)  # 90 words
        sections = [
            SectionDraft(
                section_index=0,
                title="a",
                body_markdown="Tiny.",
                word_count=1,
                citations_used=[],
            ),
            SectionDraft(
                section_index=1,
                title="b",
                body_markdown=long_body,
                word_count=90,
                citations_used=[],
            ),
        ]
        by_section, overall = score_sections(sections, _fp())
        assert set(by_section) == {"0", "1"}
        assert overall == by_section["1"]

    def test_all_short_gives_none(self) -> None:
        sections = [
            SectionDraft(
                section_index=0,
                title="a",
                body_markdown="Tiny.",
                word_count=1,
                citations_used=[],
            )
        ]
        assert score_sections(sections, _fp())[1] is None
