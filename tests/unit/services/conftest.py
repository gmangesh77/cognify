import hashlib

from src.services.embeddings import EmbeddingService
from src.services.google_trends_client import (
    GoogleTrendsClient,
    GTRelatedQuery,
    GTTrendingSearch,
)
from src.services.hackernews_client import HackerNewsClient, HNStoryResponse

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
