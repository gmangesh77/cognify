"""Tests for article validation — word count checks and citation dedup."""

from src.agents.content.validate import replace_section, validate_drafts
from src.models.content_pipeline import (
    ArticleOutline,
    CitationRef,
    OutlineSection,
    SectionDraft,
)


def _make_outline(section_targets: list[int]) -> ArticleOutline:
    sections = [
        OutlineSection(
            index=i,
            title=f"Section {i}",
            description="d",
            key_points=["k"],
            target_word_count=t,
            relevant_facets=[0],
        )
        for i, t in enumerate(section_targets)
    ]
    return ArticleOutline(
        title="T",
        content_type="article",
        sections=sections,
        total_target_words=sum(section_targets),
        reasoning="r",
    )


def _make_draft(
    index: int,
    word_count: int,
    url: str = "https://a.com",
) -> SectionDraft:
    words = " ".join(["word"] * word_count)
    return SectionDraft(
        section_index=index,
        title=f"Section {index}",
        body_markdown=words,
        word_count=word_count,
        citations_used=[CitationRef(index=1, source_url=url, source_title="A")],
    )


class TestValidateDrafts:
    def test_passes_when_above_target(self) -> None:
        drafts = [_make_draft(0, 800), _make_draft(1, 800)]
        result = validate_drafts(drafts)
        assert result.total_word_count == 1600
        assert result.needs_expansion is False

    def test_flags_below_target(self) -> None:
        drafts = [_make_draft(0, 400), _make_draft(1, 300)]
        result = validate_drafts(drafts)
        assert result.total_word_count == 700
        assert result.needs_expansion is True
        assert result.shortest_index == 1

    def test_deduplicates_citations(self) -> None:
        drafts = [
            _make_draft(0, 800, url="https://a.com"),
            _make_draft(1, 800, url="https://a.com"),
        ]
        result = validate_drafts(drafts)
        assert len(result.all_citations) == 1

    def test_multiple_unique_citations(self) -> None:
        drafts = [
            _make_draft(0, 800, url="https://a.com"),
            _make_draft(1, 800, url="https://b.com"),
        ]
        result = validate_drafts(drafts)
        assert len(result.all_citations) == 2

    def test_empty_drafts(self) -> None:
        result = validate_drafts([])
        assert result.total_word_count == 0
        assert result.needs_expansion is True
        assert result.shortest_index is None
        assert result.all_citations == []


class TestBudgetAwareValidation:
    """AUTHOR-008 — expansion threshold derives from the outline's totals."""

    def test_pillar_outline_raises_expansion_threshold(self) -> None:
        # 6 x 400 = 2400 words: fine under the legacy 1500 floor, but a
        # 6000-word pillar outline demands expansion (floor = 0.6 * 6000).
        outline = _make_outline([1000] * 6)
        drafts = [_make_draft(i, 400) for i in range(6)]
        result = validate_drafts(drafts, outline)
        assert result.needs_expansion is True

    def test_no_outline_keeps_legacy_1500_threshold(self) -> None:
        drafts = [_make_draft(i, 400) for i in range(4)]  # 1600 total
        assert validate_drafts(drafts).needs_expansion is False

    def test_short_outline_does_not_demand_1500(self) -> None:
        # 3 x 250 = 750 words >= 0.6 * 900 — a short article is complete
        # even though it is far below the legacy 1500 floor.
        outline = _make_outline([300] * 3)
        drafts = [_make_draft(i, 250) for i in range(3)]
        assert validate_drafts(drafts, outline).needs_expansion is False

    def test_outline_meeting_target_passes(self) -> None:
        outline = _make_outline([1000] * 6)
        drafts = [_make_draft(i, 900) for i in range(6)]
        assert validate_drafts(drafts, outline).needs_expansion is False


class TestReplaceSection:
    def test_replaces_by_index(self) -> None:
        drafts = [_make_draft(0, 400), _make_draft(1, 300)]
        new = _make_draft(1, 600)
        result = replace_section(drafts, new)
        assert result[1].word_count == 600
        assert result[0].word_count == 400

    def test_preserves_other_sections(self) -> None:
        drafts = [_make_draft(0, 400), _make_draft(1, 300), _make_draft(2, 500)]
        new = _make_draft(1, 600)
        result = replace_section(drafts, new)
        assert len(result) == 3
        assert result[0].word_count == 400
        assert result[1].word_count == 600
        assert result[2].word_count == 500

    def test_no_match_leaves_list_unchanged(self) -> None:
        drafts = [_make_draft(0, 400), _make_draft(1, 300)]
        new = _make_draft(9, 600)
        result = replace_section(drafts, new)
        assert result[0].word_count == 400
        assert result[1].word_count == 300
