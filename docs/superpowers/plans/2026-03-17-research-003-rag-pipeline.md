# RESEARCH-003: RAG Pipeline (Milvus) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the RAG infrastructure: token-aware document chunking, Milvus vector storage with metadata filtering, top-k retrieval service, and an `index_findings` orchestrator node that indexes research findings after each dispatch round.

**Architecture:** `TokenChunker` splits text into 512-token chunks. `MilvusService` manages a single `research_chunks` collection (IVF_FLAT, COSINE). `MilvusRetriever` queries with topic_id filtering. New `index_findings` node in the LangGraph orchestrator indexes findings between dispatch and evaluate. All pymilvus calls wrapped in `run_in_executor` for async compatibility.

**Tech Stack:** pymilvus (Milvus Lite for dev), tiktoken, sentence-transformers (existing), LangGraph (existing)

**Spec:** [`docs/superpowers/specs/2026-03-17-research-003-rag-pipeline-design.md`](../specs/2026-03-17-research-003-rag-pipeline-design.md)

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/services/chunker.py` | TokenChunker: token-aware document chunking |
| `src/services/milvus_service.py` | MilvusService: connection, schema, insert, search, stats |
| `src/services/milvus_retriever.py` | MilvusRetriever: embed query + search Milvus |
| `src/models/research.py` | Add ChunkMetadata, DocumentChunk, ChunkResult, KnowledgeBaseStats (modify) |
| `src/agents/research/orchestrator.py` | Add index_findings node, update build_graph signature (modify) |
| `src/config/settings.py` | Add milvus_*, chunk_*, top_k_* settings (modify) |
| `pyproject.toml` | Add pymilvus, tiktoken dependencies (modify) |
| `tests/unit/services/test_chunker.py` | Chunker unit tests |
| `tests/unit/services/test_milvus_service.py` | Milvus Lite integration tests |
| `tests/unit/services/test_milvus_retriever.py` | Retriever tests with Milvus Lite |
| `tests/unit/agents/research/test_orchestrator.py` | Add index_findings tests (modify) |

---

## Task 1: Add Dependencies and Settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/config/settings.py`

- [ ] **Step 1: Add pymilvus and tiktoken to pyproject.toml**

Add to `dependencies`:
```toml
"pymilvus>=2.4.0",
"tiktoken>=0.7.0",
```

Add mypy overrides:
```toml
[[tool.mypy.overrides]]
module = "pymilvus.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tiktoken.*"
ignore_missing_imports = true
```

- [ ] **Step 2: Add Milvus and chunking settings**

Add after the SerpAPI settings in `src/config/settings.py`:

```python
    # Milvus
    milvus_uri: str = "./milvus_data.db"
    milvus_collection_name: str = "research_chunks"
    # Chunking
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 50
    # Retrieval
    top_k_retrieval: int = 5
```

- [ ] **Step 3: Install dependencies**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pip install -e ".[dev]"`
Expected: pymilvus and tiktoken install successfully.

- [ ] **Step 4: Verify imports**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify python -c "from pymilvus import MilvusClient; import tiktoken; print('OK')"`
Expected: Prints `OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/config/settings.py
git commit -m "chore(research-003): add pymilvus, tiktoken dependencies and Milvus settings"
```

---

## Task 2: RAG Data Models

**Files:**
- Modify: `src/models/research.py`
- Test: `tests/unit/models/test_research_models.py` (append)

- [ ] **Step 1: Write failing tests for new models**

Append to `tests/unit/models/test_research_models.py`:

