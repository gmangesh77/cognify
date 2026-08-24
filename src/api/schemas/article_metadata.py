"""Request/response schemas for article metadata editing (AUTHOR-006)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.api.schemas.articles import SEOMetadataResponse
from src.models.content import SEOMetadata

SEO_TITLE_RANGE = (50, 60)
SEO_DESCRIPTION_RANGE = (150, 160)


class ArticleMetadataPatch(BaseModel):
    """Partial update; caps mirror SEOMetadata so persistence can't 422."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=500)
    seo_title: str | None = Field(default=None, min_length=1, max_length=70)
    seo_description: str | None = Field(default=None, min_length=1, max_length=170)
    keywords: list[str] | None = Field(default=None, max_length=20)


class FieldWarning(BaseModel):
    field: str
    message: str


class ArticleMetadataResponse(BaseModel):
    id: UUID
    title: str
    subtitle: str | None
    seo: SEOMetadataResponse
    warnings: list[FieldWarning]


class SeoRegenerateRequest(BaseModel):
    field: Literal["seo_title", "seo_description", "keywords"]


class SeoRegenerateResponse(BaseModel):
    field: str
    value: str | list[str]
    warnings: list[FieldWarning]


def _range_warning(field: str, length: int, lo: int, hi: int) -> FieldWarning:
    return FieldWarning(
        field=field,
        message=f"{field} is {length} chars; {lo}-{hi} recommended",
    )


def seo_length_warnings(seo: SEOMetadata) -> list[FieldWarning]:
    """Advisory (never blocking) SEO length checks."""
    warnings: list[FieldWarning] = []
    lo, hi = SEO_TITLE_RANGE
    if not lo <= len(seo.title) <= hi:
        warnings.append(_range_warning("seo_title", len(seo.title), lo, hi))
    lo, hi = SEO_DESCRIPTION_RANGE
    if not lo <= len(seo.description) <= hi:
        warnings.append(_range_warning("seo_description", len(seo.description), lo, hi))
    return warnings
