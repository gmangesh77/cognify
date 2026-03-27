"""Publishing router — publish articles to external platforms."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.rate_limiter import limiter
from src.api.schemas.publishing import (
    PlatformSummaryResponse,
    PublicationListResponse,
    PublicationResponse,
    PublishRequest,
    PublishResponse,
)

logger = structlog.get_logger()

publishing_router = APIRouter()


@limiter.limit("5/minute")
@publishing_router.post(
    "/articles/{article_id}/publish",
    response_model=PublishResponse,
    status_code=HTTP_201_CREATED,
)
async def publish_article(
    request: Request,
    article_id: UUID,
    body: PublishRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PublishResponse:
    svc = request.app.state.publishing_service
    result = await svc.publish(article_id, body.platform, body.schedule_at)
    logger.info(
        "publish_endpoint_called",
        article_id=str(article_id),
        platform=body.platform,
        status=result.status,
    )
    return PublishResponse(
        article_id=result.article_id,
        platform=result.platform,
        status=result.status,
        external_id=result.external_id,
        external_url=result.external_url,
        published_at=result.published_at,
        error_message=result.error_message,
    )


@limiter.limit("30/minute")
@publishing_router.get(
    "/publications",
    response_model=PublicationListResponse,
)
async def list_publications(
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    platform: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: TokenPayload = Depends(require_viewer_or_above),
) -> PublicationListResponse:
    pub_repo = request.app.state.pub_repo
    article_repo = request.app.state.article_repo
    pubs, total = await pub_repo.list(
        page=page, size=size, platform=platform, status=status,
    )

    items = []
    for pub in pubs:
        article = await article_repo.get(pub.article_id)
        title = article.title if article else "Unknown"
        items.append(
            PublicationResponse(
                id=pub.id,
                article_id=pub.article_id,
                article_title=title,
                platform=pub.platform,
                status=pub.status.value,
                external_id=pub.external_id,
                external_url=pub.external_url,
                published_at=pub.published_at,
                view_count=pub.view_count,
                seo_score=pub.seo_score,
                error_message=pub.error_message,
                event_history=[
                    {
                        "timestamp": e.timestamp,
                        "status": e.status.value,
                        "error_message": e.error_message,
                    }
                    for e in pub.event_history
                ],
                created_at=pub.created_at,
                updated_at=pub.updated_at,
            ),
        )
    return PublicationListResponse(items=items, total=total, page=page, size=size)


@limiter.limit("30/minute")
@publishing_router.get(
    "/publications/summaries",
    response_model=list[PlatformSummaryResponse],
)
async def get_platform_summaries(
    request: Request,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> list[PlatformSummaryResponse]:
    pub_repo = request.app.state.pub_repo
    summaries = await pub_repo.get_platform_summaries()
    return [
        PlatformSummaryResponse(
            platform=s.platform,
            total=s.total,
            success=s.success,
            failed=s.failed,
            scheduled=s.scheduled,
        )
        for s in summaries
    ]


@limiter.limit("30/minute")
@publishing_router.get(
    "/publications/{publication_id}",
    response_model=PublicationResponse,
)
async def get_publication(
    request: Request,
    publication_id: UUID,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> PublicationResponse:
    pub_repo = request.app.state.pub_repo
    article_repo = request.app.state.article_repo
    pub = await pub_repo.get(publication_id)
    if pub is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    article = await article_repo.get(pub.article_id)
    title = article.title if article else "Unknown"
    return PublicationResponse(
        id=pub.id,
        article_id=pub.article_id,
        article_title=title,
        platform=pub.platform,
        status=pub.status.value,
        external_id=pub.external_id,
        external_url=pub.external_url,
        published_at=pub.published_at,
        view_count=pub.view_count,
        seo_score=pub.seo_score,
        error_message=pub.error_message,
        event_history=[
            {
                "timestamp": e.timestamp,
                "status": e.status.value,
                "error_message": e.error_message,
            }
            for e in pub.event_history
        ],
        created_at=pub.created_at,
        updated_at=pub.updated_at,
    )


@limiter.limit("5/minute")
@publishing_router.post(
    "/publications/{publication_id}/retry",
    response_model=PublishResponse,
)
async def retry_publication(
    request: Request,
    publication_id: UUID,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PublishResponse:
    svc = request.app.state.publishing_service
    try:
        result = await svc.retry(publication_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PublishResponse(
        article_id=result.article_id,
        platform=result.platform,
        status=result.status,
        external_id=result.external_id,
        external_url=result.external_url,
        published_at=result.published_at,
        error_message=result.error_message,
    )