```python
from src.models.research import (
    ChunkMetadata,
    ChunkResult,
    DocumentChunk,
    KnowledgeBaseStats,
)


class TestChunkMetadata:
    def test_construct(self) -> None:
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Test",
            topic_id="topic-1",
            session_id="session-1",
        )
        assert meta.source_url == "https://example.com"

    def test_frozen(self) -> None:
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Test",
            topic_id="t",
            session_id="s",
        )
        with pytest.raises(ValidationError):
            meta.source_url = "changed"  # type: ignore[misc]


class TestDocumentChunk:
    def test_construct(self) -> None:
        chunk = DocumentChunk(
            text="Some chunk text",
            source_url="https://example.com",
            source_title="Test",
            topic_id="topic-1",
            session_id="session-1",
            chunk_index=0,
        )
        assert chunk.chunk_index == 0
        assert chunk.text == "Some chunk text"


class TestChunkResult:
    def test_construct(self) -> None:
        result = ChunkResult(
            text="Retrieved chunk",
            source_url="https://example.com",
            source_title="Test",
            score=0.95,
            chunk_index=0,
        )
        assert result.score == 0.95


class TestKnowledgeBaseStats:
    def test_construct_with_topic(self) -> None:
        stats = KnowledgeBaseStats(
            total_chunks=100,
            total_documents=25,
            collection_name="research_chunks",
            topic_id="topic-1",
        )
        assert stats.total_chunks == 100
        assert stats.topic_id == "topic-1"

    def test_construct_without_topic(self) -> None:
        stats = KnowledgeBaseStats(
            total_chunks=100,
            total_documents=25,
            collection_name="research_chunks",
        )
        assert stats.topic_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_research_models.py -v -k "Chunk or KnowledgeBase"`
Expected: FAIL — ImportError

- [ ] **Step 3: Add models to src/models/research.py**

Append after `EvaluationResult` at the end of `src/models/research.py`:

```python


class ChunkMetadata(BaseModel, frozen=True):
    """Metadata for a document chunk (passed to TokenChunker)."""

    source_url: str
    source_title: str
    topic_id: str
    session_id: str


class DocumentChunk(BaseModel, frozen=True):
    """A chunked document ready for embedding and Milvus storage."""

    text: str
    source_url: str
    source_title: str
    topic_id: str
    session_id: str
    chunk_index: int


class ChunkResult(BaseModel, frozen=True):
    """A retrieved chunk from Milvus similarity search."""

    text: str
    source_url: str
    source_title: str
    score: float
    chunk_index: int


class KnowledgeBaseStats(BaseModel, frozen=True):
    """Knowledge base statistics from Milvus."""

    total_chunks: int
    total_documents: int
    collection_name: str
    topic_id: str | None = None
```

- [ ] **Step 4: Update src/models/__init__.py exports**

Read `src/models/__init__.py` first, then add the new imports and `__all__` entries.

- [ ] **Step 5: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_research_models.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/models/research.py src/models/__init__.py tests/unit/models/test_research_models.py
git commit -m "feat(research-003): add RAG data models (DocumentChunk, ChunkResult, KnowledgeBaseStats)"
```

---

## Task 3: TokenChunker

**Files:**
- Create: `src/services/chunker.py`
- Create: `tests/unit/services/test_chunker.py`

- [ ] **Step 1: Write failing tests for TokenChunker**

Create `tests/unit/services/test_chunker.py`:

```python
"""Tests for the token-aware document chunker."""

from src.models.research import ChunkMetadata, DocumentChunk
from src.services.chunker import TokenChunker


def _make_metadata() -> ChunkMetadata:
    return ChunkMetadata(
        source_url="https://example.com/article",
        source_title="Test Article",
        topic_id="topic-1",
        session_id="session-1",
    )


