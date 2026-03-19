"""Request/response schemas for the articles API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GenerateArticleRequest(BaseModel):
    session_id: UUID


class OutlineSectionResponse(BaseModel):
    index: int
    title: str
    description: str
    key_points: list[str]
    target_word_count: int
    relevant_facets: list[int]


class ArticleOutlineResponse(BaseModel):
    draft_id: UUID
    title: str
    subtitle: str | None
    content_type: str
    sections: list[OutlineSectionResponse]
    total_target_words: int
    reasoning: str
    status: str


class CitationRefResponse(BaseModel):
    index: int
    source_url: str
    source_title: str


class SectionDraftResponse(BaseModel):
    section_index: int
    title: str
    body_markdown: str
    word_count: int
    citations_used: list[CitationRefResponse]


class StructuredDataLDResponse(BaseModel):
    headline: str
    description: str
    keywords: list[str]
    date_published: str
    date_modified: str


class SEOResultResponse(BaseModel):
    title: str
    description: str
    keywords: list[str]
    summary: str
    key_claims: list[str]
    ai_disclosure: str
    structured_data: StructuredDataLDResponse | None = None


class ArticleDraftResponse(BaseModel):
    draft_id: UUID
    session_id: UUID
    status: str
    outline: ArticleOutlineResponse | None
    created_at: datetime
    completed_at: datetime | None
    section_drafts: list[SectionDraftResponse] = []
    citations: list[CitationRefResponse] = []
    total_word_count: int = 0
    seo_result: SEOResultResponse | None = None
