"""Content pipeline models — outline generation and article drafting.

Intermediate models for the content pipeline stages (CONTENT-001 through
CONTENT-004). Not part of the final CanonicalArticle contract.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.content import ContentType, ImageAsset, Provenance, SEOMetadata


class DraftStatus(StrEnum):
    """Valid article draft statuses."""

    OUTLINE_GENERATING = "outline_generating"
    OUTLINE_COMPLETE = "outline_complete"
    DRAFTING = "drafting"
    DRAFT_COMPLETE = "draft_complete"
    COMPLETE = "complete"
    FAILED = "failed"


class OutlineSection(BaseModel, frozen=True):
    """A single section in an article outline."""

    index: int
    title: str
    description: str
    key_points: list[str]
    target_word_count: int
    relevant_facets: list[int]


class ArticleOutline(BaseModel, frozen=True):
    """LLM-generated article outline from research findings."""

    title: str
    subtitle: str | None = None
    content_type: ContentType
    sections: list[OutlineSection]
    total_target_words: int
    reasoning: str


class CitationRef(BaseModel, frozen=True):
    """Lightweight citation reference collected during drafting."""

    index: int
    source_url: str
    source_title: str
    published_at: datetime | None = None
    author: str | None = None


class SectionQueries(BaseModel, frozen=True):
    """Retrieval queries generated for one outline section."""

    section_index: int
    queries: list[str]


class SectionDraft(BaseModel, frozen=True):
    """Drafted content for one article section."""

    section_index: int
    title: str
    body_markdown: str
    word_count: int
    citations_used: list[CitationRef]


class AIDiscoverabilityResult(BaseModel, frozen=True):
    """LLM-extracted summary and key claims."""

    summary: str = Field(max_length=500)
    key_claims: list[str] = Field(min_length=1, max_length=10)


class SEOResult(BaseModel, frozen=True):
    """Output of the seo_optimize pipeline node."""

    seo: SEOMetadata
    summary: str
    key_claims: list[str]
    provenance: Provenance
    ai_disclosure: str


class Violation(BaseModel, frozen=True):
    """A single slop violation with location context."""

    category: str
    phrase: str
    sentence_index: int


class SlopScore(BaseModel, frozen=True):
    """Slop detection score for a text section."""

    score: int
    rating: str
    violations: list[Violation]
    phrase_deductions: int
    pattern_deductions: int


class ArticleDraft(BaseModel):
    """Tracks article generation state."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    topic_id: UUID
    outline: ArticleOutline | None = None
    status: DraftStatus = DraftStatus.OUTLINE_GENERATING
    created_at: datetime
    completed_at: datetime | None = None
    section_drafts: list[SectionDraft] = Field(default_factory=list)
    citations: list[CitationRef] = Field(default_factory=list)
    total_word_count: int = 0
    seo_result: SEOResult | None = None
    article_id: UUID | None = None
    global_citations: list[dict[str, object]] = Field(default_factory=list)
    references_markdown: str = ""
    visuals: list[ImageAsset] = Field(default_factory=list)
