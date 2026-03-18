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


class ArticleDraftResponse(BaseModel):
    draft_id: UUID
    session_id: UUID
    status: str
    outline: ArticleOutlineResponse | None
    created_at: datetime
    completed_at: datetime | None
