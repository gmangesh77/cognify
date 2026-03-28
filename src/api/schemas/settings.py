"""Request/response schemas for the settings API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# --- Domain schemas ---


class CreateDomainRequest(BaseModel):
    name: str
    status: str = "active"
    trend_sources: list[str] = []
    keywords: list[str] = []


class UpdateDomainRequest(BaseModel):
    name: str | None = None
    status: str | None = None
    trend_sources: list[str] | None = None
    keywords: list[str] | None = None


class DomainResponse(BaseModel):
    id: UUID
    name: str
    status: str
    trend_sources: list[str]
    keywords: list[str]
    article_count: int
    created_at: datetime
    updated_at: datetime


class DomainListResponse(BaseModel):
    items: list[DomainResponse]


# --- API key schemas ---

ApiKeyServiceType = Literal[
    "anthropic",
    "openai",
    "serpapi",
    "ghost",
    "newsapi",
    "arxiv",
    "reddit_client_id",
    "reddit_client_secret",
    "semantic_scholar",
]


class AddApiKeyRequest(BaseModel):
    service: ApiKeyServiceType
    key: str = Field(min_length=10, max_length=500)


class RotateApiKeyRequest(BaseModel):
    key: str = Field(min_length=10, max_length=500)


class ApiKeyResponse(BaseModel):
    id: UUID
    service: str
    masked_key: str
    status: str
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyResponse]


# --- LLM config schemas ---


class UpdateLlmConfigRequest(BaseModel):
    primary_model: str | None = None
    drafting_model: str | None = None
    image_generation: str | None = None


class LlmConfigResponse(BaseModel):
    primary_model: str
    drafting_model: str
    image_generation: str


# --- SEO defaults schemas ---


class UpdateSeoDefaultsRequest(BaseModel):
    auto_meta_tags: bool | None = None
    keyword_optimization: bool | None = None
    auto_cover_images: bool | None = None
    include_citations: bool | None = None
    human_review_before_publish: bool | None = None


class SeoDefaultsResponse(BaseModel):
    auto_meta_tags: bool
    keyword_optimization: bool
    auto_cover_images: bool
    include_citations: bool
    human_review_before_publish: bool


# --- General config schemas ---


class UpdateGeneralConfigRequest(BaseModel):
    article_length_target: str | None = None
    content_tone: str | None = None


class GeneralConfigResponse(BaseModel):
    article_length_target: str
    content_tone: str