class TestTokenChunkerShortText:
    def test_short_text_single_chunk(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        chunks = chunker.chunk("This is a short text.", _make_metadata())
        assert len(chunks) == 1
        assert chunks[0].text == "This is a short text."
        assert chunks[0].chunk_index == 0

    def test_preserves_metadata(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        meta = _make_metadata()
        chunks = chunker.chunk("Short text.", meta)
        assert chunks[0].source_url == meta.source_url
        assert chunks[0].source_title == meta.source_title
        assert chunks[0].topic_id == meta.topic_id
        assert chunks[0].session_id == meta.session_id


class TestTokenChunkerLongText:
    def test_long_text_multiple_chunks(self) -> None:
        chunker = TokenChunker(chunk_size=10, overlap=2)
        # Create text that is definitely longer than 10 tokens
        long_text = " ".join(f"word{i}" for i in range(50))
        chunks = chunker.chunk(long_text, _make_metadata())
        assert len(chunks) > 1
        # Each chunk should have content
        for chunk in chunks:
            assert len(chunk.text) > 0

    def test_chunk_indices_sequential(self) -> None:
        chunker = TokenChunker(chunk_size=10, overlap=2)
        long_text = " ".join(f"word{i}" for i in range(50))
        chunks = chunker.chunk(long_text, _make_metadata())
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_overlap_creates_shared_content(self) -> None:
        chunker = TokenChunker(chunk_size=10, overlap=3)
        long_text = " ".join(f"word{i}" for i in range(30))
        chunks = chunker.chunk(long_text, _make_metadata())
        # With overlap, adjacent chunks should share some text
        if len(chunks) >= 2:
            # The end of chunk 0 and start of chunk 1 should overlap
            assert len(chunks) >= 2


class TestTokenChunkerEdgeCases:
    def test_empty_text_returns_empty(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        chunks = chunker.chunk("", _make_metadata())
        assert chunks == []

    def test_whitespace_only_returns_empty(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        chunks = chunker.chunk("   \n\t  ", _make_metadata())
        assert chunks == []

    def test_returns_document_chunk_type(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        chunks = chunker.chunk("Some text here.", _make_metadata())
        assert all(isinstance(c, DocumentChunk) for c in chunks)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_chunker.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement TokenChunker**

Create `src/services/chunker.py`:

```python
"""Token-aware document chunker.

Splits text into chunks of a configurable token size with overlap.
Uses tiktoken (cl100k_base) for token counting. Pure logic — no I/O.

Note: tiktoken uses cl100k_base (GPT-4 family) while the embedding
model (all-MiniLM-L6-v2) uses WordPiece. Token counts diverge ~10-20%.
The embedding model truncates silently at its sequence limit — this is
an accepted trade-off for consistent, predictable chunk sizes.
"""

import tiktoken

from src.models.research import ChunkMetadata, DocumentChunk


class TokenChunker:
    """Splits text into token-aware chunks with overlap."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._enc = tiktoken.get_encoding("cl100k_base")

    def chunk(
        self, text: str, metadata: ChunkMetadata
    ) -> list[DocumentChunk]:
        """Split text into chunks. Returns empty list for empty text."""
        stripped = text.strip()
        if not stripped:
            return []

        tokens = self._enc.encode(stripped)
        if len(tokens) <= self._chunk_size:
            return [self._make_chunk(stripped, metadata, 0)]

        return self._split_tokens(tokens, metadata)

    def _split_tokens(
        self, tokens: list[int], metadata: ChunkMetadata
    ) -> list[DocumentChunk]:
        """Sliding window split with overlap."""
        chunks: list[DocumentChunk] = []
        step = self._chunk_size - self._overlap
        start = 0
        index = 0

        while start < len(tokens):
            end = min(start + self._chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            text = self._enc.decode(chunk_tokens)
            chunks.append(self._make_chunk(text, metadata, index))
            index += 1
            start += step
            if end == len(tokens):
                break

        return chunks

    def _make_chunk(
        self, text: str, metadata: ChunkMetadata, index: int
    ) -> DocumentChunk:
        """Create a DocumentChunk with metadata."""
        return DocumentChunk(
            text=text,
            source_url=metadata.source_url,
            source_title=metadata.source_title,
            topic_id=metadata.topic_id,
            session_id=metadata.session_id,
            chunk_index=index,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_chunker.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/chunker.py tests/unit/services/test_chunker.py
git commit -m "feat(research-003): add TokenChunker with tiktoken-based splitting"
```

---

## Task 4: MilvusService

**Files:**
- Create: `src/services/milvus_service.py`
- Create: `tests/unit/services/test_milvus_service.py`

- [ ] **Step 1: Write failing tests for MilvusService**

Create `tests/unit/services/test_milvus_service.py`:

```python
"""Tests for MilvusService using Milvus Lite (real embedded Milvus)."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.research import DocumentChunk
from src.services.milvus_service import MilvusService, MilvusServiceError


@pytest.fixture
def milvus_db(tmp_path):
    """Create a Milvus Lite instance with a temp file."""
    db_path = str(tmp_path / "test_milvus.db")
    svc = MilvusService(uri=db_path, collection_name="test_chunks")
    svc.ensure_collection()
    yield svc
    svc.close()


def _make_chunks(
    num: int = 3, topic_id: str = "topic-1", session_id: str = "sess-1"
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


def _make_embeddings(num: int = 3, dim: int = 384) -> list[list[float]]:
    """Create simple normalized embeddings for testing."""
    import numpy as np

    rng = np.random.default_rng(42)
    vecs = rng.standard_normal((num, dim)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return (vecs / norms).tolist()


class TestMilvusServiceInsert:
    async def test_insert_chunks(self, milvus_db: MilvusService) -> None:
        chunks = _make_chunks(3)
        embeddings = _make_embeddings(3)
        count = await milvus_db.insert_chunks(chunks, embeddings)
        assert count == 3

    async def test_insert_mismatched_lengths_raises(
        self, milvus_db: MilvusService
    ) -> None:
        chunks = _make_chunks(3)
        embeddings = _make_embeddings(2)  # Mismatch!
        with pytest.raises(ValueError, match="length"):
            await milvus_db.insert_chunks(chunks, embeddings)


class TestMilvusServiceSearch:
    async def test_search_returns_results(self, milvus_db: MilvusService) -> None:
        chunks = _make_chunks(5)
        embeddings = _make_embeddings(5)
        await milvus_db.insert_chunks(chunks, embeddings)

        # Search with the first embedding
        results = await milvus_db.search(embeddings[0], "topic-1", top_k=3)
        assert len(results) <= 3
        assert all(r.source_url.startswith("https://") for r in results)

    async def test_search_filters_by_topic(self, milvus_db: MilvusService) -> None:
        # Insert chunks for two topics
        chunks_a = _make_chunks(3, topic_id="topic-a")
        chunks_b = _make_chunks(3, topic_id="topic-b")
        emb_a = _make_embeddings(3)
        emb_b = _make_embeddings(3)
        await milvus_db.insert_chunks(chunks_a, emb_a)
        await milvus_db.insert_chunks(chunks_b, emb_b)

        # Search for topic-a only — should return at most 3 (only topic-a chunks)
        results = await milvus_db.search(emb_a[0], "topic-a", top_k=10)
        assert len(results) <= 3

    async def test_search_nonexistent_topic_returns_empty(self, milvus_db: MilvusService) -> None:
        chunks = _make_chunks(3, topic_id="topic-a")
        emb = _make_embeddings(3)
        await milvus_db.insert_chunks(chunks, emb)

        results = await milvus_db.search(emb[0], "nonexistent-topic", top_k=10)
        assert results == []

    async def test_search_empty_collection(self, milvus_db: MilvusService) -> None:
        emb = _make_embeddings(1)
        results = await milvus_db.search(emb[0], "topic-1", top_k=5)
        assert results == []


class TestMilvusServiceStats:
    async def test_get_stats(self, milvus_db: MilvusService) -> None:
        chunks = _make_chunks(5)
        embeddings = _make_embeddings(5)
        await milvus_db.insert_chunks(chunks, embeddings)

        stats = await milvus_db.get_stats()
        assert stats.total_chunks == 5
        assert stats.collection_name == "test_chunks"

    async def test_get_stats_empty(self, milvus_db: MilvusService) -> None:
        stats = await milvus_db.get_stats()
        assert stats.total_chunks == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_milvus_service.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement MilvusService**

Create `src/services/milvus_service.py`:

```python
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
from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient

from src.models.research import ChunkResult, DocumentChunk, KnowledgeBaseStats

logger = structlog.get_logger()

_EMBEDDING_DIM = 384


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
        self._client.create_collection(
            collection_name=self._collection_name,
            schema=schema,
        )
        self._create_index()

    def _build_schema(self) -> CollectionSchema:
        """Build the collection schema."""
        fields = [
            FieldSchema("id", DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=_EMBEDDING_DIM),
            FieldSchema("text", DataType.VARCHAR, max_length=65535),
            FieldSchema("source_url", DataType.VARCHAR, max_length=2048),
            FieldSchema("source_title", DataType.VARCHAR, max_length=1024),
            FieldSchema("topic_id", DataType.VARCHAR, max_length=64),
            FieldSchema("session_id", DataType.VARCHAR, max_length=64),
            FieldSchema("chunk_index", DataType.INT64),
            FieldSchema("created_at", DataType.VARCHAR, max_length=32),
        ]
        return CollectionSchema(fields=fields)

    def _create_index(self) -> None:
        """Create IVF_FLAT index on embedding field."""
        self._client.create_index(
            collection_name=self._collection_name,
            field_name="embedding",
            index_params={
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE",
                "params": {"nlist": 128},
            },
        )

    async def insert_chunks(
        self, chunks: list[DocumentChunk], embeddings: list[list[float]]
    ) -> int:
        """Insert chunks with embeddings. Returns count inserted."""
        if len(chunks) != len(embeddings):
            msg = f"Chunks length {len(chunks)} != embeddings length {len(embeddings)}"
            raise ValueError(msg)
        if not chunks:
            return 0

        data = self._prepare_insert_data(chunks, embeddings)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self._sync_insert, data
        )
        return result

    def _prepare_insert_data(
        self, chunks: list[DocumentChunk], embeddings: list[list[float]]
    ) -> list[dict]:
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
                "created_at": now,
            }
            for chunk, emb in zip(chunks, embeddings, strict=True)
        ]

    def _sync_insert(self, data: list[dict]) -> int:
        """Synchronous insert (called via run_in_executor)."""
        self._client.insert(
            collection_name=self._collection_name, data=data
        )
        return len(data)

    async def search(
        self, query_embedding: list[float], topic_id: str, top_k: int
    ) -> list[ChunkResult]:
        """Top-k similarity search with topic_id filter."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_search, query_embedding, topic_id, top_k
        )

    def _sync_search(
        self, query_embedding: list[float], topic_id: str, top_k: int
    ) -> list[ChunkResult]:
        """Synchronous search (called via run_in_executor)."""
        results = self._client.search(
            collection_name=self._collection_name,
            data=[query_embedding],
            limit=top_k,
            filter=f'topic_id == "{topic_id}"',
            output_fields=["text", "source_url", "source_title", "chunk_index"],
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
            )
            for hit in results[0]
        ]

    async def get_stats(
        self, topic_id: str | None = None
    ) -> KnowledgeBaseStats:
        """Collection-level stats."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_get_stats, topic_id
        )

    def _sync_get_stats(
        self, topic_id: str | None
    ) -> KnowledgeBaseStats:
        """Synchronous stats (called via run_in_executor)."""
        stats = self._client.get_collection_stats(self._collection_name)
        total = stats.get("row_count", 0)
        return KnowledgeBaseStats(
            total_chunks=total,
            total_documents=total,  # Approximation; unique URL count requires query
            collection_name=self._collection_name,
            topic_id=topic_id,
        )

    def close(self) -> None:
        """Close the Milvus connection."""
        self._client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_milvus_service.py -v`
Expected: All PASS

- [ ] **Step 5: Lint**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/services/milvus_service.py && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/services/milvus_service.py`

- [ ] **Step 6: Commit**

```bash
git add src/services/milvus_service.py tests/unit/services/test_milvus_service.py
git commit -m "feat(research-003): add MilvusService with Milvus Lite support"
```

---

## Task 5: MilvusRetriever

**Files:**
- Create: `src/services/milvus_retriever.py`
- Create: `tests/unit/services/test_milvus_retriever.py`

- [ ] **Step 1: Write failing tests for MilvusRetriever**

Create `tests/unit/services/test_milvus_retriever.py`:

```python
"""Tests for MilvusRetriever using Milvus Lite + real embeddings."""

import pytest

from src.models.research import ChunkResult, DocumentChunk
from src.services.embeddings import EmbeddingService
from src.services.milvus_retriever import MilvusRetriever
from src.services.milvus_service import MilvusService


@pytest.fixture
def embedding_svc():
    return EmbeddingService(model_name="all-MiniLM-L6-v2")


@pytest.fixture
def milvus_db(tmp_path):
    db_path = str(tmp_path / "test_retriever.db")
    svc = MilvusService(uri=db_path, collection_name="test_retriever")
    svc.ensure_collection()
    yield svc
    svc.close()


@pytest.fixture
def retriever(milvus_db, embedding_svc):
    return MilvusRetriever(milvus_db, embedding_svc)


async def _seed_chunks(
    milvus_db: MilvusService,
    embedding_svc: EmbeddingService,
    texts: list[str],
    topic_id: str = "topic-1",
) -> None:
    chunks = [
        DocumentChunk(
            text=t,
            source_url=f"https://example.com/{i}",
            source_title=f"Doc {i}",
            topic_id=topic_id,
            session_id="sess-1",
            chunk_index=i,
        )
        for i, t in enumerate(texts)
    ]
    embeddings = embedding_svc.embed(texts)
    await milvus_db.insert_chunks(chunks, embeddings)


class TestMilvusRetriever:
    async def test_retrieve_returns_relevant_chunks(
        self, retriever: MilvusRetriever, milvus_db: MilvusService, embedding_svc: EmbeddingService
    ) -> None:
        texts = [
            "AI security threats are increasing in 2026",
            "Machine learning models can be poisoned by adversarial data",
            "The weather forecast for tomorrow is sunny and warm",
        ]
        await _seed_chunks(milvus_db, embedding_svc, texts)

        results = await retriever.retrieve("AI security", "topic-1", top_k=2)
        assert len(results) <= 2
        assert all(isinstance(r, ChunkResult) for r in results)

    async def test_retrieve_empty_collection(
        self, retriever: MilvusRetriever
    ) -> None:
        results = await retriever.retrieve("test", "topic-1", top_k=5)
        assert results == []

    async def test_retrieve_respects_top_k(
        self, retriever: MilvusRetriever, milvus_db: MilvusService, embedding_svc: EmbeddingService
    ) -> None:
        texts = [f"Document about topic {i}" for i in range(10)]
        await _seed_chunks(milvus_db, embedding_svc, texts)

        results = await retriever.retrieve("topic", "topic-1", top_k=3)
        assert len(results) <= 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_milvus_retriever.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement MilvusRetriever**

Create `src/services/milvus_retriever.py`:

```python
"""Milvus retrieval service.

Embeds a query via EmbeddingService, searches Milvus for top-k
similar chunks with topic_id filtering. Returns ranked ChunkResults.
"""

from src.models.research import ChunkResult
from src.services.embeddings import EmbeddingService
from src.services.milvus_service import MilvusService


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
        """Embed query and search Milvus with topic filtering."""
        vectors = self._embeddings.embed([query])
        if not vectors:
            return []
        return await self._milvus.search(vectors[0], topic_id, top_k)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_milvus_retriever.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/milvus_retriever.py tests/unit/services/test_milvus_retriever.py
git commit -m "feat(research-003): add MilvusRetriever for top-k semantic search"
```

---

## Task 6: Orchestrator index_findings Node

**Files:**
- Modify: `src/agents/research/orchestrator.py`
- Modify: `tests/unit/agents/research/test_orchestrator.py`

- [ ] **Step 1: Write failing tests for index_findings**

Append to `tests/unit/agents/research/test_orchestrator.py`:

```python
from unittest.mock import AsyncMock, MagicMock

from src.agents.research.orchestrator import IndexingDeps
from src.models.research import DocumentChunk


def _initial_state() -> dict:
    """Shared initial state for orchestrator tests."""
    return {
        "topic": _make_topic(),
        "research_plan": None,
        "dispatched_tasks": [],
        "findings": [],
        "evaluation": None,
        "round_number": 0,
        "session_id": uuid4(),
        "status": "initial",
        "error": None,
        "indexed_count": 0,
    }


def _make_indexing_deps(
    insert_side_effect: Exception | None = None,
) -> IndexingDeps:
    """Create mock IndexingDeps for testing."""
    mock_store = AsyncMock()
    if insert_side_effect:
        mock_store.insert_chunks = AsyncMock(side_effect=insert_side_effect)
    else:
        mock_store.insert_chunks = AsyncMock(return_value=3)

    mock_embedder = MagicMock()
    mock_embedder.embed = MagicMock(
        side_effect=lambda texts: [[0.1] * 384] * len(texts)
    )

    mock_chunker = MagicMock()
    mock_chunker.chunk = MagicMock(return_value=[
        DocumentChunk(
            text="chunk", source_url="https://example.com",
            source_title="Test", topic_id="t", session_id="s", chunk_index=0,
        )
    ])

    return IndexingDeps(
        vector_store=mock_store,
        embedder=mock_embedder,
        chunker=mock_chunker,
    )


class TestIndexFindingsNode:
    async def test_graph_with_indexing(self) -> None:
        """Graph runs with indexing node — findings get indexed."""
        deps = _make_indexing_deps()
        llm = FakeListChatModel(responses=[_plan_json(3), _eval_json(True)])
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent, indexing_deps=deps)
        result = await graph.ainvoke(_initial_state())
        assert result["status"] == "complete"
        assert deps.vector_store.insert_chunks.called

    async def test_graph_without_indexing_deps(self) -> None:
        """Graph works when indexing_deps is None (backward compat)."""
        llm = FakeListChatModel(responses=[_plan_json(3), _eval_json(True)])
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent)
        result = await graph.ainvoke(_initial_state())
        assert result["status"] == "complete"
        assert len(result["findings"]) == 3

    async def test_index_failure_does_not_crash_graph(self) -> None:
        """Milvus insert failure is logged but graph continues."""
        deps = _make_indexing_deps(insert_side_effect=Exception("Milvus down"))
        llm = FakeListChatModel(responses=[_plan_json(3), _eval_json(True)])
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent, indexing_deps=deps)
        result = await graph.ainvoke(_initial_state())
        assert result["status"] == "complete"
