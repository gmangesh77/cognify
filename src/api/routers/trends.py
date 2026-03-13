import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.trends import HNFetchRequest, HNFetchResponse
from src.services.hackernews import HackerNewsService
from src.services.hackernews_client import (
    HackerNewsAPIError,
    HackerNewsClient,
)

logger = structlog.get_logger()

trends_router = APIRouter()


def _get_hn_service(request: Request) -> HackerNewsService:
    settings = request.app.state.settings
    # Test injection: tests set app.state.hn_client to a mock.
    # In production, a fresh short-lived client is created per request.
    if hasattr(request.app.state, "hn_client"):
        client = request.app.state.hn_client
    else:
        client = HackerNewsClient(
            base_url=settings.hn_api_base_url,
            timeout=settings.hn_request_timeout,
        )
    return HackerNewsService(
        client=client,
        points_cap=settings.hn_points_cap,
    )


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/hackernews/fetch",
    response_model=HNFetchResponse,
    summary="Fetch trending HN stories",
)
async def fetch_hackernews(
    request: Request,
    body: HNFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> HNFetchResponse:
    service = _get_hn_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            max_results=body.max_results,
            min_points=body.min_points,
        )
    except HackerNewsAPIError as exc:
        logger.error(
            "hackernews_api_error",
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="hackernews_unavailable",
            message="Hacker News API is not available",
        ) from exc
