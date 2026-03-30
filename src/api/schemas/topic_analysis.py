"""Schemas for topic analysis API."""

from pydantic import BaseModel, Field

VALID_TONES = [
    "technical-authoritative",
    "conversational",
    "educational",
    "analytical",
    "news-reporting",
]


class TopicAnalysisResult(BaseModel):
    """LLM-suggested metadata for a topic."""

    description: str
    domain: str
    keywords: list[str] = Field(max_length=10)
    target_audience: str
    content_tone: str
    preferred_angle: str


class AnalyzeTopicRequest(BaseModel):
    """Request body for POST /topics/analyze."""

    title: str = Field(min_length=3, max_length=500)
    regenerate_field: str | None = None
    current_values: TopicAnalysisResult | None = None
