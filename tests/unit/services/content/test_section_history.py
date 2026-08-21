"""Tests for the section-history service (outline-index contract, L-013)."""

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
)
from src.services.content.section_history_contracts import (
    VersionRow,
    append_version_row,
    make_section_id,
    md_index_for,
    outline_index_for,
    parse_section_id,
)

ARTICLE_BODY = (
    "Intro prelude paragraph.\n\n"
    "## First Section\n"
    "First section body.\n\n"
    "## Second Section\n"
    "Second section body.\n"
)
BODY_NO_PRELUDE = (
    "## First Section\nFirst section body.\n\n## Second Section\nSecond section body.\n"
)


def _build_article(
    article_id: UUID,
    *,
    image_specs: list[ImageSpec] | None = None,
    body: str = ARTICLE_BODY,
) -> CanonicalArticle:
    return CanonicalArticle(
        id=article_id,
        title="Quiet refactor",
        body_markdown=body,
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


def _heading_spec(section_index: int, heading: str = "First Section") -> ImageSpec:
    return ImageSpec(
        id=f"img-{section_index}",
        role_style="hero",
        prompt="placeholder",
        placement=ImagePlacement(
            anchor="before_heading",
            heading_text=heading,
            section_index=section_index,
        ),
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


def _service(
    article: CanonicalArticle | None,
) -> tuple[SectionHistoryService, _FakeArticleRepo, _FakeVersionRepo]:
    articles = _FakeArticleRepo(article)
    versions = _FakeVersionRepo()
    return SectionHistoryService(articles, versions), articles, versions


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

    def test_md_index_is_outline_plus_one_and_inverts(self) -> None:
        assert md_index_for(0) == 1
        assert outline_index_for(1) == 0
        assert outline_index_for(md_index_for(4)) == 4

    @pytest.mark.asyncio
    async def test_append_version_row_fans_out_every_column(self) -> None:
        article_id = uuid4()
        versions = _FakeVersionRepo()
        row = VersionRow(
            article_id=article_id,
            section_index=2,
            markdown="## H\n\nbody",
            source="regenerate",
            instruction="tighter",
            model="claude-x",
            tokens_input=10,
            tokens_output=4,
            usd=0.01,
            created_by="user-1",
        )
        version_id = await append_version_row(versions, row)
        assert versions.appended == [
            {
                "article_id": article_id,
                "section_id": make_section_id(article_id, 2),
                "section_index": 2,
                "markdown": "## H\n\nbody",
                "source": "regenerate",
                "instruction": "tighter",
                "model": "claude-x",
                "tokens_input": 10,
                "tokens_output": 4,
                "usd": 0.01,
                "created_by": "user-1",
            }
        ]
        assert version_id == next(iter(versions._stored))


class TestOutlineIndexContract:
    """section_index is the 0-based H2 index — never the split_sections index."""

    @pytest.mark.asyncio
    async def test_index_zero_is_first_h2_when_body_starts_with_heading(self) -> None:
        article_id = uuid4()
        svc, _, _ = _service(_build_article(article_id, body=BODY_NO_PRELUDE))
        _, section = await svc.get_section_markdown(article_id, 0)
        assert section.heading == "## First Section"
        _, second = await svc.get_section_markdown(article_id, 1)
        assert second.heading == "## Second Section"

    @pytest.mark.asyncio
    async def test_index_zero_skips_the_prelude(self) -> None:
        article_id = uuid4()
        svc, _, _ = _service(_build_article(article_id))
        _, section = await svc.get_section_markdown(article_id, 0)
        assert section.heading == "## First Section"
        assert "Intro prelude" not in section.text

    @pytest.mark.asyncio
    async def test_negative_index_is_not_found(self) -> None:
        article_id = uuid4()
        svc, _, _ = _service(_build_article(article_id))
        with pytest.raises(SectionNotFoundError):
            await svc.get_section_markdown(article_id, -1)

    @pytest.mark.asyncio
    async def test_persist_replaces_outline_section_and_records_outline_index(
        self,
    ) -> None:
        article_id = uuid4()
        svc, articles, versions = _service(_build_article(article_id))
        await svc.persist_section_update(
            article_id=article_id,
            section_index=0,
            new_section_markdown="## First Section\nNew first body.",
            source="manual",
        )
        body = articles.persisted_body or ""
        assert body.startswith("Intro prelude paragraph.")
        assert "New first body." in body
        assert "## Second Section\nSecond section body." in body
        assert versions.appended[0]["section_index"] == 0
        assert versions.appended[0]["section_id"] == make_section_id(article_id, 0)

    @pytest.mark.asyncio
    async def test_heading_check_receives_the_outline_index(self) -> None:
        # Spec bound to OUTLINE section 0 ("First Section").
        article_id = uuid4()
        svc, articles, _ = _service(
            _build_article(article_id, image_specs=[_heading_spec(0)])
        )
        # Renaming section 0's heading must violate.
        with pytest.raises(AnchorViolationError) as ei:
            await svc.persist_section_update(
                article_id=article_id,
                section_index=0,
                new_section_markdown="## Renamed Heading\nNew body.",
                source="manual",
            )
        assert ei.value.violations[0].kind == "heading_text"
        assert articles.persisted_body is None
        # Renaming section 1's heading is fine — the spec is not bound to it.
        await svc.persist_section_update(
            article_id=article_id,
            section_index=1,
            new_section_markdown="## Other\nNew body.",
            source="manual",
        )
        assert "## Other" in (articles.persisted_body or "")


class TestPersistSectionUpdate:
    @pytest.mark.asyncio
    async def test_happy_path_updates_body_and_appends_version(self) -> None:
        article_id = uuid4()
        svc, articles, versions = _service(_build_article(article_id))
        result = await svc.persist_section_update(
            article_id=article_id,
            section_index=0,
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
        svc, articles, versions = _service(
            _build_article(article_id, image_specs=[_heading_spec(0)])
        )
        with pytest.raises(AnchorViolationError) as ei:
            await svc.persist_section_update(
                article_id=article_id,
                section_index=0,
                new_section_markdown="## Renamed Heading\nNew body.",
                source="manual",
            )
        assert ei.value.violations
        assert ei.value.violations[0].kind == "heading_text"
        assert articles.persisted_body is None
        assert versions.appended == []

    @pytest.mark.asyncio
    async def test_unknown_article_raises_not_found(self) -> None:
        svc, _, _ = _service(None)
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
        svc, _, _ = _service(_build_article(article_id))
        with pytest.raises(SectionNotFoundError):
            await svc.persist_section_update(
                article_id=article_id,
                section_index=99,
                new_section_markdown="x",
                source="manual",
            )

    @pytest.mark.asyncio
    async def test_restore_round_trip_uses_outline_index(self) -> None:
        article_id = uuid4()
        svc, articles, versions = _service(_build_article(article_id))
        v1 = await svc.persist_section_update(
            article_id=article_id,
            section_index=0,
            new_section_markdown="## First Section\nVersion one.",
            source="ai",
            instruction="tighten",
        )
        await svc.persist_section_update(
            article_id=article_id,
            section_index=0,
            new_section_markdown="## First Section\nVersion two.",
            source="manual",
        )
        assert "Version two" in (articles.persisted_body or "")
        restored = await svc.restore(
            section_id=make_section_id(article_id, 0),
            version_id=v1.version_id,
            created_by="user-1",
        )
        body = articles.persisted_body or ""
        assert "Version one" in body
        assert body.startswith("Intro prelude paragraph.")  # prelude untouched
        assert "## Second Section" in body
        assert restored.version_id is not None
        assert len(versions.appended) == 3
        assert versions.appended[-1]["source"] == "restore"
