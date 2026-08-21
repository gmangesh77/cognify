"""Section-level edit history service (VISUAL-011 / Phase 8; L-013 index contract).

Stitches the canonical article body, the anchor validator, and the
append-only `section_versions` repository into one Service-Layer entry
point that the `/content/*` route handlers call.

Boundary invariants (mirrored from plan §11.8):
- The active state still lives on `CanonicalArticle.body_markdown` —
  this service updates that on every persist. The `section_versions`
  table is an audit sidecar; no other subsystem reads it.
- Anchor preservation is enforced here. Edits that drop a `data-spec-id`
  marker or rename a heading bound to a `before_heading` placement
  raise `AnchorViolationError`, which the route maps to HTTP 422.
- Index contract (L-013): every public `section_index` is the 0-based H2
  (outline) index. `md_index_for` converts to `split_sections` space
  exactly where the body is read / replaced; `validate_anchors` always
  receives the outline index.

Contracts (errors, protocols, `VersionRow`, index helpers) live in
`section_history_contracts`; import them from there.
"""

from __future__ import annotations

from typing import Unpack
from uuid import UUID

import structlog

from src.models.content import CanonicalArticle
from src.services.content.section_anchors import validate_anchors
from src.services.content.section_history_contracts import (
    AnchorViolationError,
    ArticleNotFoundError,
    ArticleRepoProtocol,
    PersistResult,
    SectionNotFoundError,
    VersionMeta,
    VersionRepoProtocol,
    VersionRow,
    append_version_row,
    md_index_for,
    outline_index_for,
    parse_section_id,
)
from src.services.content.section_markdown import (
    MarkdownSection,
    get_section,
    replace_section,
)

logger = structlog.get_logger()


class SectionHistoryService:
    """Single Service-Layer entry point used by `/content/*` routes."""

    def __init__(
        self,
        articles: ArticleRepoProtocol,
        versions: VersionRepoProtocol,
    ) -> None:
        self._articles = articles
        self._versions = versions

    async def get_section_markdown(
        self,
        article_id: UUID,
        section_index: int,
    ) -> tuple[CanonicalArticle, MarkdownSection]:
        """Fetch the article + the H2 section at OUTLINE index `section_index`."""
        article = await self._articles.get(article_id)
        if article is None:
            raise ArticleNotFoundError(str(article_id))
        section = None
        if section_index >= 0:
            section = get_section(article.body_markdown, md_index_for(section_index))
        if section is None:
            raise SectionNotFoundError(
                f"section {section_index} of article {article_id} not found"
            )
        return article, section

    async def persist_section_update(
        self,
        *,
        article_id: UUID,
        section_index: int,
        new_section_markdown: str,
        source: str,
        **meta: Unpack[VersionMeta],
    ) -> PersistResult:
        """Validate anchors, swap the OUTLINE section in, append a version row."""
        row = VersionRow(
            article_id=article_id,
            section_index=section_index,
            markdown=new_section_markdown,
            source=source,
            **meta,
        )
        return await self._persist_row(row)

    async def _persist_row(self, row: VersionRow) -> PersistResult:
        article, section = await self.get_section_markdown(
            row.article_id, row.section_index
        )
        _ensure_anchors(article, section, row.markdown)
        updated = await self._swap_section(article, row)
        version_id = await append_version_row(self._versions, row)
        logger.info(
            "section_persisted",
            article_id=str(row.article_id),
            section_index=row.section_index,
            source=row.source,
            version_id=str(version_id),
        )
        return PersistResult(
            article=updated, new_section_markdown=row.markdown, version_id=version_id
        )

    async def _swap_section(
        self, article: CanonicalArticle, row: VersionRow
    ) -> CanonicalArticle:
        """Replace the OUTLINE section in the body and persist it."""
        new_body = replace_section(
            article.body_markdown, md_index_for(row.section_index), row.markdown
        )
        updated = await self._articles.update_body_markdown(article.id, new_body)
        if updated is None:  # race: article deleted between fetch + update
            raise ArticleNotFoundError(str(article.id))
        return updated

    async def list_history(self, section_id: str, limit: int = 50) -> list[object]:
        article_id, _ = parse_section_id(section_id)
        return await self._versions.list_for_section(
            article_id=article_id, section_id=section_id, limit=limit
        )

    async def restore(
        self,
        *,
        section_id: str,
        version_id: UUID,
        created_by: str | None = None,
    ) -> PersistResult:
        """Restore a section to a prior version. Appends a `restore` version row."""
        article_id, section_index = parse_section_id(section_id)
        markdown = await self._version_markdown(version_id)
        return await self.persist_section_update(
            article_id=article_id,
            section_index=section_index,
            new_section_markdown=markdown,
            source="restore",
            instruction=f"restore version {version_id}",
            created_by=created_by,
        )

    async def _version_markdown(self, version_id: UUID) -> str:
        version = await self._versions.get(version_id)
        if version is None:
            raise SectionNotFoundError(f"version {version_id} not found")
        markdown = getattr(version, "markdown", None)
        if not isinstance(markdown, str):
            raise SectionNotFoundError(f"version {version_id} has no markdown payload")
        return markdown


def _ensure_anchors(
    article: CanonicalArticle, section: MarkdownSection, new_markdown: str
) -> None:
    """Run the validator with the OUTLINE index (ImagePlacement.section_index space)."""
    violations = validate_anchors(
        original_markdown=section.text,
        new_markdown=new_markdown,
        image_specs=list(article.image_specs),
        section_index=outline_index_for(section.index),
    )
    if violations:
        raise AnchorViolationError(violations)


__all__ = [
    "AnchorViolationError",
    "ArticleNotFoundError",
    "SectionHistoryService",
    "SectionNotFoundError",
]
