"""Request/response schemas for the outline review API (AUTHOR-002)."""

from uuid import UUID

from pydantic import BaseModel, Field

from src.models.content_pipeline import ArticleOutline


class OutlineResponse(BaseModel):
    draft_id: UUID
    session_id: UUID
    status: str
    outline: ArticleOutline


class RegenerateOutlineRequest(BaseModel):
    instruction: str | None = Field(default=None, max_length=2000)


class SessionActionResponse(BaseModel):
    session_id: UUID
    status: str
