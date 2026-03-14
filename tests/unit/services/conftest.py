import hashlib

from src.services.embeddings import EmbeddingService
from src.services.google_trends_client import (
    GoogleTrendsClient,
    GTRelatedQuery,
    GTTrendingSearch,
)
from src.services.hackernews_client import HackerNewsClient, HNStoryResponse
from src.services.arxiv_client import ArxivClient, ArxivPaper
from src.services.newsapi_client import NewsAPIArticle, NewsAPIClient
from src.services.reddit_client import RedditClient, RedditPostResponse

VECTOR_DIM = 384


class MockEmbeddingService(EmbeddingService):
    """Deterministic mock: texts with 'duplicate-A' get the same vector,
    texts with 'duplicate-B' get another, all others get unique vectors."""

    def __init__(self) -> None:
        super().__init__(model_name="mock")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            if "duplicate-A" in text:
                vec = [0.0] * VECTOR_DIM
                vec[0] = 1.0
            elif "duplicate-B" in text:
                vec = [0.0] * VECTOR_DIM
                vec[1] = 1.0
            else:
                h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
                idx = h % VECTOR_DIM
                vec = [0.0] * VECTOR_DIM
                vec[idx] = 1.0
            vectors.append(vec)
        return vectors


class MockHackerNewsClient(HackerNewsClient):
    """Returns canned stories for deterministic testing."""

    def __init__(
        self,
        stories: list[HNStoryResponse] | None = None,
    ) -> None:
        super().__init__(base_url="http://mock", timeout=1.0)
        self._stories = stories or []

    async def fetch_stories(
        self,
        query: str,
        min_points: int,
        num_results: int,
    ) -> list[HNStoryResponse]:
        return self._stories[:num_results]


class MockRedditClient(RedditClient):
    """Returns canned posts per subreddit for deterministic testing."""

    def __init__(
        self,
        posts: dict[str, list[RedditPostResponse]] | None = None,
    ) -> None:
        super().__init__(
            client_id="mock",
            client_secret="mock",
            user_agent="mock",
            timeout=1.0,
        )
        self._posts = posts or {}

    async def fetch_subreddit_posts(
        self,
        subreddit: str,
        sort: str,
        time_filter: str,
        limit: int,
    ) -> list[RedditPostResponse]:
        return self._posts.get(subreddit, [])[:limit]


class MockGoogleTrendsClient(GoogleTrendsClient):
    """Returns canned trending/related data for deterministic testing."""

    def __init__(
        self,
        trending: list[GTTrendingSearch] | None = None,
        related: list[GTRelatedQuery] | None = None,
    ) -> None:
        # Skip parent __init__ — TrendReq() in super().__init__
        # attempts real HTTP initialization. Unlike MockHackerNewsClient
        # which can call super() with dummy URL/timeout, pytrends
        # TrendReq has no equivalent safe constructor args.
        self._trending = trending or []
        self._related = related or []

    async def fetch_trending_searches(
        self,
        country: str,
    ) -> list[GTTrendingSearch]:
        return self._trending

    async def fetch_related_queries(
        self,
        keywords: list[str],
    ) -> list[GTRelatedQuery]:
        return self._related


class MockNewsAPIClient(NewsAPIClient):
    """Returns canned articles for deterministic testing."""

    def __init__(
        self,
        articles: list[NewsAPIArticle] | None = None,
    ) -> None:
        super().__init__(
            api_key="mock",
            base_url="http://mock",
            timeout=1.0,
        )
        self._articles = articles or []

    async def fetch_top_headlines(
        self,
        category: str,
        country: str,
        page_size: int,
    ) -> list[NewsAPIArticle]:
        return self._articles[:page_size]


class MockArxivClient(ArxivClient):
    """Returns canned papers for deterministic testing."""

    def __init__(
        self,
        papers: list[ArxivPaper] | None = None,
    ) -> None:
        super().__init__(base_url="http://mock", timeout=1.0)
        self._papers = papers or []

    async def fetch_papers(
        self,
        categories: list[str],
        max_results: int,
        sort_by: str,
    ) -> list[ArxivPaper]:
        return self._papers[:max_results]
