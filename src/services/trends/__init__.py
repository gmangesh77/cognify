from src.config.settings import Settings
from src.services.trends.arxiv import ArxivService
from src.services.trends.arxiv_client import ArxivClient
from src.services.trends.google_trends import GoogleTrendsService
from src.services.trends.google_trends_client import GoogleTrendsClient
from src.services.trends.hackernews import HackerNewsService
from src.services.trends.hackernews_client import HackerNewsClient
from src.services.trends.newsapi import NewsAPIService
from src.services.trends.newsapi_client import NewsAPIClient
from src.services.trends.protocol import TrendFetchConfig, TrendSource, TrendSourceError
from src.services.trends.reddit import RedditFetchDefaults, RedditService
from src.services.trends.reddit_client import RedditClient
from src.services.trends.registry import TrendSourceRegistry

__all__ = [
    "TrendFetchConfig",
    "TrendSource",
    "TrendSourceError",
    "TrendSourceRegistry",
    "init_registry",
]


def _register_hackernews(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = HackerNewsClient(
        base_url=settings.hn_api_base_url,
        timeout=settings.hn_request_timeout,
    )
    registry.register(HackerNewsService(
        client=client,
        points_cap=settings.hn_points_cap,
        min_points=settings.hn_default_min_points,
    ))


def _register_google_trends(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = GoogleTrendsClient(
        language=settings.gt_language,
        timezone_offset=settings.gt_timezone_offset,
        timeout=settings.gt_request_timeout,
    )
    registry.register(GoogleTrendsService(
        client=client,
        country=settings.gt_default_country,
    ))


def _register_reddit(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = RedditClient(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
        timeout=settings.reddit_request_timeout,
    )
    defaults = RedditFetchDefaults(
        subreddits=settings.reddit_default_subreddits,
        sort="hot",
        time_filter="day",
    )
    registry.register(RedditService(
        client=client,
        score_cap=settings.reddit_score_cap,
        defaults=defaults,
    ))


def _register_newsapi(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = NewsAPIClient(
        api_key=settings.newsapi_api_key,
        base_url=settings.newsapi_base_url,
        timeout=settings.newsapi_request_timeout,
    )
    registry.register(NewsAPIService(
        client=client,
        category=settings.newsapi_default_category,
        country=settings.newsapi_default_country,
    ))


def _register_arxiv(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = ArxivClient(
        base_url=settings.arxiv_api_base_url,
        timeout=settings.arxiv_request_timeout,
    )
    registry.register(ArxivService(
        client=client,
        categories=settings.arxiv_default_categories,
    ))


def init_registry(settings: Settings) -> TrendSourceRegistry:
    """Construct all trend sources from settings."""
    registry = TrendSourceRegistry()
    _register_hackernews(registry, settings)
    _register_google_trends(registry, settings)
    _register_reddit(registry, settings)
    _register_newsapi(registry, settings)
    _register_arxiv(registry, settings)
    return registry
