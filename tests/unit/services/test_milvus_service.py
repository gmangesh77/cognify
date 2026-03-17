"""Tests for MilvusService.

Milvus Lite is not available on Windows, so these tests mock
MilvusClient to verify service logic: async wrappers, data
preparation, result parsing, validation, and error handling.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.models.research import DocumentChunk
from src.services.milvus_service import MilvusService


def _make_chunks(
    num: int = 3,
    topic_id: str = "topic-1",
    session_id: str = "sess-1",
) -> list[DocumentChunk]:
    return [
        DocumentChunk(
            text=f"Chunk text number {i} about AI security.",
            source_url=f"https://example.com/doc-{i}",
            source_title=f"Document {i}",
            topic_id=topic_id,
            session_id=session_id,
            chunk_index=i,
        )
        for i in range(num)
    ]


def _make_embeddings(
    num: int = 3, dim: int = 384,
) -> list[list[float]]:
    """Create simple normalized embeddings for testing."""
    rng = np.random.default_rng(42)
    vecs = rng.standard_normal((num, dim)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return (vecs / norms).tolist()


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock MilvusClient."""
    client = MagicMock()
    client.has_collection.return_value = False
    client.insert.return_value = {"insert_count": 3}
    client.search.return_value = [[]]
    client.get_collection_stats.return_value = {"row_count": 0}
    return client


@pytest.fixture
def milvus_db(mock_client: MagicMock) -> MilvusService:
    """Create a MilvusService with a mocked client."""
    with patch(
        "src.services.milvus_service.MilvusClient",
        return_value=mock_client,
    ):
        svc = MilvusService(
            uri="mock://test", collection_name="test_chunks",
        )
    svc.ensure_collection()
    return svc


class TestMilvusServiceEnsureCollection:
    def test_creates_collection_when_missing(
        self, milvus_db: MilvusService, mock_client: MagicMock,
    ) -> None:
        mock_client.create_collection.assert_called_once()
        call_kwargs = mock_client.create_collection.call_args
        assert call_kwargs.kwargs["collection_name"] == "test_chunks"

    def test_skips_create_when_exists(
        self, mock_client: MagicMock,
    ) -> None:
        mock_client.has_collection.return_value = True
        with patch(
            "src.services.milvus_service.MilvusClient",
            return_value=mock_client,
        ):
            svc = MilvusService(
                uri="mock://test", collection_name="test_chunks",
            )
        svc.ensure_collection()
        mock_client.create_collection.assert_not_called()


class TestMilvusServiceInsert:
    async def test_insert_chunks(
        self, milvus_db: MilvusService,
    ) -> None:
        chunks = _make_chunks(3)
        embeddings = _make_embeddings(3)
        count = await milvus_db.insert_chunks(chunks, embeddings)
        assert count == 3

    async def test_insert_prepares_correct_data(
        self,
        milvus_db: MilvusService,
        mock_client: MagicMock,
    ) -> None:
        chunks = _make_chunks(2)
        embeddings = _make_embeddings(2)
        await milvus_db.insert_chunks(chunks, embeddings)
        call_args = mock_client.insert.call_args
        data = call_args.kwargs["data"]
        assert len(data) == 2
        assert data[0]["text"] == "Chunk text number 0 about AI security."
        assert data[0]["source_url"] == "https://example.com/doc-0"
        assert data[0]["topic_id"] == "topic-1"
        assert data[0]["chunk_index"] == 0
        assert "id" in data[0]
        assert "embedding" in data[0]
        assert "created_at" in data[0]

    async def test_insert_mismatched_lengths_raises(
        self, milvus_db: MilvusService,
    ) -> None:
        chunks = _make_chunks(3)
        embeddings = _make_embeddings(2)
        with pytest.raises(ValueError, match="length"):
            await milvus_db.insert_chunks(chunks, embeddings)

    async def test_insert_empty_returns_zero(
        self, milvus_db: MilvusService,
    ) -> None:
        count = await milvus_db.insert_chunks([], [])
        assert count == 0