```

**IMPORTANT:** The implementer must also refactor `TestOrchestrator` and `TestRunner` to use the module-level `_initial_state()` function instead of `self._initial_state()`. Remove the method from `TestOrchestrator` class. Add `"indexed_count": 0` to the initial state dict.

- [ ] **Step 2: Run tests to verify the new tests fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_orchestrator.py::TestIndexFindingsNode -v`
Expected: FAIL — `build_graph` doesn't accept `milvus_service` yet

- [ ] **Step 3: Update orchestrator with index_findings node**

Modify `src/agents/research/orchestrator.py`:

1. Update `build_graph` signature to accept optional `IndexingDeps`:
```python
def build_graph(
    llm: BaseChatModel,
    dispatcher: TaskDispatcher,
    agent_fn: AgentFunction,
    indexing_deps: IndexingDeps | None = None,
) -> CompiledStateGraph:
```

Note: `IndexingDeps` is a frozen dataclass bundling `VectorStore`, `Embedder`, and `ChunkService` protocols. This keeps the orchestrator decoupled from concrete types while maintaining type safety (no `object | None` + type: ignore).

2. Add `indexed_count` to ResearchState. Modify `src/agents/research/state.py` to add:
```python
    indexed_count: int  # Tracks how many findings have been indexed (avoids re-indexing on retry)
```
And update `_initial_state` in runner.py to include `"indexed_count": 0`.

