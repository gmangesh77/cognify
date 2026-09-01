"""Article metadata editing endpoints (AUTHOR-006).

Separate module because `canonical_articles.py` is already over the
200-line budget (same rationale as `content_regenerate.py` vs
`content.py`). PATCH persists title/subtitle/SEO with advisory length
warnings; the SEO regenerate endpoint proposes a single field without
persisting — the user saves through PATCH.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request

from src.agents.prompts import bind_prompt_overrides
from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.errors import CognifyValidationError, ServiceUnavailableError
from src.api.prompt_scope import load_prompt_overrides
from src.api.rate_limiter import limiter
from src.api.routers.canonical_articles import (
    _get_content_service,
    _to_seo_metadata_response,
)
from src.api.schemas.article_metadata import (
    ArticleMetadataPatch,
    ArticleMetadataResponse,
    SeoRegenerateRequest,
    SeoRegenerateResponse,
    seo_length_warnings,
)
from src.models.content import CanonicalArticle, SEOMetadata
from src.services.content import ContentService
from src.utils.tracked_llm import current_session_id, current_step_name

logger = structlog.get_logger()

article_metadata_router = APIRouter()


def _build_fields(
    article: CanonicalArticle, patch: ArticleMetadataPatch
) -> dict[str, object]:
    fields: dict[str, object] = {}
    if patch.title is not None:
        fields["title"] = patch.title
    # model_fields_set distinguishes {"subtitle": null} (clear) from absent
    # (the AUTHOR-003 PATCH flaw — fixed here for the new endpoint).
    if "subtitle" in patch.model_fields_set:
        fields["subtitle"] = patch.subtitle
    if patch.status is not None:
        fields["status"] = patch.status
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
        status=article.status.value,
        seo=_to_seo_metadata_response(article),
        warnings=seo_length_warnings(article.seo),
    )


# NOTE decorator order: the route decorator must be OUTERMOST and
# @limiter.limit closest to the function, or slowapi never evaluates the
# per-route limit (caught in review; canonical_articles.py/briefs.py have
# the same latent bug — follow-up filed).
@article_metadata_router.patch(
    "/articles/{article_id}",
    response_model=ArticleMetadataResponse,
    summary="Edit article title/subtitle/SEO metadata",
)
@limiter.limit("30/minute")
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


async def _regenerate_seo(
    svc: ContentService, article: CanonicalArticle
) -> SEOMetadata:
    """One tracked LLM call; bound to the draft's REAL session id (L-013)."""
    from src.agents.content.seo_optimizer import generate_seo_metadata

    llm = svc.deps.llm
    if llm is None:
        raise ServiceUnavailableError(
            message="LLM not configured. Set COGNIFY_ANTHROPIC_API_KEY."
        )
    draft = await svc.repos.drafts.find_by_article_id(article.id)
    if draft is None:
        return await generate_seo_metadata(article.title, article.body_markdown, llm)
    session_token = current_session_id.set(draft.session_id)
    step_token = current_step_name.set("seo_regenerate")
    try:
        return await generate_seo_metadata(article.title, article.body_markdown, llm)
    finally:
        current_step_name.reset(step_token)
        current_session_id.reset(session_token)


@article_metadata_router.post(
    "/articles/{article_id}/seo/regenerate",
    response_model=SeoRegenerateResponse,
    summary="Propose a regenerated SEO field (not persisted)",
)
@limiter.limit("10/minute")
async def regenerate_seo_field(
    request: Request,
    article_id: UUID,
    body: SeoRegenerateRequest,
    user: TokenPayload = Depends(require_editor_or_above),
    overrides: Mapping[str, str] = Depends(load_prompt_overrides),
) -> SeoRegenerateResponse:
    svc = _get_content_service(request)
    article = await svc.get_article(article_id)
    with bind_prompt_overrides(overrides):
        seo = await _regenerate_seo(svc, article)
    seo_field = {"seo_title": "title", "seo_description": "description"}.get(
        body.field, "keywords"
    )
    value: str | list[str] = getattr(seo, seo_field)
    proposed = article.seo.model_copy(update={seo_field: value})
    warnings = [w for w in seo_length_warnings(proposed) if w.field == body.field]
    return SeoRegenerateResponse(field=body.field, value=value, warnings=warnings)
