"""Tests for content pipeline Pydantic models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.content_pipeline import (
    ArticleDraft,
    ArticleOutline,
    DraftStatus,
    OutlineSection,
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
