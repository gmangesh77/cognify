"""Tests for MilvusRetriever (mocked services)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.research import ChunkResult
from src.services.milvus_retriever import MilvusRetriever


def _make_chunk_results(num: int = 3) -> list[ChunkResult]:
    return [
        ChunkResult(
            text=f"Result text {i}",
            source_url=f"https://example.com/{i}",
            source_title=f"Doc {i}",
            score=0.9 - i * 0.1,
            chunk_index=i,
        )
        for i in range(num)
    ]


class TestMilvusRetriever:
    async def test_retrieve_embeds_and_searches(self) -> None:
        mock_milvus = AsyncMock()
        mock_milvus.search = AsyncMock(return_value=_make_chunk_results(3))
        mock_embedding = MagicMock()
        mock_embedding.embed = MagicMock(return_value=[[0.1] * 384])

        retriever = MilvusRetriever(mock_milvus, mock_embedding)
        results = await retriever.retrieve("AI security", "topic-1", top_k=3)

        assert len(results) == 3
        assert all(isinstance(r, ChunkResult) for r in results)
        mock_embedding.embed.assert_called_once_with(["AI security"])
        mock_milvus.search.assert_called_once_with([0.1] * 384, "topic-1", 3)

    async def test_retrieve_empty_results(self) -> None:
        mock_milvus = AsyncMock()
        mock_milvus.search = AsyncMock(return_value=[])
        mock_embedding = MagicMock()
        mock_embedding.embed = MagicMock(return_value=[[0.1] * 384])

        retriever = MilvusRetriever(mock_milvus, mock_embedding)
        results = await retriever.retrieve("obscure query", "topic-1")

        assert results == []

    async def test_retrieve_respects_top_k(self) -> None:
        mock_milvus = AsyncMock()
        mock_milvus.search = AsyncMock(return_value=_make_chunk_results(2))
        mock_embedding = MagicMock()
        mock_embedding.embed = MagicMock(return_value=[[0.1] * 384])

        retriever = MilvusRetriever(mock_milvus, mock_embedding)
        results = await retriever.retrieve("query", "topic-1", top_k=2)

        assert len(results) == 2
        # Verify top_k was passed through
        call_args = mock_milvus.search.call_args
        assert call_args[0][2] == 2  # top_k param

    async def test_retrieve_empty_embedding(self) -> None:
        mock_milvus = AsyncMock()
        mock_embedding = MagicMock()
        mock_embedding.embed = MagicMock(return_value=[])

        retriever = MilvusRetriever(mock_milvus, mock_embedding)
        results = await retriever.retrieve("query", "topic-1")

        assert results == []
        mock_milvus.search.assert_not_called()
