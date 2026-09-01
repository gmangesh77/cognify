"""Stylometric fingerprint — stdlib only (spec §4.1)."""

from __future__ import annotations

import re
import statistics

from src.models.persona import DimStat, VoiceFingerprint
from src.services.persona.lexicon import (
    _BOOSTERS,
    _FIRST_PERSON,
    _HEDGES,
    DIM_LABELS,
)
from src.utils.markdown_structure import (
    extract_humanizable_text,
    humanizable_blocks,
    parse_markdown_blocks,
)

__all__ = [
    "DIMENSIONS",
    "DIM_LABELS",
    "InsufficientSamples",
    "build_fingerprint",
    "count_words",
    "text_features",
]

MIN_SAMPLES = 5
MIN_SAMPLE_WORDS = 150
CONFIDENCE_FULL_N = 8
_TTR_WINDOW = 500

DIMENSIONS: tuple[str, ...] = (
    "sentence_len_mean",
    "sentence_len_std",
    "fk_grade",
    "ttr",
    "contraction_rate",
    "hedge_rate",
    "booster_rate",
    "punct_comma_per_1k",
    "punct_semicolon_per_1k",
    "punct_dash_per_1k",
    "punct_question_per_1k",
    "paragraph_len_mean",
    "first_person_rate",
)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_CONTRACTION_RE = re.compile(r"\b\w+'(?:t|s|re|ve|ll|d|m)\b", re.IGNORECASE)
_DASH_RE = re.compile(r"[—–]|(?<=\s)-(?=\s)|--")


class InsufficientSamples(ValueError):
    """Fewer than MIN_SAMPLES samples of MIN_SAMPLE_WORDS words."""


def count_words(text: str) -> int:
    """Single source of truth for "word" across the persona engine — the
    same letter-only regex `build_fingerprint`'s validity filter uses, so
    the 422 gate, the stored `word_count`, and fingerprint eligibility
    never disagree (AUTHOR-011 review round 1)."""
    return len(_WORD_RE.findall(text))


def _prose(text: str) -> str:
    blocks = parse_markdown_blocks(text)
    parts = [extract_humanizable_text(b) or "" for _, b in humanizable_blocks(blocks)]
    prose = "\n\n".join(p for p in parts if p.strip())
    return prose if prose.strip() else text


def _syllables(word: str) -> int:
    groups = re.findall(r"[aeiouy]+", word.lower())
    count = len(groups)
    if word.lower().endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def _sentences(prose: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(prose.strip()) if s.strip()]


def _per(count: int, n: int, unit: int) -> float:
    return (count / n) * unit if n else 0.0


def _sentence_stats(sentences: list[str]) -> tuple[float, float]:
    lengths = [len(_WORD_RE.findall(s)) for s in sentences]
    if not lengths:
        return 0.0, 0.0
    return statistics.fmean(lengths), statistics.pstdev(lengths)


def _fk_grade(words: list[str], sentences: list[str]) -> float:
    if not words or not sentences:
        return 0.0
    syllables = sum(_syllables(w) for w in words)
    return (
        0.39 * (len(words) / len(sentences)) + 11.8 * (syllables / len(words)) - 15.59
    )


def _ttr(words: list[str]) -> float:
    window = [w.lower() for w in words[:_TTR_WINDOW]]
    return len(set(window)) / len(window) if window else 0.0


def _paragraph_len_mean(prose: str) -> float:
    paras = [p for p in re.split(r"\n\s*\n", prose) if p.strip()]
    if not paras:
        return 0.0
    return statistics.fmean(len(_WORD_RE.findall(p)) for p in paras)


def _lexical_features(prose: str, words: list[str], n: int) -> dict[str, float]:
    """Lexical features: contractions, hedges, boosters, first-person, TTR."""
    lowered = [w.lower() for w in words]
    return {
        "contraction_rate": _per(len(_CONTRACTION_RE.findall(prose)), n, 100),
        "hedge_rate": _per(sum(w in _HEDGES for w in lowered), n, 100),
        "booster_rate": _per(sum(w in _BOOSTERS for w in lowered), n, 100),
        "ttr": _ttr(words),
        "first_person_rate": _per(sum(w in _FIRST_PERSON for w in lowered), n, 100),
    }


def _punct_features(prose: str, n: int) -> dict[str, float]:
    """Punctuation features: comma, semicolon, dash, question rates."""
    return {
        "punct_comma_per_1k": _per(prose.count(","), n, 1000),
        "punct_semicolon_per_1k": _per(prose.count(";"), n, 1000),
        "punct_dash_per_1k": _per(len(_DASH_RE.findall(prose)), n, 1000),
        "punct_question_per_1k": _per(prose.count("?"), n, 1000),
    }


def text_features(text: str) -> dict[str, float]:
    """All DIMENSIONS for one text (zeros for empty input)."""
    prose = _prose(text)
    words = _WORD_RE.findall(prose)
    sentences = _sentences(prose)
    n = len(words)
    mean_len, std_len = _sentence_stats(sentences)
    return {
        "sentence_len_mean": mean_len,
        "sentence_len_std": std_len,
        "fk_grade": max(_fk_grade(words, sentences), 0.0),
        "paragraph_len_mean": _paragraph_len_mean(prose),
        **_lexical_features(prose, words, n),
        **_punct_features(prose, n),
    }


def _dim_stat(values: list[float], n: int) -> DimStat:
    mean = statistics.fmean(values)
    stddev = statistics.pstdev(values)
    cv = stddev / abs(mean) if mean else (0.0 if stddev == 0 else 1.0)
    confidence = min(1.0, n / CONFIDENCE_FULL_N) * (1.0 - min(1.0, cv))
    return DimStat(mean=mean, stddev=stddev, confidence=round(confidence, 4))


def build_fingerprint(samples: list[str]) -> VoiceFingerprint:
    """Per-dimension {mean, stddev, confidence} over the valid samples."""
    valid = [s for s in samples if count_words(s) >= MIN_SAMPLE_WORDS]
    if len(valid) < MIN_SAMPLES:
        msg = (
            f"need {MIN_SAMPLES} samples of {MIN_SAMPLE_WORDS}+ words, "
            f"have {len(valid)}"
        )
        raise InsufficientSamples(msg)
    feats = [text_features(s) for s in valid]
    dims = {
        name: _dim_stat([f[name] for f in feats], len(valid)) for name in DIMENSIONS
    }
    return VoiceFingerprint(dims=dims, sample_count=len(valid))
