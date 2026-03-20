"""Slop scoring engine — detects AI writing patterns.

Pure functions, no LLM, no I/O. Scans text for slop phrases,
structural patterns, repetitive openers, and passive voice density.
Returns a SlopScore with violations and a 0-100 rating.
"""

import re
import statistics

from src.agents.content.slop_patterns import STRUCTURAL_PATTERNS
from src.agents.content.slop_phrases import SLOP_PHRASES
from src.models.content_pipeline import SectionDraft, SlopScore, Violation

_PHRASE_PENALTY = 2
_PASSIVE_DENSITY_THRESHOLD = 0.3
_PASSIVE_DENSITY_PENALTY = 10
_QUESTION_BONUS = 5
_VARIANCE_BONUS = 5
_VARIANCE_THRESHOLD = 4.0
_OPENER_THRESHOLD = 0.3
_OPENER_MIN_COUNT = 3
_OPENER_PENALTY = 3

_RE_FLAGS: dict[str, re.RegexFlag] = {
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "im": re.IGNORECASE | re.MULTILINE,
}

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on . ! ? boundaries."""
    parts = _SENTENCE_RE.split(text.strip())
    return [s.strip() for s in parts if s.strip()]


def _find_sentence_index(match_start: int, boundaries: list[tuple[int, int]]) -> int:
    """Return sentence index containing the match position."""
    for idx, (start, end) in enumerate(boundaries):
        if start <= match_start < end:
            return idx
    return 0


def _sentence_boundaries(text: str, sentences: list[str]) -> list[tuple[int, int]]:
    """Compute (start, end) char positions for each sentence."""
    bounds: list[tuple[int, int]] = []
    pos = 0
    for sent in sentences:
        start = text.find(sent, pos)
        if start == -1:
            start = pos
        bounds.append((start, start + len(sent)))
        pos = start + len(sent)
    return bounds


def _scan_phrases(text: str, sentences: list[str]) -> list[Violation]:
    """Detect slop phrases with whole-word, case-insensitive matching."""
    bounds = _sentence_boundaries(text, sentences)
    violations: list[Violation] = []
    lower = text.lower()
    for category, phrases in SLOP_PHRASES.items():
        for phrase in phrases:
            pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
            for match in pattern.finditer(lower):
                idx = _find_sentence_index(match.start(), bounds)
                violations.append(
                    Violation(
                        category=category,
                        phrase=phrase,
                        sentence_index=idx,
                    )
                )
    return violations


def _scan_patterns(text: str, violations: list[Violation]) -> int:
    """Scan structural patterns (except passive_voice). Returns deductions."""
    deductions = 0
    for rule in STRUCTURAL_PATTERNS:
        if rule.name == "passive_voice":
            continue
        flags = _RE_FLAGS.get(rule.flags, re.IGNORECASE)
        matches = re.findall(rule.pattern, text, flags)
        for _ in matches:
            violations.append(
                Violation(
                    category="pattern",
                    phrase=rule.name,
                    sentence_index=0,
                )
            )
        deductions += len(matches) * rule.weight
    return deductions


def _check_passive_density(text: str, sentences: list[str]) -> int:
    """Penalise if passive voice exceeds threshold."""
    passive_rule = next(
        (r for r in STRUCTURAL_PATTERNS if r.name == "passive_voice"),
        None,
    )
    if passive_rule is None or not sentences:
        return 0
    flags = _RE_FLAGS.get(passive_rule.flags, re.IGNORECASE)
    count = len(re.findall(passive_rule.pattern, text, flags))
    if count / len(sentences) > _PASSIVE_DENSITY_THRESHOLD:
        return _PASSIVE_DENSITY_PENALTY
    return 0


def _check_repetitive_openers(
    sentences: list[str],
) -> list[Violation]:
    """Flag sentences that start with the same word too often."""
    if not sentences:
        return []
    openers: dict[str, list[int]] = {}
    for idx, sent in enumerate(sentences):
        words = sent.split()
        if words:
            word = words[0].lower().rstrip(",.;:")
            openers.setdefault(word, []).append(idx)
    violations: list[Violation] = []
    for word, indices in openers.items():
        count = len(indices)
        if count >= _OPENER_MIN_COUNT and count / len(sentences) > _OPENER_THRESHOLD:
            violations.append(
                Violation(
                    category="repetitive_opener",
                    phrase=word,
                    sentence_index=indices[0],
                )
            )
    return violations


def _calculate_bonuses(text: str, sentences: list[str]) -> int:
    """Award bonuses for questions and sentence-length variance."""
    bonus = 0
    if "?" in text:
        bonus += _QUESTION_BONUS
    if len(sentences) >= 2:
        lengths = [len(s.split()) for s in sentences]
        if statistics.stdev(lengths) > _VARIANCE_THRESHOLD:
            bonus += _VARIANCE_BONUS
    return bonus


def _get_rating(score: int) -> str:
    """Map numeric score to a human-readable rating."""
    if score >= 80:
        return "HUMAN"
    if score >= 60:
        return "MOSTLY_HUMAN"
    if score >= 40:
        return "LIKELY_AI"
    return "PURE_SLOP"


def score_text(text: str) -> SlopScore:
    """Score text for AI-writing patterns. Returns SlopScore (0-100)."""
    sentences = _split_sentences(text)

    violations = _scan_phrases(text, sentences)
    phrase_deductions = len(violations) * _PHRASE_PENALTY

    pattern_deductions = _scan_patterns(text, violations)
    pattern_deductions += _check_passive_density(text, sentences)

    opener_violations = _check_repetitive_openers(sentences)
    violations.extend(opener_violations)
    opener_deductions = len(opener_violations) * _OPENER_PENALTY

    bonuses = _calculate_bonuses(text, sentences)

    raw = 100 - phrase_deductions - pattern_deductions - opener_deductions + bonuses
    clamped = max(0, min(100, raw))

    return SlopScore(
        score=clamped,
        rating=_get_rating(clamped),
        violations=violations,
        phrase_deductions=phrase_deductions,
        pattern_deductions=pattern_deductions,
    )


def score_section(section: SectionDraft) -> SlopScore:
    """Convenience wrapper: score a SectionDraft's body."""
    return score_text(section.body_markdown)
