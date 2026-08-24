"""Article metadata editing endpoints (AUTHOR-006).

Separate module because `canonical_articles.py` is already over the
200-line budget (same rationale as `content_regenerate.py` vs
`content.py`). PATCH persists title/subtitle/SEO with advisory length
warnings; the SEO regenerate endpoint proposes a single field without
persisting — the user saves through PATCH.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.errors import CognifyValidationError
from src.api.rate_limiter import limiter
from src.api.routers.canonical_articles import (
    _get_content_service,
    _to_seo_metadata_response,
)
from src.api.schemas.article_metadata import (
    ArticleMetadataPatch,
    ArticleMetadataResponse,
    seo_length_warnings,
)
from src.models.content import CanonicalArticle

logger = structlog.get_logger()

article_metadata_router = APIRouter()


def _build_fields(
    article: CanonicalArticle, patch: ArticleMetadataPatch
) -> dict[str, object]:
    fields: dict[str, object] = {}
    if patch.title is not None:
        fields["title"] = patch.title
    if patch.subtitle is not None:
        fields["subtitle"] = patch.subtitle
    seo_updates: dict[str, object] = {}
    if patch.seo_title is not None:
        seo_updates["title"] = patch.seo_title
    if patch.seo_description is not None:
        seo_updates["description"] = patch.seo_description
    if patch.keywords is not None:
        seo_updates["keywords"] = patch.keywords
    if seo_updates:
        fields["seo"] = article.seo.model_copy(update=seo_updates)
    return fields


def _to_metadata_response(article: CanonicalArticle) -> ArticleMetadataResponse:
    return ArticleMetadataResponse(
        id=article.id,
        title=article.title,
        subtitle=article.subtitle,
        seo=_to_seo_metadata_response(article),
        warnings=seo_length_warnings(article.seo),
    )


@limiter.limit("30/minute")
@article_metadata_router.patch(
    "/articles/{article_id}",
    response_model=ArticleMetadataResponse,
    summary="Edit article title/subtitle/SEO metadata",
)
async def patch_article_metadata(
    request: Request,
    article_id: UUID,
    body: ArticleMetadataPatch,
    user: TokenPayload = Depends(require_editor_or_above),
) -> ArticleMetadataResponse:
    svc = _get_content_service(request)
    article = await svc.get_article(article_id)
    fields = _build_fields(article, body)
    if not fields:
        raise CognifyValidationError("No fields to update")
    updated = await svc.update_article_metadata(article_id, fields)
    return _to_metadata_response(updated)
