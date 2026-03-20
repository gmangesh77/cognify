from pydantic import BaseModel, Field

from src.api.schemas.topics import RawTopic


class TrendFetchRequest(BaseModel):
    """Request body for the unified trend fetch endpoint."""

    domain_keywords: list[str] = Field(min_length=1)
    max_results: int = Field(default=30, ge=1, le=100)
    sources: list[str] | None = Field(
        default=None,
        description="Sources to query. None = all active sources.",
    )


class SourceResult(BaseModel):
    """Per-source result metadata."""

    source_name: str
    topics: list[RawTopic]
    topic_count: int
    duration_ms: int
    error: str | None = None


class TrendFetchResponse(BaseModel):
    """Unified response combining results from multiple sources."""

    topics: list[RawTopic]
    sources_queried: list[str]
    source_results: dict[str, SourceResult]
