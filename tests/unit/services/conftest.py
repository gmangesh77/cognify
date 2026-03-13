import hashlib

from src.services.embeddings import EmbeddingService
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
