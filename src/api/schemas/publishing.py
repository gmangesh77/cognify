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


class PublicationEventResponse(BaseModel):
    timestamp: datetime
    status: str
    error_message: str | None = None


class PublicationResponse(BaseModel):
    id: UUID
    article_id: UUID
    article_title: str
    platform: str
    status: str
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    view_count: int = 0
    seo_score: int = 0
    error_message: str | None = None
    event_history: list[PublicationEventResponse] = []
    created_at: datetime
    updated_at: datetime


class PublicationListResponse(BaseModel):
    items: list[PublicationResponse]
    total: int
    page: int
    size: int


class PlatformSummaryResponse(BaseModel):
    platform: str
    total: int
    success: int
    failed: int
    scheduled: int
