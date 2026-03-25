"""Milvus vector database service.

Manages connection, collection schema, and CRUD operations for the
research_chunks collection. Uses Milvus Lite for dev (file-based),
configurable URI for production.

Note: pymilvus is synchronous. All I/O methods wrap calls in
run_in_executor to avoid blocking the event loop.
"""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import structlog
from pymilvus import (
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
)

from src.models.research import (
    ChunkResult,
    DocumentChunk,
    KnowledgeBaseStats,
)

logger = structlog.get_logger()

_EMBEDDING_DIM = 384


def _parse_iso_datetime(value: str) -> datetime | None:
    """Parse an ISO datetime string, returning None for empty/invalid."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class MilvusServiceError(Exception):
    """Raised when Milvus operations fail."""


class MilvusService:
    """Manages a single Milvus collection for research chunks."""

    def __init__(self, uri: str, collection_name: str) -> None:
        self._uri = uri
        self._collection_name = collection_name
        self._client = MilvusClient(uri=uri)

    def ensure_collection(self) -> None:
        """Create collection with schema if it doesn't exist."""
        if self._client.has_collection(self._collection_name):
            return
        schema = self._build_schema()
        index_params = self._build_index_params()
        self._client.create_collection(
            collection_name=self._collection_name,
            schema=schema,
            index_params=index_params,
        )
        logger.info("milvus_collection_created", collection_name=self._collection_name)

    def _build_schema(self) -> CollectionSchema:
        """Build the collection schema."""
        fields = [
            FieldSchema(
                "id",
                DataType.VARCHAR,
                is_primary=True,
                max_length=64,
            ),
            FieldSchema(
                "embedding",
                DataType.FLOAT_VECTOR,
                dim=_EMBEDDING_DIM,
            ),
            FieldSchema("text", DataType.VARCHAR, max_length=65535),
            FieldSchema(
                "source_url",
                DataType.VARCHAR,
                max_length=2048,
            ),
            FieldSchema(
                "source_title",
                DataType.VARCHAR,
                max_length=1024,
            ),
            FieldSchema(
                "topic_id",
                DataType.VARCHAR,
                max_length=64,
            ),
            FieldSchema(
                "session_id",
                DataType.VARCHAR,
                max_length=64,
            ),
            FieldSchema("chunk_index", DataType.INT64),
            FieldSchema(
                "published_at",
                DataType.VARCHAR,
                max_length=64,
            ),
            FieldSchema(
                "author",
                DataType.VARCHAR,
                max_length=512,
            ),
            FieldSchema(
                "created_at",
                DataType.VARCHAR,
                max_length=32,
            ),
        ]
        return CollectionSchema(fields=fields)

    def _build_index_params(self) -> "MilvusClient.IndexParams":
        """Build index params for the embedding field."""
        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )
        return index_params

    async def insert_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        """Insert chunks with embeddings. Returns count inserted."""
        if len(chunks) != len(embeddings):
            msg = f"Chunks length {len(chunks)} != embeddings length {len(embeddings)}"
            raise ValueError(msg)
        if not chunks:
            return 0
        data = self._prepare_insert_data(chunks, embeddings)
        loop = asyncio.get_running_loop()
        count = await loop.run_in_executor(None, self._sync_insert, data)
        logger.debug(
            "milvus_chunks_inserted",
            count=count,
            topic_id=chunks[0].topic_id if chunks else "",
            session_id=chunks[0].session_id if chunks else "",
        )
        return count

    def _prepare_insert_data(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> list[dict[str, object]]:
        """Prepare data dicts for Milvus insert."""
        now = datetime.now(UTC).isoformat()
        return [
            {
                "id": str(uuid4()),
                "embedding": emb,
                "text": chunk.text,
                "source_url": chunk.source_url,
                "source_title": chunk.source_title,
                "topic_id": chunk.topic_id,
                "session_id": chunk.session_id,
                "chunk_index": chunk.chunk_index,
                "published_at": chunk.published_at or "",
                "author": chunk.author or "",
                "created_at": now,
            }
            for chunk, emb in zip(chunks, embeddings, strict=True)
        ]

    def _sync_insert(self, data: list[dict[str, object]]) -> int:
        """Synchronous insert (called via run_in_executor)."""
        self._client.insert(
            collection_name=self._collection_name,
            data=data,
        )
        return len(data)

    async def search(
        self,
        query_embedding: list[float],
        topic_id: str,
        top_k: int,
    ) -> list[ChunkResult]:
        """Top-k similarity search with topic_id filter."""
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None, self._sync_search, query_embedding, topic_id, top_k,
        )
        if not results:
            logger.warning("milvus_search_empty", topic_id=topic_id, top_k=top_k)
        else:
            logger.debug(
                "milvus_search_executed",
                topic_id=topic_id,
                top_k=top_k,
                results_count=len(results),
            )
        return results

    def _sync_search(
        self,
        query_embedding: list[float],
        topic_id: str,
        top_k: int,
    ) -> list[ChunkResult]:
        """Synchronous search (called via run_in_executor)."""
        results = self._client.search(
            collection_name=self._collection_name,
            data=[query_embedding],
            limit=top_k,
            filter=f'topic_id == "{topic_id}"',
            output_fields=[
                "text",
                "source_url",
                "source_title",
                "chunk_index",
                "published_at",
                "author",
            ],
        )
        if not results or not results[0]:
            return []
        return [
            ChunkResult(
                text=hit["entity"]["text"],
                source_url=hit["entity"]["source_url"],
                source_title=hit["entity"]["source_title"],
                score=hit["distance"],
                chunk_index=hit["entity"]["chunk_index"],
                published_at=_parse_iso_datetime(
                    hit["entity"].get("published_at", ""),
                ),
                author=hit["entity"].get("author", "") or None,
            )
            for hit in results[0]
        ]

    async def get_stats(
        self,
        topic_id: str | None = None,
    ) -> KnowledgeBaseStats:
        """Collection-level stats."""
        loop = asyncio.get_running_loop()
        stats = await loop.run_in_executor(None, self._sync_get_stats, topic_id)
        logger.debug(
            "milvus_stats_fetched",
            total_chunks=stats.total_chunks,
            collection_name=stats.collection_name,
        )
        return stats

    def _sync_get_stats(
        self,
        topic_id: str | None,
    ) -> KnowledgeBaseStats:
        """Synchronous stats (called via run_in_executor)."""
        stats = self._client.get_collection_stats(
            self._collection_name,
        )
        total = stats.get("row_count", 0)
        return KnowledgeBaseStats(
            total_chunks=total,
            total_documents=total,
            collection_name=self._collection_name,
            topic_id=topic_id,
        )

    def close(self) -> None:
        """Close the Milvus connection."""
        self._client.close()
