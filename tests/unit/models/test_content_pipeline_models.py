"""Tests for content pipeline Pydantic models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.content_pipeline import (
    ArticleDraft,
    ArticleOutline,
    CitationRef,
    DraftStatus,
    OutlineSection,
    SectionDraft,
    SectionQueries,
)


class TestOutlineSection:
    def test_construct(self) -> None:
        section = OutlineSection(
            index=0,
            title="Introduction",
            description="Set the context",
            key_points=["Point 1", "Point 2"],
            target_word_count=300,
            relevant_facets=[0, 1],
        )
        assert section.title == "Introduction"
        assert section.target_word_count == 300

    def test_frozen(self) -> None:
        section = OutlineSection(
            index=0,
            title="Intro",
            description="Desc",
            key_points=["P"],
            target_word_count=200,
            relevant_facets=[0],
        )
        with pytest.raises(ValidationError):
            section.title = "Changed"  # type: ignore[misc]


class TestArticleOutline:
    def test_construct(self) -> None:
        sections = [
            OutlineSection(
                index=i,
                title=f"Section {i}",
                description=f"Desc {i}",
                key_points=[f"Point {i}"],
                target_word_count=300,
                relevant_facets=[i % 3],
            )
            for i in range(5)
        ]
        outline = ArticleOutline(
            title="Test Article",
            content_type="article",
            sections=sections,
            total_target_words=1500,
            reasoning="Good structure",
        )
        assert len(outline.sections) == 5
        assert outline.total_target_words == 1500

    def test_serialization_roundtrip(self) -> None:
        outline = ArticleOutline(
            title="Test",
            content_type="analysis",
            sections=[
                OutlineSection(
                    index=0,
                    title="S",
                    description="D",
                    key_points=["P"],
                    target_word_count=200,
                    relevant_facets=[0],
                )
            ],
            total_target_words=200,
            reasoning="R",
        )
        data = outline.model_dump()
        restored = ArticleOutline.model_validate(data)
        assert restored == outline


class TestDraftStatus:
    def test_values(self) -> None:
        assert DraftStatus.OUTLINE_GENERATING == "outline_generating"
        assert DraftStatus.OUTLINE_COMPLETE == "outline_complete"
        assert DraftStatus.FAILED == "failed"


class TestArticleDraft:
    def test_construct_defaults(self) -> None:
        draft = ArticleDraft(
            session_id=uuid4(),
            topic_id=uuid4(),
            created_at=datetime.now(UTC),
        )
        assert draft.status == DraftStatus.OUTLINE_GENERATING
        assert draft.outline is None

    def test_with_outline(self) -> None:
        outline = ArticleOutline(
            title="Test",
            content_type="article",
            sections=[
                OutlineSection(
                    index=0,
                    title="S",
                    description="D",
                    key_points=["P"],
                    target_word_count=200,
                    relevant_facets=[0],
                )
            ],
            total_target_words=200,
            reasoning="R",
        )
        draft = ArticleDraft(
            session_id=uuid4(),
            topic_id=uuid4(),
            outline=outline,
            status=DraftStatus.OUTLINE_COMPLETE,
            created_at=datetime.now(UTC),
        )
        assert draft.outline is not None
        assert draft.status == DraftStatus.OUTLINE_COMPLETE


class TestCitationRef:
    def test_construct(self) -> None:
        ref = CitationRef(index=1, source_url="https://a.com", source_title="A")
        assert ref.index == 1
        assert ref.source_url == "https://a.com"

    def test_frozen(self) -> None:
        ref = CitationRef(index=1, source_url="https://a.com", source_title="A")
        with pytest.raises(ValidationError):
            ref.index = 2  # type: ignore[misc]


class TestSectionQueries:
    def test_construct(self) -> None:
        sq = SectionQueries(section_index=0, queries=["q1", "q2"])
        assert sq.section_index == 0
        assert len(sq.queries) == 2

    def test_frozen(self) -> None:
        sq = SectionQueries(section_index=0, queries=["q1"])
        with pytest.raises(ValidationError):
            sq.section_index = 1  # type: ignore[misc]


class TestSectionDraft:
    def test_construct(self) -> None:
        ref = CitationRef(index=1, source_url="https://a.com", source_title="A")
        sd = SectionDraft(
            section_index=0,
            title="Intro",
            body_markdown="Text with [1] citation.",
            word_count=5,
            citations_used=[ref],
        )
        assert sd.title == "Intro"
        assert sd.word_count == 5
        assert len(sd.citations_used) == 1

    def test_frozen(self) -> None:
        sd = SectionDraft(
            section_index=0,
            title="Intro",
            body_markdown="Text",
            word_count=1,
            citations_used=[],
        )
        with pytest.raises(ValidationError):
            sd.title = "Changed"  # type: ignore[misc]


class TestDraftStatusExtended:
    def test_draft_complete_value(self) -> None:
        assert DraftStatus.DRAFT_COMPLETE == "draft_complete"

    def test_all_values(self) -> None:
        expected = {
            "outline_generating",
            "outline_complete",
            "drafting",
            "draft_complete",
            "complete",
            "failed",
        }
        assert {s.value for s in DraftStatus} == expected