class TestMilvusServiceSearch:
    async def test_search_returns_results(
        self,
        milvus_db: MilvusService,
        mock_client: MagicMock,
    ) -> None:
        mock_client.search.return_value = [
            [
                {
                    "entity": {
                        "text": "AI security findings",
                        "source_url": "https://example.com/doc-0",
                        "source_title": "Document 0",
                        "chunk_index": 0,
                    },
                    "distance": 0.95,
                },
                {
                    "entity": {
                        "text": "More security data",
                        "source_url": "https://example.com/doc-1",
                        "source_title": "Document 1",
                        "chunk_index": 1,
                    },
                    "distance": 0.88,
                },
            ],
        ]
        emb = _make_embeddings(1)
        results = await milvus_db.search(emb[0], "topic-1", top_k=3)
        assert len(results) == 2
        assert results[0].text == "AI security findings"
        assert results[0].source_url == "https://example.com/doc-0"
        assert results[0].score == 0.95
        assert results[0].chunk_index == 0
        assert results[1].score == 0.88

    async def test_search_passes_correct_params(
        self,
        milvus_db: MilvusService,
        mock_client: MagicMock,
    ) -> None:
        emb = _make_embeddings(1)
        await milvus_db.search(emb[0], "topic-abc", top_k=5)
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["collection_name"] == "test_chunks"
        assert call_kwargs["limit"] == 5
        assert 'topic_id == "topic-abc"' in call_kwargs["filter"]

    async def test_search_empty_results(
        self,
        milvus_db: MilvusService,
        mock_client: MagicMock,
    ) -> None:
        mock_client.search.return_value = [[]]
        emb = _make_embeddings(1)
        results = await milvus_db.search(emb[0], "topic-1", top_k=5)
        assert results == []

    async def test_search_no_results_at_all(
        self,
        milvus_db: MilvusService,
        mock_client: MagicMock,
    ) -> None:
        mock_client.search.return_value = []
        emb = _make_embeddings(1)
        results = await milvus_db.search(
            emb[0], "nonexistent", top_k=10,
        )
        assert results == []

    async def test_search_filters_by_topic(
        self,
        milvus_db: MilvusService,
        mock_client: MagicMock,
    ) -> None:
        mock_client.search.return_value = [
            [
                {
                    "entity": {
                        "text": "topic-a only",
                        "source_url": "https://a.com",
                        "source_title": "A",
                        "chunk_index": 0,
                    },
                    "distance": 0.9,
                },
            ],
        ]
        emb = _make_embeddings(1)
        results = await milvus_db.search(
            emb[0], "topic-a", top_k=10,
        )
        assert len(results) == 1
        assert results[0].text == "topic-a only"
        call_kwargs = mock_client.search.call_args.kwargs
        assert 'topic_id == "topic-a"' in call_kwargs["filter"]


class TestMilvusServiceStats:
    async def test_get_stats(
        self,
        milvus_db: MilvusService,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get_collection_stats.return_value = {
            "row_count": 5,
        }
        stats = await milvus_db.get_stats()
        assert stats.total_chunks == 5
        assert stats.collection_name == "test_chunks"

    async def test_get_stats_empty(
        self,
        milvus_db: MilvusService,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get_collection_stats.return_value = {
            "row_count": 0,
        }
        stats = await milvus_db.get_stats()
        assert stats.total_chunks == 0

    async def test_get_stats_with_topic(
        self,
        milvus_db: MilvusService,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get_collection_stats.return_value = {
            "row_count": 10,
        }
        stats = await milvus_db.get_stats(topic_id="topic-1")
        assert stats.topic_id == "topic-1"
        assert stats.total_chunks == 10


class TestMilvusServiceClose:
    def test_close_calls_client_close(
        self, milvus_db: MilvusService, mock_client: MagicMock,
    ) -> None:
        milvus_db.close()
        mock_client.close.assert_called_once()
