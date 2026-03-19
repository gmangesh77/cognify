"""Content pipeline models — the canonical article boundary.

These models define the contract between content generation (Epics 2-4)
and publishing (Epic 5). See ADR-003 for rationale.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ContentType(StrEnum):
    """Article content type. Maps to Schema.org @type in platform transformers."""

    ARTICLE = "article"
    HOW_TO = "how-to"
    ANALYSIS = "analysis"
    REPORT = "report"


class SchemaOrgAuthor(BaseModel, frozen=True):
    """Schema.org author for JSON-LD."""

    type: str = Field(default="Organization", alias="@type")
    name: str = "Cognify"

    model_config = ConfigDict(populate_by_name=True)


class StructuredDataLD(BaseModel, frozen=True):
    """Typed JSON-LD Schema.org Article structured data."""

    context: str = Field(default="https://schema.org", alias="@context")
    type: str = Field(default="Article", alias="@type")
    headline: str
    description: str
    keywords: list[str] = Field(default_factory=list)
    author: SchemaOrgAuthor = Field(default_factory=SchemaOrgAuthor)
    date_published: str = Field(alias="datePublished")
    date_modified: str = Field(alias="dateModified")

    model_config = ConfigDict(populate_by_name=True)


class SEOMetadata(BaseModel):
    """Platform-neutral SEO defaults."""

    title: str = Field(min_length=1, max_length=70)
    description: str = Field(min_length=1, max_length=170)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    canonical_url: str | None = None
    structured_data: StructuredDataLD | None = None


class Citation(BaseModel):
    """Source reference for inline citations."""

    index: int = Field(ge=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None


class ImageAsset(BaseModel):
    """Reference to a visual asset (chart, illustration, diagram)."""

    id: UUID = Field(default_factory=uuid4)
    url: str = Field(min_length=1)
    caption: str | None = None
    alt_text: str | None = None
    metadata: dict[str, str | int | float] = Field(default_factory=dict)


class Provenance(BaseModel):
    """Tracks which models and versions produced the article."""

    research_session_id: UUID
    primary_model: str = Field(min_length=1)
    drafting_model: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    embedding_version: str = Field(min_length=1)


class CanonicalArticle(BaseModel):
    """The central content pipeline contract.

    Output of content generation, input to all publishing transformers.
    Frozen after construction — downstream consumers must not mutate it.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = None
    body_markdown: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=500)
    key_claims: list[str] = Field(min_length=1, max_length=10)
    content_type: ContentType
    seo: SEOMetadata
    citations: list[Citation] = Field(min_length=1)
    visuals: list[ImageAsset] = Field(default_factory=list)
    authors: list[str] = Field(min_length=1)
    domain: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provenance: Provenance
    ai_generated: bool = True
