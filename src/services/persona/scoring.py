"""Voice-match scoring (spec §4.2): confidence-weighted capped z-scores."""

from __future__ import annotations

from src.models.content_pipeline import SectionDraft
from src.models.persona import (
    DimScore,
    DimStat,
    VoiceBand,
    VoiceDeviation,
    VoiceFingerprint,
    VoiceScore,
)
from src.services.persona.fingerprint import DIM_LABELS, text_features

MIN_CONFIDENCE = 0.5
DEVIATION_Z = 1.5
SHORT_SECTION_WORDS = 60
_Z_CAP = 3.0


def band_for(score: int) -> VoiceBand:
    if score >= 80:
        return "match"
    if score >= 60:
        return "close"
    return "off_voice"


def _denominator(stat: DimStat) -> float:
    return max(stat.stddev, 0.1 * abs(stat.mean), 0.25)


def _message(dim: str, observed: float, stat: DimStat) -> str:
    label = DIM_LABELS.get(dim, dim)
    return f"{label} is {observed:.1f}; target {stat.mean:.1f} ± {stat.stddev:.1f}"


def _dim_score(
    dim: str, observed: float, stat: DimStat
) -> tuple[DimScore, VoiceDeviation | None]:
    z = (observed - stat.mean) / _denominator(stat)
    score = DimScore(value=observed, z=z, confidence=stat.confidence)
    if abs(z) <= DEVIATION_Z:
        return score, None
    msg = _message(dim, observed, stat)
    dev = VoiceDeviation(dim=dim, observed=observed, target=stat.mean, message=msg)
    return score, dev


def score_text(text: str, fp: VoiceFingerprint) -> VoiceScore:
    """0–100 match of `text` against `fp` over its confident dimensions."""
    feats = text_features(text)
    per_dim: dict[str, DimScore] = {}
    deviations: list[VoiceDeviation] = []
    weighted = total = 0.0
    for dim, stat in fp.dims.items():
        if stat.confidence < MIN_CONFIDENCE or dim not in feats:
            continue
        score, deviation = _dim_score(dim, feats[dim], stat)
        per_dim[dim] = score
        weighted += stat.confidence * min(abs(score.z), _Z_CAP) / _Z_CAP
        total += stat.confidence
        if deviation is not None:
            deviations.append(deviation)
    final = 100 if total == 0 else round(100 * (1 - weighted / total))
    deviations.sort(key=lambda d: -abs(per_dim[d.dim].z))
    return VoiceScore(
        score=final, band=band_for(final), per_dim=per_dim, deviations=deviations
    )


def score_sections(
    sections: list[SectionDraft], fp: VoiceFingerprint
) -> tuple[dict[str, int], int | None]:
    """Per-section scores + word-weighted mean over non-short sections."""
    by_section = {
        str(s.section_index): score_text(s.body_markdown, fp).score for s in sections
    }
    weighted = [
        (by_section[str(s.section_index)], s.word_count)
        for s in sections
        if s.word_count >= SHORT_SECTION_WORDS
    ]
    if not weighted:
        return by_section, None
    total_words = sum(w for _, w in weighted)
    mean = sum(score * w for score, w in weighted) / total_words
    return by_section, round(mean)
