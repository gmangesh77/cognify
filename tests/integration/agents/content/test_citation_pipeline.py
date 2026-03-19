"""Integration tests for the citation management pipeline node."""

from datetime import UTC, datetime

import pytest

from src.agents.content.citation_manager import manage_citations
from src.models.content_pipeline import CitationRef, SectionDraft


def _make_ref(
    index: int,
    url: str,
    title: str,
    *,
    author: str | None = None,
    published_at: datetime | None = None,
) -> CitationRef:
    """Build a CitationRef with sensible defaults."""
    return CitationRef(
        index=index,
        source_url=url,
        source_title=title,
        author=author,
        published_at=published_at,
    )


@pytest.fixture()
def five_source_drafts() -> list[SectionDraft]:
    """Three section drafts referencing 5 unique source URLs."""
    ts = datetime(2026, 1, 15, tzinfo=UTC)
    return [
        SectionDraft(
            section_index=0,
            title="Introduction",
            body_markdown="Fact A [1]. Fact B [2]. Fact C [3].",
            word_count=300,
            citations_used=[
                _make_ref(
                    1, "https://a.com", "Source A", author="Alice", published_at=ts
                ),
                _make_ref(2, "https://b.com", "Source B"),
                _make_ref(3, "https://c.com", "Source C"),
            ],
        ),
        SectionDraft(
            section_index=1,
            title="Analysis",
            body_markdown="Claim D [1]. Claim E [2].",
            word_count=250,
            citations_used=[
                _make_ref(1, "https://a.com", "Source A"),
                _make_ref(2, "https://d.com", "Source D"),
            ],
        ),
        SectionDraft(
            section_index=2,
            title="Conclusion",
            body_markdown="Summary [1].",
            word_count=200,
            citations_used=[
                _make_ref(1, "https://e.com", "Source E"),
            ],
        ),
    ]


async def test_produces_globally_renumbered_markdown(
    five_source_drafts: list[SectionDraft],
) -> None:
    """Full pipeline produces global citations and references markdown."""
    state = {"section_drafts": five_source_drafts, "status": "draft_complete"}

    result = await manage_citations(state)  # type: ignore[arg-type]

    assert result.get("status") != "failed", result.get("error")
    citations = result["global_citations"]
    assert isinstance(citations, list)
    assert len(citations) == 5

    refs_md = result["references_markdown"]
    assert isinstance(refs_md, str)
    assert "## References" in refs_md
    for url in ("a.com", "b.com", "c.com", "d.com", "e.com"):
        assert url in refs_md


async def test_fails_with_insufficient_sources() -> None:
    """Pipeline fails when fewer than 5 unique sources are provided."""
    drafts = [
        SectionDraft(
            section_index=0,
            title="Intro",
            body_markdown="Claim [1].",
            word_count=100,
            citations_used=[_make_ref(1, "https://x.com", "Source X")],
        ),
        SectionDraft(
            section_index=1,
            title="Body",
            body_markdown="Claim [1].",
            word_count=100,
            citations_used=[_make_ref(1, "https://y.com", "Source Y")],
        ),
    ]
    state = {"section_drafts": drafts, "status": "draft_complete"}

    result = await manage_citations(state)  # type: ignore[arg-type]

    assert result["status"] == "failed"
    error = str(result.get("error", ""))
    assert "5" in error
    assert "2" in error


async def test_preserves_upstream_metadata(
    five_source_drafts: list[SectionDraft],
) -> None:
    """Author and published_at survive deduplication into global citations."""
    state = {"section_drafts": five_source_drafts, "status": "draft_complete"}

    result = await manage_citations(state)  # type: ignore[arg-type]

    citations = result["global_citations"]
    assert isinstance(citations, list)

    a_com = next(c for c in citations if c["url"] == "https://a.com")
    assert a_com["authors"] == ["Alice"]
    assert a_com["published_at"] is not None