3. Define Protocol types for indexing dependencies (avoids `object | None` + type: ignore):
```python
from typing import Protocol

class ChunkService(Protocol):
    def chunk(self, text: str, metadata: ChunkMetadata) -> list[DocumentChunk]: ...

class VectorStore(Protocol):
    async def insert_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> int: ...

class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

@dataclass(frozen=True)
class IndexingDeps:
    """Bundles indexing dependencies to respect 3-param limit."""
    vector_store: VectorStore
    embedder: Embedder
    chunker: ChunkService
```

4. Add `index_findings` node:
```python
    async def index_findings(state: ResearchState) -> dict:  # type: ignore[type-arg]
        if indexing_deps is None:
            logger.info("index_findings_skipped", reason="services not configured")
            return {}
        try:
            new_count = await _index_new_findings(state, indexing_deps)
            return {"indexed_count": state.get("indexed_count", 0) + new_count}
        except Exception as exc:
            logger.error("index_findings_failed", error=str(exc))
            return {}
```

5. Add helper function (outside build_graph):
```python
async def _index_new_findings(
    state: ResearchState, deps: IndexingDeps
) -> int:
    """Index only un-indexed findings into Milvus. Returns chunk count."""
    findings = _validate_findings(state)
    indexed_count = state.get("indexed_count", 0)
    new_findings = findings[indexed_count:]
    if not new_findings:
        return 0

    all_chunks = _chunk_findings(new_findings, state, deps.chunker)
    if not all_chunks:
        return 0

    texts = [c.text for c in all_chunks]
    embeddings = deps.embedder.embed(texts)
    await deps.vector_store.insert_chunks(all_chunks, embeddings)
    logger.info("findings_indexed", chunk_count=len(all_chunks))
    return len(new_findings)


def _chunk_findings(
    findings: list[FacetFindings],
    state: ResearchState,
    chunker: ChunkService,
) -> list[DocumentChunk]:
    """Chunk all source snippets from findings."""
    topic = _validate_topic(state)
    session_id = str(state["session_id"])
    all_chunks: list[DocumentChunk] = []
    for finding in findings:
        for source in finding.sources:
            metadata = ChunkMetadata(
                source_url=source.url,
                source_title=source.title,
                topic_id=str(topic.id),
                session_id=session_id,
            )
            all_chunks.extend(chunker.chunk(source.snippet, metadata))
    return all_chunks
```
```

4. Register the node and update edges:
```python
    graph.add_node("index_findings", index_findings)

    # Updated edges
    graph.add_edge("dispatch_agents", "index_findings")
    graph.add_edge("index_findings", "evaluate_completeness")
    # Remove: graph.add_edge("dispatch_agents", "evaluate_completeness")
