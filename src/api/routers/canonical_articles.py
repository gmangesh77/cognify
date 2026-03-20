"""Canonical article API endpoints — finalize and retrieve."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.errors import BadRequestError
from src.api.rate_limiter import limiter
from src.api.schemas.articles import (
    CanonicalArticleResponse,
    CitationResponse,
    ImageAssetResponse,
    ProvenanceResponse,
    SEOMetadataResponse,
    StructuredDataLDResponse,
)
from src.models.content import (
    CanonicalArticle,
    Citation,
    ImageAsset,
    StructuredDataLD,
)
from src.services.content import ContentService

logger = structlog.get_logger()

canonical_articles_router = APIRouter()


def _get_content_service(request: Request) -> ContentService:
    return request.app.state.content_service  # type: ignore[no-any-return]


@limiter.limit("3/minute")
@canonical_articles_router.post(
    "/articles/drafts/{draft_id}/finalize",
    response_model=CanonicalArticleResponse,
    status_code=HTTP_201_CREATED,
)
async def finalize_article(
    request: Request,
    draft_id: str,
    user: TokenPayload = Depends(require_editor_or_above),
) -> CanonicalArticleResponse:
    """Finalize a completed draft into a CanonicalArticle."""
    svc = _get_content_service(request)
    try:
        article = await svc.finalize_article(UUID(draft_id))
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    return _to_canonical_response(article)


@limiter.limit("30/minute")
@canonical_articles_router.get(
    "/articles/{article_id}",
    response_model=CanonicalArticleResponse,
)
async def get_article(
    request: Request,
    article_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> CanonicalArticleResponse:
    """Retrieve a stored CanonicalArticle by ID."""
    svc = _get_content_service(request)
    article = await svc.get_article(UUID(article_id))
    return _to_canonical_response(article)


def _to_canonical_response(
    article: CanonicalArticle,
) -> CanonicalArticleResponse:
    """Map a CanonicalArticle domain model to its API response."""
    return CanonicalArticleResponse(
        id=article.id,
        title=article.title,
        subtitle=article.subtitle,
        body_markdown=article.body_markdown,
        summary=article.summary,
        key_claims=list(article.key_claims),
        content_type=article.content_type.value,
        seo=_to_seo_metadata_response(article),
        citations=[_to_citation_response(c) for c in article.citations],
        visuals=[_to_image_response(v) for v in article.visuals],
        authors=list(article.authors),
        domain=article.domain,
        generated_at=article.generated_at,
        provenance=_to_provenance_response(article),
        ai_generated=article.ai_generated,
    )


def _to_seo_metadata_response(
    article: CanonicalArticle,
) -> SEOMetadataResponse:
    """Map SEOMetadata to its response schema."""
    sd = article.seo.structured_data
    sd_resp = _to_sd_response(sd) if sd else None
    return SEOMetadataResponse(
        title=article.seo.title,
        description=article.seo.description,
        keywords=list(article.seo.keywords),
        canonical_url=article.seo.canonical_url,
        structured_data=sd_resp,
    )


def _to_sd_response(sd: StructuredDataLD) -> StructuredDataLDResponse:
    """Map StructuredDataLD to its response schema."""
    return StructuredDataLDResponse(
        headline=sd.headline,
        description=sd.description,
        keywords=list(sd.keywords),
        date_published=sd.date_published,
        date_modified=sd.date_modified,
    )


def _to_citation_response(c: Citation) -> CitationResponse:
    """Map a Citation model to its response schema."""
    return CitationResponse(
        index=c.index,
        title=c.title,
        url=c.url,
        authors=list(c.authors),
        published_at=c.published_at,
    )


def _to_image_response(v: ImageAsset) -> ImageAssetResponse:
    """Map an ImageAsset model to its response schema."""
    return ImageAssetResponse(
        id=v.id,
        url=v.url,
        caption=v.caption,
        alt_text=v.alt_text,
    )


def _to_provenance_response(
    article: CanonicalArticle,
) -> ProvenanceResponse:
    """Map Provenance to its response schema."""
    p = article.provenance
    return ProvenanceResponse(
        research_session_id=p.research_session_id,
        primary_model=p.primary_model,
        drafting_model=p.drafting_model,
        embedding_model=p.embedding_model,
        embedding_version=p.embedding_version,
    )
