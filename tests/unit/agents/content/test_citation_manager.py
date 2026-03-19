"""Tests for citation manager — global map, renumbering, validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.agents.content.citation_manager import (
    CitationValidationError,
    build_global_citation_map,
    renumber_section_markdown,
    validate_citation_count,
)
from src.models.content import Citation
from src.models.content_pipeline import CitationRef, SectionDraft


def _make_ref(
    index: int,
    url: str = "https://example.com",
    title: str = "Example",
    author: str | None = None,
    published_at: datetime | None = None,
) -> CitationRef:
    return CitationRef(
        index=index,
        source_url=url,
        source_title=title,
        author=author,
        published_at=published_at,
    )


def _make_draft(
    section_index: int,
    refs: list[CitationRef],
) -> SectionDraft:
    return SectionDraft(
        section_index=section_index,
        title=f"Section {section_index}",
        body_markdown="Some text.",
        word_count=50,
        citations_used=refs,
    )


# -- build_global_citation_map ------------------------------------------------


class TestBuildGlobalCitationMap:
    def test_deduplicates_by_url(self) -> None:
        drafts = [
            _make_draft(0, [_make_ref(1, url="https://a.com", title="A")]),
            _make_draft(
                1,
                [
                    _make_ref(1, url="https://a.com", title="A"),
                    _make_ref(2, url="https://b.com", title="B"),
                ],
            ),
        ]
        citations, _remap = build_global_citation_map(drafts)
        urls = [c.url for c in citations]
        assert len(citations) == 2
        assert "https://a.com" in urls
        assert "https://b.com" in urls

    def test_assigns_sequential_global_indices(self) -> None:
        drafts = [
            _make_draft(
                0,
                [
                    _make_ref(1, url="https://a.com"),
                    _make_ref(2, url="https://b.com"),
                ],
            ),
        ]
        citations, _remap = build_global_citation_map(drafts)
        assert citations[0].index == 1
        assert citations[1].index == 2

    def test_preserves_author_and_published_at(self) -> None:
        dt = datetime(2026, 3, 15, tzinfo=UTC)
        drafts = [
            _make_draft(
                0,
                [
                    _make_ref(
                        1,
                        url="https://a.com",
                        title="Article",
                        author="Jane Smith",
                        published_at=dt,
                    ),
                ],
            ),
        ]
        citations, _remap = build_global_citation_map(drafts)
        assert citations[0].authors == ["Jane Smith"]
        assert citations[0].published_at == dt

    def test_empty_drafts(self) -> None:
        citations, remap = build_global_citation_map([])
        assert citations == []
        assert remap == {}

    def test_remap_table_maps_section_local_to_global(self) -> None:
        drafts = [
            _make_draft(
                0,
                [
                    _make_ref(1, url="https://a.com"),
                    _make_ref(2, url="https://b.com"),
                ],
            ),
            _make_draft(
                1,
                [
                    _make_ref(1, url="https://b.com"),
                    _make_ref(2, url="https://c.com"),
                ],
            ),
        ]
        _citations, remap = build_global_citation_map(drafts)
        # Section 0: local 1 → a.com = global 1, local 2 → b.com = global 2
        assert remap[(0, 1)] == 1
        assert remap[(0, 2)] == 2
        # Section 1: local 1 → b.com = global 2, local 2 → c.com = global 3
        assert remap[(1, 1)] == 2
        assert remap[(1, 2)] == 3


# -- renumber_section_markdown -------------------------------------------------


class TestRenumberSectionMarkdown:
    def test_replaces_citation_indices(self) -> None:
        md = "Claim one [1] and claim two [2]."
        result = renumber_section_markdown(md, {1: 3, 2: 5})
        assert result == "Claim one [3] and claim two [5]."

    def test_handles_consecutive_citations(self) -> None:
        md = "Both sources agree [1][2] on this."
        result = renumber_section_markdown(md, {1: 4, 2: 7})
        assert result == "Both sources agree [4][7] on this."

    def test_skips_citations_in_code_blocks(self) -> None:
        md = (
            "Normal text [1] here.\n"
            "```\n"
            "code with [1] inside\n"
            "```\n"
            "After code [2] here."
        )
        result = renumber_section_markdown(md, {1: 10, 2: 20})
        assert "[10]" in result
        assert "[20]" in result
        # Inside code block should remain unchanged
        assert "code with [1] inside" in result

    def test_no_remap_needed(self) -> None:
        md = "No citations here."
        result = renumber_section_markdown(md, {})
        assert result == "No citations here."


# -- validate_citation_count ---------------------------------------------------


class TestValidateCitationCount:
    def test_passes_with_five_sources(self) -> None:
        citations = [
            Citation(index=i, title=f"T{i}", url=f"https://{i}.com")
            for i in range(1, 6)
        ]
        validate_citation_count(citations)  # should not raise

    def test_fails_with_four_sources(self) -> None:
        citations = [
            Citation(index=i, title=f"T{i}", url=f"https://{i}.com")
            for i in range(1, 5)
        ]
        with pytest.raises(CitationValidationError):
            validate_citation_count(citations)

    def test_passes_above_minimum(self) -> None:
        citations = [
            Citation(index=i, title=f"T{i}", url=f"https://{i}.com")
            for i in range(1, 9)
        ]
        validate_citation_count(citations)  # should not raise
