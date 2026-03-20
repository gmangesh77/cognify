"""Structural pattern rules for AI text detection.

Regex patterns ported from slop-radar (MIT license).
Each pattern has a weight used for score deductions.
"""

from pydantic import BaseModel


class PatternRule(BaseModel, frozen=True):
    """A structural pattern that signals AI-generated text."""

    name: str
    pattern: str
    weight: int
    flags: str = "i"


STRUCTURAL_PATTERNS: list[PatternRule] = [
    PatternRule(name="em_dash", pattern=r"[\u2014\u2013]", weight=3),
    PatternRule(
        name="let_me_starter",
        pattern=r"^\s*let me \w+",
        weight=3,
        flags="im",
    ),
    PatternRule(
        name="heres_the_thing",
        pattern=r"here'?s (the thing|what|the deal|the kicker)",
        weight=3,
    ),
    PatternRule(
        name="binary_contrast",
        pattern=r"not (just|only|merely|simply) .{5,40}, but (also )?",
        weight=3,
    ),
    PatternRule(
        name="wh_starters",
        pattern=(
            r"^\s*(what makes this|why this matters"
            r"|why it matters|how this works|what this means)"
        ),
        weight=4,
        flags="im",
    ),
    PatternRule(
        name="bullet_overload",
        pattern=r"(^\s*[-*]\s.+\n){6,}",
        weight=4,
        flags="m",
    ),
    PatternRule(
        name="triple_adjective",
        pattern=(
            r"\b\w+(?:ly)?\b,\s+\b\w+(?:ly)?\b,"
            r"\s+(?:and\s+)?\b\w+(?:ly)?\b\s+\w+"
        ),
        weight=2,
    ),
    PatternRule(
        name="meta_reference",
        pattern=(
            r"in this (article|post|guide|blog"
            r"|piece|section|tutorial|overview|essay)"
        ),
        weight=3,
    ),
    PatternRule(
        name="passive_voice",
        pattern=r"\b(is|are|was|were|been|being)\s+\w+ed\b",
        weight=1,
    ),
    PatternRule(
        name="worth_noting",
        pattern=(
            r"^\s*it('s|\s+is)\s+worth\s+"
            r"(noting|mentioning|highlighting|pointing out)"
        ),
        weight=4,
        flags="im",
    ),
    PatternRule(
        name="colon_list_intro",
        pattern=r":\s*\n\s*[-*1]",
        weight=2,
        flags="m",
    ),
    PatternRule(
        name="emoji_header",
        pattern=r"^\s*[\U0001F300-\U0001FAD6]\s+\*\*",
        weight=5,
        flags="m",
    ),
    PatternRule(
        name="number_list_bold",
        pattern=r"^\s*\d+\.\s+\*\*.+\*\*",
        weight=2,
        flags="m",
    ),
    PatternRule(
        name="tldr_pattern",
        pattern=(
            r"(tl;?dr|key takeaway|bottom line"
            r"|in a nutshell)\s*:?\s*\n"
        ),
        weight=3,
        flags="im",
    ),
]
