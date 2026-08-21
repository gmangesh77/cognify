"""Schemas for topic analysis API."""

from pydantic import BaseModel, Field

from src.api.schemas.topics import PersistedTopic
from src.models.brief import BriefCreate
from src.models.tones import (
    VALID_TONES,  # noqa: F401 — re-exported for existing importers
)


class TopicAnalysisResult(BaseModel):
    """LLM-suggested metadata for a topic."""

    description: str
    domain: str
    keywords: list[str] = Field(max_length=10)
    target_audience: str
    content_tone: str
    preferred_angle: str
    suggested_brief: BriefCreate | None = None


class AnalyzeTopicRequest(BaseModel):
    """Request body for POST /topics/analyze."""

    title: str = Field(min_length=3, max_length=500)
    regenerate_field: str | None = None
    current_values: TopicAnalysisResult | None = None


class ManualTopicCreateRequest(BaseModel):
    """Request body for POST /topics."""

    title: str = Field(min_length=3, max_length=500)
    description: str = Field(max_length=2000)
    domain: str = Field(max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    force_create: bool = False


class ManualTopicResult(BaseModel):
    """Response for POST /topics."""

    topic: PersistedTopic
    is_duplicate: bool = False
    duplicate_of: str | None = None
