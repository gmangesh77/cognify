"""Article validation — word count checks, citation aggregation, re-drafting.

Pure validation functions (no I/O) plus a replace_section helper.
Called by the validate_article graph node.
"""

from dataclasses import dataclass

import structlog

from src.models.content_pipeline import CitationRef, SectionDraft

logger = structlog.get_logger()

_MIN_TOTAL_WORDS = 1500


@dataclass(frozen=True)
class ValidationResult:
    """Result of article draft validation."""

    total_word_count: int
    all_citations: list[CitationRef]
    needs_expansion: bool
    shortest_index: int | None


def validate_drafts(drafts: list[SectionDraft]) -> ValidationResult:
    """Validate section drafts and aggregate citations."""
    total = sum(d.word_count for d in drafts)
    citations = _deduplicate_citations(drafts)
    shortest = _find_shortest(drafts)
    result = ValidationResult(
        total_word_count=total,
        all_citations=citations,
        needs_expansion=total < _MIN_TOTAL_WORDS,
        shortest_index=shortest,
    )
    _log_section_warnings(drafts)
    _log_validation_result(drafts, result)
    return result


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


def _log_section_warnings(drafts: list[SectionDraft]) -> None:
    """Warn on sections outside the 200-500 word range."""
    for d in drafts:
        if d.word_count < 200 or d.word_count > 500:
            logger.warning(
                "section_word_count_outside_range",
                section_index=d.section_index,
                word_count=d.word_count,
            )


def _log_validation_result(
    drafts: list[SectionDraft],
    result: ValidationResult,
) -> None:
    """Log final validation summary."""
    if result.needs_expansion:
        logger.warning(
            "article_below_word_target",
            total_words=result.total_word_count,
            target=_MIN_TOTAL_WORDS,
            shortest_section=result.shortest_index,
        )
    logger.info(
        "article_draft_validated",
        total_words=result.total_word_count,
        section_count=len(drafts),
        unique_citations=len(result.all_citations),
    )
