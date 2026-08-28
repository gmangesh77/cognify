"""Milvus retrieval service.

Embeds a query via EmbeddingService, searches Milvus for top-k
similar chunks with topic_id filtering. Returns ranked ChunkResults.
"""

import structlog

from src.models.research import ChunkResult
from src.services.embeddings import EmbeddingService
from src.services.milvus_service import MilvusService

logger = structlog.get_logger()


class MilvusRetriever:
    """Retrieves relevant chunks from Milvus by semantic similarity."""

    def __init__(
        self, milvus_service: MilvusService, embedding_service: EmbeddingService
    ) -> None:
        self._milvus = milvus_service
        self._embeddings = embedding_service

    async def retrieve(
        self, query: str, topic_id: str, top_k: int = 5
    ) -> list[ChunkResult]:
        """Embed query and search Milvus with topic filtering.

        INFRA-008: while the embedding model is still warming up the
        retriever degrades to "no RAG context" instead of blocking the
        event loop on a synchronous model load.
        """
        vectors = self._embeddings.try_embed([query])
        if vectors is None:
            logger.info("retriever_skipped_embedding_cold", topic_id=topic_id)
            return []
        if not vectors:
            return []
        return await self._milvus.search(vectors[0], topic_id, top_k)
