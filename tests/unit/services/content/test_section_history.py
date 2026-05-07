"""Tests for the section-history service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.models.content import (
    CanonicalArticle,
    ContentType,
    Provenance,
    SEOMetadata,
)
from src.models.visual import ImagePlacement, ImageSpec
from src.services.content.section_history import (
    AnchorViolationError,
    ArticleNotFoundError,
    SectionHistoryService,
    SectionNotFoundError,
    make_section_id,
    parse_section_id,
)

ARTICLE_BODY = (
    "Intro prelude paragraph.\n\n"
    "## First Section\n"
    "First section body.\n\n"
    "## Second Section\n"
    "Second section body.\n"
)


def _build_article(
    article_id: UUID,
    *,
    image_specs: list[ImageSpec] | None = None,
) -> CanonicalArticle:
    return CanonicalArticle(
        id=article_id,
        title="Quiet refactor",
        body_markdown=ARTICLE_BODY,
        summary="Small steps compound.",
        content_type=ContentType.ARTICLE,
        seo=SEOMetadata(title="Quiet refactor", description="Summary."),
        authors=["Cognify"],
        domain="engineering",
        generated_at=datetime.now(UTC),
        provenance=Provenance(
            research_session_id=uuid4(),
            primary_model="m",
            drafting_model="m",
            embedding_model="e",
            embedding_version="v1",
        ),
        image_specs=image_specs or [],
    )


@dataclass
class _StoredVersion:
    id: UUID
    markdown: str


class _FakeArticleRepo:
    def __init__(self, article: CanonicalArticle | None) -> None:
        self.article = article
        self.persisted_body: str | None = None

    async def get(self, article_id: UUID) -> CanonicalArticle | None:
        if self.article is None or self.article.id != article_id:
            return None
        return self.article

    async def update_body_markdown(
        self, article_id: UUID, body_markdown: str
    ) -> CanonicalArticle | None:
        if self.article is None or self.article.id != article_id:
            return None
        self.persisted_body = body_markdown
        self.article = self.article.model_copy(update={"body_markdown": body_markdown})
        return self.article


class _FakeVersionRepo:
    def __init__(self) -> None:
        self.appended: list[dict[str, object]] = []
        self._stored: dict[UUID, _StoredVersion] = {}

    async def append(self, **kwargs: object) -> _StoredVersion:
        version_id = uuid4()
        markdown = kwargs.get("markdown", "")
        assert isinstance(markdown, str)
        self.appended.append(kwargs)
        stored = _StoredVersion(id=version_id, markdown=markdown)
        self._stored[version_id] = stored
        return stored

    async def list_for_section(
        self, *, article_id: UUID, section_id: str, limit: int = 50
    ) -> list[_StoredVersion]:
        return list(self._stored.values())

    async def get(self, version_id: UUID) -> _StoredVersion | None:
        return self._stored.get(version_id)


class TestSectionIdHelpers:
    def test_make_and_parse_round_trip(self) -> None:
        article_id = uuid4()
        sid = make_section_id(article_id, 3)
        parsed_article, parsed_index = parse_section_id(sid)
        assert parsed_article == article_id
        assert parsed_index == 3

    def test_parse_rejects_malformed(self) -> None:
        with pytest.raises(ValueError):
            parse_section_id("not-a-section-id")


class TestPersistSectionUpdate:
    @pytest.mark.asyncio
    async def test_happy_path_updates_body_and_appends_version(self) -> None:
        article_id = uuid4()
        articles = _FakeArticleRepo(_build_article(article_id))
        versions = _FakeVersionRepo()
        svc = SectionHistoryService(articles, versions)

        result = await svc.persist_section_update(
            article_id=article_id,
            section_index=1,
            new_section_markdown="## First Section\nA tighter rewrite.",
            source="manual",
            created_by="user-1",
        )
        assert articles.persisted_body is not None
        assert "tighter rewrite" in articles.persisted_body
        assert "## Second Section" in articles.persisted_body
        assert len(versions.appended) == 1
        assert versions.appended[0]["source"] == "manual"
        assert result.version_id is not None

    @pytest.mark.asyncio
    async def test_anchor_violation_raises(self) -> None:
        article_id = uuid4()
        spec = ImageSpec(
            id="img-01",
            role_style="hero",
            prompt="placeholder",
            placement=ImagePlacement(
                anchor="before_heading",
                heading_text="First Section",
                section_index=1,
            ),
        )
        articles = _FakeArticleRepo(_build_article(article_id, image_specs=[spec]))
        versions = _FakeVersionRepo()
        svc = SectionHistoryService(articles, versions)

        with pytest.raises(AnchorViolationError) as ei:
            await svc.persist_section_update(
                article_id=article_id,
                section_index=1,
                new_section_markdown="## Renamed Heading\nNew body.",
                source="manual",
            )
        assert ei.value.violations
        assert ei.value.violations[0].kind == "heading_text"
        # Article body must NOT have been modified after a violation.
        assert articles.persisted_body is None
        assert versions.appended == []

    @pytest.mark.asyncio
    async def test_unknown_article_raises_not_found(self) -> None:
        articles = _FakeArticleRepo(None)
        versions = _FakeVersionRepo()
        svc = SectionHistoryService(articles, versions)
        with pytest.raises(ArticleNotFoundError):
            await svc.persist_section_update(
                article_id=uuid4(),
                section_index=0,
                new_section_markdown="x",
                source="manual",
            )

    @pytest.mark.asyncio
    async def test_out_of_range_section_raises(self) -> None:
        article_id = uuid4()
        articles = _FakeArticleRepo(_build_article(article_id))
        versions = _FakeVersionRepo()
        svc = SectionHistoryService(articles, versions)
        with pytest.raises(SectionNotFoundError):
            await svc.persist_section_update(
                article_id=article_id,
                section_index=99,
                new_section_markdown="x",
                source="manual",
            )

    @pytest.mark.asyncio
    async def test_restore_round_trip(self) -> None:
        article_id = uuid4()
        articles = _FakeArticleRepo(_build_article(article_id))
        versions = _FakeVersionRepo()
        svc = SectionHistoryService(articles, versions)

        # Persist v1 (the rewrite).
        v1 = await svc.persist_section_update(
            article_id=article_id,
            section_index=1,
            new_section_markdown="## First Section\nVersion one.",
            source="ai",
            instruction="tighten",
        )
        # Persist v2 (a manual edit).
        await svc.persist_section_update(
            article_id=article_id,
            section_index=1,
            new_section_markdown="## First Section\nVersion two.",
            source="manual",
        )
        assert "Version two" in (articles.persisted_body or "")

        # Restore to v1.
        section_id = make_section_id(article_id, 1)
        restored = await svc.restore(
            section_id=section_id,
            version_id=v1.version_id,
            created_by="user-1",
        )
        assert "Version one" in (articles.persisted_body or "")
        assert restored.version_id is not None
        # 3 appends total: v1, v2, restore.
        assert len(versions.appended) == 3
        assert versions.appended[-1]["source"] == "restore"
