"""Article generation API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.rate_limiter import limiter
from src.api.schemas.articles import (
    ArticleDraftResponse,
    ArticleOutlineResponse,
    GenerateArticleRequest,
    OutlineSectionResponse,
)
from src.models.content_pipeline import ArticleDraft
from src.services.content import ContentService

logger = structlog.get_logger()

articles_router = APIRouter()


def _get_content_service(request: Request) -> ContentService:
    return request.app.state.content_service  # type: ignore[no-any-return]


@limiter.limit("3/minute")
@articles_router.post(
    "/articles/generate",
    response_model=ArticleOutlineResponse,
    status_code=HTTP_201_CREATED,
)
async def generate_article(
    request: Request,
    body: GenerateArticleRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> ArticleOutlineResponse:
    svc = _get_content_service(request)
    draft = await svc.generate_outline(body.session_id)
    return _to_outline_response(draft)


@limiter.limit("30/minute")
@articles_router.get(
    "/articles/drafts/{draft_id}",
    response_model=ArticleDraftResponse,
)
async def get_draft(
    request: Request,
    draft_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> ArticleDraftResponse:
    svc = _get_content_service(request)
    draft = await svc.get_draft(UUID(draft_id))
    outline_resp = _to_outline_response(draft) if draft.outline else None
    return ArticleDraftResponse(
        draft_id=draft.id,
        session_id=draft.session_id,
        status=draft.status,
        outline=outline_resp,
        created_at=draft.created_at,
        completed_at=draft.completed_at,
    )


def _to_outline_response(draft: ArticleDraft) -> ArticleOutlineResponse:
    """Convert ArticleDraft to ArticleOutlineResponse."""
    o = draft.outline
    if o is None:
        msg = "Draft has no outline"
        raise ValueError(msg)
    sections = [
        OutlineSectionResponse(
            index=s.index,
            title=s.title,
            description=s.description,
            key_points=list(s.key_points),
            target_word_count=s.target_word_count,
            relevant_facets=list(s.relevant_facets),
        )
        for s in o.sections
    ]
    return ArticleOutlineResponse(
        draft_id=draft.id,
        title=o.title,
        subtitle=o.subtitle,
        content_type=o.content_type,
        sections=sections,
        total_target_words=o.total_target_words,
        reasoning=o.reasoning,
        status=draft.status,
    )
