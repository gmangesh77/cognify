"""Pydantic domain models for settings (domain config, API keys, LLM, SEO, general)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DomainConfig(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    status: str = "active"
    trend_sources: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    article_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApiKeyConfig(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    service: str
    masked_key: str = ""
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LlmConfig(BaseModel):
    primary_model: str = "claude-opus-4"
    drafting_model: str = "claude-sonnet-4"
    image_generation: str = "stable-diffusion-xl"


class SeoDefaults(BaseModel):
    auto_meta_tags: bool = True
    keyword_optimization: bool = True
    auto_cover_images: bool = True
    include_citations: bool = True
    human_review_before_publish: bool = True


class GeneralConfig(BaseModel):
    article_length_target: str = "3000-5000"
    content_tone: str = "professional"
