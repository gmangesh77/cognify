"""Section-level edit history service (VISUAL-011 / Phase 8).

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
- Service-Layer pattern: the service depends on repository protocols,
  not concrete classes — keeps unit tests trivial.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import structlog

from src.models.content import CanonicalArticle
from src.services.content.section_anchors import AnchorViolation, validate_anchors
from src.services.content.section_markdown import (
    MarkdownSection,
    get_section,
    replace_section,
)

logger = structlog.get_logger()


def make_section_id(article_id: UUID, section_index: int) -> str:
    """Stable, schema-free identifier per the handoff brief."""
    return f"{article_id}:{section_index}"


def parse_section_id(section_id: str) -> tuple[UUID, int]:
    """Inverse of `make_section_id`. Raises ValueError on malformed input."""
    if ":" not in section_id:
        raise ValueError(f"section_id missing ':' separator: {section_id!r}")
    raw_article, raw_index = section_id.rsplit(":", 1)
    return UUID(raw_article), int(raw_index)


class AnchorViolationError(Exception):
    """Raised when an edit would drop one or more required anchors."""

    def __init__(self, violations: list[AnchorViolation]) -> None:
        self.violations = violations
        super().__init__(f"edit would drop {len(violations)} required anchor(s)")


class SectionNotFoundError(Exception):
    """Raised when the article exists but the section index is out of range."""


class ArticleNotFoundError(Exception):
    """Raised when the article id does not resolve to a CanonicalArticle."""


class _ArticleRepoProtocol(Protocol):
    async def get(self, article_id: UUID) -> CanonicalArticle | None: ...
    async def update_body_markdown(
        self, article_id: UUID, body_markdown: str
    ) -> CanonicalArticle | None: ...


class _VersionRepoProtocol(Protocol):
    async def append(  # noqa: PLR0913 — repo signature, mirrored for typing
        self,
        *,
        article_id: UUID,
        section_id: str,
        section_index: int,
        markdown: str,
        source: str,
        instruction: str | None = None,
        model: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        usd: float | None = None,
        created_by: str | None = None,
    ) -> object: ...

    async def list_for_section(
        self,
        *,
        article_id: UUID,
        section_id: str,
        limit: int = 50,
    ) -> list[object]: ...

    async def get(self, version_id: UUID) -> object | None: ...


@dataclass(frozen=True)
class PersistResult:
    """Outcome of `persist_section_update`."""

    article: CanonicalArticle
    new_section_markdown: str
    version_id: UUID


class SectionHistoryService:
    """Single Service-Layer entry point used by `/content/*` routes."""

    def __init__(
        self,
        articles: _ArticleRepoProtocol,
        versions: _VersionRepoProtocol,
    ) -> None:
        self._articles = articles
        self._versions = versions

    async def get_section_markdown(
        self,
        article_id: UUID,
        section_index: int,
    ) -> tuple[CanonicalArticle, MarkdownSection]:
        """Fetch the article + the addressed section. Raises if missing."""
        article = await self._articles.get(article_id)
        if article is None:
            raise ArticleNotFoundError(str(article_id))
        section = get_section(article.body_markdown, section_index)
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
        instruction: str | None = None,
        model: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        usd: float | None = None,
        created_by: str | None = None,
    ) -> PersistResult:
        """Validate anchors, swap the section in, append a version row."""
        article, section = await self.get_section_markdown(article_id, section_index)
        original_section_text = section.text
        violations = validate_anchors(
            original_markdown=original_section_text,
            new_markdown=new_section_markdown,
            image_specs=list(article.image_specs),
            section_index=section_index,
        )
        if violations:
            raise AnchorViolationError(violations)

        new_body = replace_section(
            article.body_markdown,
            section_index,
            new_section_markdown,
        )
        updated = await self._articles.update_body_markdown(article_id, new_body)
        if updated is None:
            # Race: article was deleted between fetch + update.
            raise ArticleNotFoundError(str(article_id))

        section_id = make_section_id(article_id, section_index)
        version = await self._versions.append(
            article_id=article_id,
            section_id=section_id,
            section_index=section_index,
            markdown=new_section_markdown,
            source=source,
            instruction=instruction,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            usd=usd,
            created_by=created_by,
        )
        version_id = version.id  # type: ignore[attr-defined]
        logger.info(
            "section_persisted",
            article_id=str(article_id),
            section_index=section_index,
            source=source,
            version_id=str(version_id),
        )
        return PersistResult(
            article=updated,
            new_section_markdown=new_section_markdown,
            version_id=version_id,
        )

    async def list_history(
        self,
        section_id: str,
        limit: int = 50,
    ) -> list[object]:
        article_id, _ = parse_section_id(section_id)
        return await self._versions.list_for_section(
            article_id=article_id,
            section_id=section_id,
            limit=limit,
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
        version = await self._versions.get(version_id)
        if version is None:
            raise SectionNotFoundError(f"version {version_id} not found")
        markdown = getattr(version, "markdown", None)
        if not isinstance(markdown, str):
            raise SectionNotFoundError(f"version {version_id} has no markdown payload")
        return await self.persist_section_update(
            article_id=article_id,
            section_index=section_index,
            new_section_markdown=markdown,
            source="restore",
            instruction=f"restore version {version_id}",
            created_by=created_by,
        )


__all__ = [
    "AnchorViolationError",
    "ArticleNotFoundError",
    "PersistResult",
    "SectionHistoryService",
    "SectionNotFoundError",
    "make_section_id",
    "parse_section_id",
]
