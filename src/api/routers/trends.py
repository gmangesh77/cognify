import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.trends import (
    ArxivFetchRequest,
    ArxivFetchResponse,
    GTFetchRequest,
    GTFetchResponse,
    HNFetchRequest,
    HNFetchResponse,
    NewsAPIFetchRequest,
    NewsAPIFetchResponse,
    RedditFetchRequest,
    RedditFetchResponse,
)
from src.services.arxiv import ArxivService
from src.services.arxiv_client import (
    ArxivAPIError,
    ArxivClient,
)
from src.services.google_trends import GoogleTrendsService
from src.services.google_trends_client import (
    GoogleTrendsAPIError,
    GoogleTrendsClient,
)
from src.services.hackernews import HackerNewsService
from src.services.hackernews_client import (
    HackerNewsAPIError,
    HackerNewsClient,
)
from src.services.newsapi import NewsAPIService
from src.services.newsapi_client import (
    NewsAPIClient,
    NewsAPIError,
)
from src.services.reddit import RedditService
from src.services.reddit_client import (
    RedditAPIError,
    RedditClient,
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


def _get_gt_service(request: Request) -> GoogleTrendsService:
    settings = request.app.state.settings
    # Test injection: tests set app.state.gt_client to a mock.
    # In production, a fresh short-lived client is created per request.
    if hasattr(request.app.state, "gt_client"):
        client = request.app.state.gt_client
    else:
        client = GoogleTrendsClient(
            language=settings.gt_language,
            timezone_offset=settings.gt_timezone_offset,
            timeout=settings.gt_request_timeout,
        )
    return GoogleTrendsService(client=client)


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


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/google/fetch",
    response_model=GTFetchResponse,
    summary="Fetch Google Trends topics",
)
async def fetch_google_trends(
    request: Request,
    body: GTFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> GTFetchResponse:
    service = _get_gt_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            country=body.country,
            max_results=body.max_results,
        )
    except GoogleTrendsAPIError as exc:
        logger.error(
            "google_trends_api_error",
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="google_trends_unavailable",
            message="Google Trends API is not available",
        ) from exc


def _get_reddit_service(request: Request) -> RedditService:
    settings = request.app.state.settings
    # Test injection: tests set app.state.reddit_client to a mock.
    # In production, a fresh short-lived client is created per request.
    if hasattr(request.app.state, "reddit_client"):
        client = request.app.state.reddit_client
    else:
        client = RedditClient(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            timeout=settings.reddit_request_timeout,
        )
    return RedditService(
        client=client,
        score_cap=settings.reddit_score_cap,
    )


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/reddit/fetch",
    response_model=RedditFetchResponse,
    summary="Fetch trending Reddit posts",
)
async def fetch_reddit(
    request: Request,
    body: RedditFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> RedditFetchResponse:
    settings = request.app.state.settings
    subreddits = body.subreddits or settings.reddit_default_subreddits
    service = _get_reddit_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            subreddits=subreddits,
            max_results=body.max_results,
            sort=body.sort,
            time_filter=body.time_filter,
        )
    except RedditAPIError as exc:
        logger.error(
            "reddit_api_error",
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="reddit_unavailable",
            message="Reddit API is not available",
        ) from exc


def _get_newsapi_service(request: Request) -> NewsAPIService:
    settings = request.app.state.settings
    if hasattr(request.app.state, "newsapi_client"):
        client = request.app.state.newsapi_client
    else:
        client = NewsAPIClient(
            api_key=settings.newsapi_api_key,
            base_url=settings.newsapi_base_url,
            timeout=settings.newsapi_request_timeout,
        )
    return NewsAPIService(client=client)


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/newsapi/fetch",
    response_model=NewsAPIFetchResponse,
    summary="Fetch trending NewsAPI headlines",
)
async def fetch_newsapi(
    request: Request,
    body: NewsAPIFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> NewsAPIFetchResponse:
    service = _get_newsapi_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            category=body.category,
            country=body.country,
            max_results=body.max_results,
        )
    except NewsAPIError as exc:
        logger.error(
            "newsapi_api_error",
            error=str(exc),
            category=body.category,
            country=body.country,
        )
        raise ServiceUnavailableError(
            code="newsapi_unavailable",
            message="NewsAPI is not available",
        ) from exc


def _get_arxiv_service(request: Request) -> ArxivService:
    settings = request.app.state.settings
    if hasattr(request.app.state, "arxiv_client"):
        client = request.app.state.arxiv_client
    else:
        client = ArxivClient(
            base_url=settings.arxiv_api_base_url,
            timeout=settings.arxiv_request_timeout,
        )
    return ArxivService(client=client)


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/arxiv/fetch",
    response_model=ArxivFetchResponse,
    summary="Fetch trending arXiv papers",
)
async def fetch_arxiv(
    request: Request,
    body: ArxivFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> ArxivFetchResponse:
    service = _get_arxiv_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            categories=body.categories,
            max_results=body.max_results,
        )
    except ArxivAPIError as exc:
        logger.error(
            "arxiv_api_error",
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="arxiv_unavailable",
            message="arXiv API is not available",
        ) from exc