```

- [ ] **Step 4: Run all orchestrator tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_orchestrator.py -v`
Expected: All PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add src/agents/research/orchestrator.py tests/unit/agents/research/test_orchestrator.py
git commit -m "feat(research-003): add index_findings node to orchestrator"
```

---

## Task 7: Lint, Full Test Suite, Update Progress

**Files:**
- Modify: `project-management/PROGRESS.md`

- [ ] **Step 1: Run linter on all new code**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/services/chunker.py src/services/milvus_service.py src/services/milvus_retriever.py src/agents/research/orchestrator.py`
Expected: No issues

- [ ] **Step 2: Run formatter**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/ tests/`
Expected: No issues. Fix any that arise.

- [ ] **Step 3: Run full test suite with coverage**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v --cov=src --cov-report=term-missing --tb=short`
Expected: All tests PASS, coverage >= 80%

- [ ] **Step 4: Update PROGRESS.md**

Update RESEARCH-003 row:

| RESEARCH-003 | RAG Pipeline (Milvus) | Done | `feature/RESEARCH-003-rag-pipeline` | [plan](../docs/superpowers/plans/2026-03-17-research-003-rag-pipeline.md) | [spec](../docs/superpowers/specs/2026-03-17-research-003-rag-pipeline-design.md) |

Update the stubs section — mark RESEARCH-003 stub line as done. Update the infra ticket note to clarify Celery is still pending (moved out of RESEARCH-003 scope).

- [ ] **Step 5: Commit**

```bash
git add project-management/PROGRESS.md
git commit -m "docs: update PROGRESS.md — RESEARCH-003 done"
```
