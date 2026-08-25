"""Length-target word budgets for the outliner (AUTHOR-008).

Defaults live here (next to the consumer); ``COGNIFY_LENGTH_BUDGETS_JSON``
in settings holds sparse per-key overrides, merged two-level so
``{"long": {"total_max": 6000}}`` keeps long's other numbers.
"""

from __future__ import annotations

LengthBudget = dict[str, int]

DEFAULT_LENGTH_BUDGETS: dict[str, LengthBudget] = {
    "short": {
        "sections_min": 3,
        "sections_max": 5,
        "section_min": 150,
        "section_max": 350,
        "total_min": 800,
        "total_max": 1200,
    },
    "medium": {
        "sections_min": 4,
        "sections_max": 8,
        "section_min": 200,
        "section_max": 500,
        "total_min": 1500,
        "total_max": 3000,
    },
    "long": {
        "sections_min": 6,
        "sections_max": 10,
        "section_min": 400,
        "section_max": 700,
        "total_min": 3000,
        "total_max": 5000,
    },
    "pillar": {
        "sections_min": 8,
        "sections_max": 12,
        "section_min": 500,
        "section_max": 900,
        "total_min": 5000,
        "total_max": 8000,
    },
}

_CONTENT_TYPE_GUIDANCE: dict[str, str] = {
    "how-to": (
        "Structure as a practical how-to guide: after a short introduction, "
        "each section is a sequential, actionable step with concrete "
        "instructions; end with common pitfalls or next steps."
    ),
    "analysis": (
        "Structure as an analysis: open with the thesis, dedicate sections "
        "to supporting evidence, address counterpoints, close with "
        "implications."
    ),
    "report": (
        "Structure as a report: lead with key findings, follow with "
        "data-driven detail sections, close with outlook and "
        "recommendations."
    ),
}


def budget_for(
    length_target: str | None,
    overrides: dict[str, dict[str, int]],
) -> LengthBudget:
    """Resolve the budget for a length target; unknown/None -> medium."""
    key = length_target if length_target in DEFAULT_LENGTH_BUDGETS else "medium"
    return {**DEFAULT_LENGTH_BUDGETS[key], **overrides.get(key, {})}


def content_type_guidance(content_type: str | None) -> str | None:
    """Structural prompt guidance per content type; None for article/default."""
    if content_type is None:
        return None
    return _CONTENT_TYPE_GUIDANCE.get(content_type)


__all__ = [
    "DEFAULT_LENGTH_BUDGETS",
    "LengthBudget",
    "budget_for",
    "content_type_guidance",
]
