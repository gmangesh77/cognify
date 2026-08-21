"""Section-id contract, index conversion, errors and repo protocols (L-013).

PUBLIC CONTRACT: ``section_id = f"{article_id}:{outline_index}"`` where
``outline_index`` is the 0-based index over H2 sections — the same space as
`ArticleOutline.sections[].index`, `SectionDraft.section_index`,
`ImagePlacement.section_index` and the frontend's `sectionIdx`.

`section_markdown.split_sections` uses a different space: index 0 is ALWAYS
the prelude (possibly empty), so the first H2 is markdown index 1. The two
helpers below are the ONLY place that conversion happens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypedDict
from uuid import UUID

from src.models.content import CanonicalArticle
from src.services.content.section_anchors import AnchorViolation


def md_index_for(outline_index: int) -> int:
    """Outline (0-based H2) index → `split_sections` index (prelude is 0)."""
    return outline_index + 1


def outline_index_for(md_index: int) -> int:
    """Inverse of `md_index_for`."""
    return md_index - 1


def make_section_id(article_id: UUID, outline_index: int) -> str:
    """Stable, schema-free identifier — outline space (L-013)."""
    return f"{article_id}:{outline_index}"


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


class ArticleRepoProtocol(Protocol):
    async def get(self, article_id: UUID) -> CanonicalArticle | None: ...
    async def update_body_markdown(
        self, article_id: UUID, body_markdown: str
    ) -> CanonicalArticle | None: ...


class VersionRepoProtocol(Protocol):
    """Append-only `section_versions` repo (mirrors PgSectionVersionRepository)."""

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


class VersionMeta(TypedDict, total=False):
    """Optional audit columns of a `section_versions` row (PEP 692 kwargs)."""

    instruction: str | None
    model: str | None
    tokens_input: int | None
    tokens_output: int | None
    usd: float | None
    created_by: str | None


@dataclass(frozen=True)
class VersionRow:
    """Inputs for one `section_versions` append (outline-space index)."""

    article_id: UUID
    section_index: int
    markdown: str
    source: str
    instruction: str | None = None
    model: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    usd: float | None = None
    created_by: str | None = None


@dataclass(frozen=True)
class PersistResult:
    """Outcome of `persist_section_update`."""

    article: CanonicalArticle
    new_section_markdown: str
    version_id: UUID


async def append_version_row(repo: VersionRepoProtocol, row: VersionRow) -> UUID:
    """The ONE fan-out from `VersionRow` to the repo's 11-kwarg `append`."""
    version = await repo.append(
        article_id=row.article_id,
        section_id=make_section_id(row.article_id, row.section_index),
        section_index=row.section_index,
        markdown=row.markdown,
        source=row.source,
        instruction=row.instruction,
        model=row.model,
        tokens_input=row.tokens_input,
        tokens_output=row.tokens_output,
        usd=row.usd,
        created_by=row.created_by,
    )
    version_id: UUID = version.id  # type: ignore[attr-defined]
    return version_id


__all__ = [
    "AnchorViolationError",
    "ArticleNotFoundError",
    "ArticleRepoProtocol",
    "PersistResult",
    "SectionNotFoundError",
    "VersionMeta",
    "VersionRepoProtocol",
    "VersionRow",
    "append_version_row",
    "make_section_id",
    "md_index_for",
    "outline_index_for",
    "parse_section_id",
]
