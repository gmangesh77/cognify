from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RawTopic(BaseModel):
    title: str
    description: str = ""
    source: str
    external_url: str = ""
    trend_score: float = Field(ge=0, le=100)
    discovered_at: datetime
    velocity: float = Field(ge=0, default=0)
    domain_keywords: list[str] = Field(default_factory=list)


class RankedTopic(RawTopic):
    composite_score: float
    rank: int
    source_count: int


class DuplicateInfo(BaseModel):
    title: str
    source: str
    duplicate_of: str
    similarity: float


class RankTopicsRequest(BaseModel):
    topics: list[RawTopic] = Field(min_length=1, max_length=500)
    domain: str
    domain_keywords: list[str] = Field(default_factory=list)
    top_n: int = Field(default=10, ge=1, le=100)


class RankTopicsResponse(BaseModel):
    ranked_topics: list[RankedTopic]
    duplicates_removed: list[DuplicateInfo]
    total_input: int
    total_after_dedup: int
    total_returned: int


class PersistedTopic(BaseModel):
    """Topic persisted in the database with cross-scan metadata."""

    id: UUID
    title: str
    description: str
    source: str
    external_url: str
    trend_score: float
    velocity: float
    domain: str
    discovered_at: datetime
    composite_score: float | None = None
    rank: int | None = None
    source_count: int = 1
    created_at: datetime
    updated_at: datetime


class PersistTopicsRequest(BaseModel):
    ranked_topics: list[RankedTopic]
    domain: str


class PersistTopicsResponse(BaseModel):
    new_count: int
    updated_count: int
    total_persisted: int
    topic_ids: list[str] = Field(default_factory=list)


class PaginatedTopics(BaseModel):
    items: list[PersistedTopic]
    total: int
    page: int
    size: int
