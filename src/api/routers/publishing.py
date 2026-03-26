"""Publishing router — publish articles to external platforms."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.rate_limiter import limiter
from src.api.schemas.publishing import PublishRequest, PublishResponse

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
