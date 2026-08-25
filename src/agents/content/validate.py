"""Article validation — word count checks, citation aggregation, re-drafting.

Pure validation functions (no I/O) plus a replace_section helper.
Called by the validate_article graph node.
"""

from dataclasses import dataclass

import structlog

from src.models.content_pipeline import ArticleOutline, CitationRef, SectionDraft

logger = structlog.get_logger()

_MIN_TOTAL_WORDS = 1500
# AUTHOR-008 — an article is "complete enough" at 60% of its outline's
# total target; below that the shortest section is re-drafted.
_EXPANSION_RATIO = 0.6


@dataclass(frozen=True)
class ValidationResult:
    """Result of article draft validation."""

    total_word_count: int
    all_citations: list[CitationRef]
    needs_expansion: bool
    shortest_index: int | None


def validate_drafts(
    drafts: list[SectionDraft],
    outline: ArticleOutline | None = None,
) -> ValidationResult:
    """Validate section drafts and aggregate citations.

    With an outline, the expansion floor and per-section warn bands come
    from its word budgets (AUTHOR-008); without one, the legacy
    1500/200-500 constants apply.
    """
    total = sum(d.word_count for d in drafts)
    citations = _deduplicate_citations(drafts)
    shortest = _find_shortest(drafts)
    floor = _expansion_floor(outline)
    result = ValidationResult(
        total_word_count=total,
        all_citations=citations,
        needs_expansion=total < floor,
        shortest_index=shortest,
    )
    _log_section_warnings(drafts, outline)
    _log_validation_result(drafts, result, floor)
    return result


def _expansion_floor(outline: ArticleOutline | None) -> int:
    """Words below which the article needs expansion."""
    if outline is None or outline.total_target_words <= 0:
        return _MIN_TOTAL_WORDS
    return int(outline.total_target_words * _EXPANSION_RATIO)


def _section_band(
    outline: ArticleOutline | None,
    section_index: int,
) -> tuple[int, int]:
    """Acceptable word band for one section: 0.5-1.5x its outline target."""
    if outline is not None:
        for s in outline.sections:
            if s.index == section_index and s.target_word_count > 0:
                return (s.target_word_count // 2, s.target_word_count * 3 // 2)
    return (200, 500)


def replace_section(
    drafts: list[SectionDraft],
    new_draft: SectionDraft,
) -> list[SectionDraft]:
    """Replace a section draft by index, return updated list."""
    return [
        new_draft if d.section_index == new_draft.section_index else d for d in drafts
    ]


def _deduplicate_citations(
    drafts: list[SectionDraft],
) -> list[CitationRef]:
    """Collect unique citations across all drafts by URL."""
    seen: dict[str, CitationRef] = {}
    for d in drafts:
        for c in d.citations_used:
            if c.source_url not in seen:
                seen[c.source_url] = c
    return list(seen.values())


def _find_shortest(drafts: list[SectionDraft]) -> int | None:
    """Return section_index of the shortest draft, or None."""
    if not drafts:
        return None
    return min(drafts, key=lambda d: d.word_count).section_index


def _log_section_warnings(
    drafts: list[SectionDraft],
    outline: ArticleOutline | None,
) -> None:
    """Warn on sections outside their budget band."""
    for d in drafts:
        lo, hi = _section_band(outline, d.section_index)
        if d.word_count < lo or d.word_count > hi:
            logger.warning(
                "section_word_count_outside_range",
                section_index=d.section_index,
                word_count=d.word_count,
            )


def _log_validation_result(
    drafts: list[SectionDraft],
    result: ValidationResult,
    floor: int,
) -> None:
    """Log final validation summary."""
    if result.needs_expansion:
        logger.warning(
            "article_below_word_target",
            total_words=result.total_word_count,
            target=floor,
            shortest_section=result.shortest_index,
        )
    logger.info(
        "article_draft_validated",
        total_words=result.total_word_count,
        section_count=len(drafts),
        unique_citations=len(result.all_citations),
    )
