"""Request/response schemas for the publishing API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PublishRequest(BaseModel):
    platform: str = Field(min_length=1)
    schedule_at: datetime | None = None


class PublishResponse(BaseModel):
    article_id: UUID
    platform: str
    status: str
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    error_message: str | None = None
