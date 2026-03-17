# RESEARCH-003: RAG Pipeline (Milvus) — Design Spec

> **Date**: 2026-03-17
> **Ticket**: RESEARCH-003
> **Status**: Design approved
> **Depends on**: RESEARCH-001 (Orchestrator — merged), RESEARCH-002 (Web Search Agent — merged)
> **Blocks**: CONTENT-002 (Section-by-Section Drafting with RAG), RESEARCH-005 (Session Tracking)

---

## 1. Overview

Build the RAG (Retrieval-Augmented Generation) infrastructure: document chunking, Milvus vector storage, and retrieval service. Adds an `index_findings` node to the orchestrator that indexes research findings into Milvus after each dispatch round. Provides a standalone retriever for downstream consumers (Writer Agent in CONTENT-002).

### Scope

**In scope:**
- `MilvusService` — connection lifecycle, collection schema, insert, stats
- `MilvusRetriever` — top-k query with topic_id filtering
- `TokenChunker` — token-aware document chunking (512 tokens, 50-token overlap)
- `index_findings` orchestrator node — indexes findings into Milvus after dispatch
- Knowledge base stats (chunk count, document count)
- Milvus Lite for dev/tests, configurable URI for production
- New Pydantic models: `DocumentChunk`, `ChunkMetadata`, `ChunkResult`, `KnowledgeBaseStats`
- Configuration via pydantic-settings

**Out of scope:**
- Celery integration (deferred to separate infra ticket)
- RAG research agent (retrieval agent is a service, not an orchestrator agent)
- Full page content fetching (future ticket)
- Writer Agent consumption of retriever (CONTENT-002)
- WebSocket real-time updates (RESEARCH-005)

### Stubs Replaced / Updated

| Change | Location | Detail |
|--------|----------|--------|
| New orchestrator node | `src/agents/research/orchestrator.py` | `index_findings` node added after `dispatch_agents` |
| New `build_graph` params | `src/agents/research/orchestrator.py` | Accepts `milvus_service` and `embedding_service` |

Note: The `stub_research_agent` and `AsyncIODispatcher` are NOT replaced in this ticket. Celery is deferred. The stub is still used in orchestrator unit tests.

---

## 2. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Milvus client | `pymilvus` directly (no langchain-milvus) | More control, follows existing client patterns, avoids extra abstraction |
| Collection strategy | Single `research_chunks` collection, filter by `topic_id` | Simplest for <500K embeddings; metadata filtering is fast in Milvus |
| Indexing location | New `index_findings` orchestrator node after `dispatch_agents` | Keeps agents decoupled from Milvus; indexes per round (retry rounds benefit) |
| Retrieval | Standalone `MilvusRetriever` service | Clean interface for any consumer; not an orchestrator agent |
| Celery | Deferred to separate infra ticket | Orthogonal to RAG; AsyncIODispatcher works fine |
| Token counting | `tiktoken` (cl100k_base) | Accurate token counting for chunking; same tokenizer family as Claude |
| Milvus dev mode | Milvus Lite (`uri="./milvus_data.db"`) | File-based, no server needed; real Milvus in tests |

---

## 3. Milvus Collection Schema

Collection: `research_chunks`

| Field | Type | Description |
|-------|------|-------------|
| `id` | VARCHAR (PK) | UUID string |
| `embedding` | FLOAT_VECTOR(384) | all-MiniLM-L6-v2 output |
| `text` | VARCHAR(65535) | Chunk text |
| `source_url` | VARCHAR(2048) | Original document URL |
| `source_title` | VARCHAR(1024) | Document title |
| `topic_id` | VARCHAR(64) | For metadata filtering |
| `session_id` | VARCHAR(64) | Research session reference |
| `chunk_index` | INT64 | Position within document |
| `created_at` | VARCHAR(32) | ISO timestamp |

**Index:** IVF_FLAT on `embedding` field, `nlist=128`, metric=COSINE.

---

## 4. Service Layer

### MilvusService (connection + CRUD)

```python
class MilvusService:
    def __init__(self, uri: str, collection_name: str) -> None:
        # uri="./milvus_data.db" for Milvus Lite
        # uri="http://host:19530" for production

    def ensure_collection(self) -> None:
        """Create collection with schema if it doesn't exist."""

    async def insert_chunks(
        self, chunks: list[DocumentChunk], embeddings: list[list[float]]
    ) -> int:
        """Insert chunks with embeddings. Returns count inserted.
        Raises ValueError if len(chunks) != len(embeddings)."""

    async def search(
        self, query_embedding: list[float], topic_id: str, top_k: int
    ) -> list[ChunkResult]:
        """Top-k similarity search with topic_id filter."""

    async def get_stats(self, topic_id: str | None = None) -> KnowledgeBaseStats:
        """Collection-level stats, optionally filtered by topic."""

    def close(self) -> None:
        """Close the Milvus connection."""

> **Implementation note (pymilvus is synchronous):** The `pymilvus` SDK is blocking. All Milvus I/O methods (`insert_chunks`, `search`, `get_stats`) must wrap calls in `asyncio.get_event_loop().run_in_executor(None, ...)` to avoid blocking the event loop. This is a single-line wrapper per method.
```

### MilvusRetriever (query service)

```python
class MilvusRetriever:
    def __init__(
        self, milvus_service: MilvusService, embedding_service: EmbeddingService
    ) -> None: ...

    async def retrieve(
        self, query: str, topic_id: str, top_k: int = 5
    ) -> list[ChunkResult]:
        """Embed query, search Milvus, return ranked chunks."""
```

### TokenChunker (pure function module)

```python
class TokenChunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        # Uses tiktoken cl100k_base encoding

    def chunk(self, text: str, metadata: ChunkMetadata) -> list[DocumentChunk]:
        """Split text into token-aware chunks with metadata."""
```

**Behavior:**
- Short text (< chunk_size tokens): 1 chunk, no overlap
- Long text: sliding window of chunk_size tokens, overlap between adjacent chunks
- Empty text: returns empty list

> **Tokenizer note:** `tiktoken cl100k_base` is used for chunking token counts, while `all-MiniLM-L6-v2` uses a WordPiece tokenizer internally. Token counts diverge by ~10-20%. At 512 cl100k_base tokens, the actual WordPiece count is typically 450-540. The embedding model truncates silently at its sequence limit (256 tokens) — this means very long chunks may lose tail content in their embeddings. This is an acceptable trade-off: chunking gives us consistent, predictable chunk sizes, and the model handles overflow gracefully.

---

## 5. Data Models (new in `src/models/research.py`)

```python
class ChunkMetadata(BaseModel, frozen=True):
    source_url: str
    source_title: str
    topic_id: str
    session_id: str

class DocumentChunk(BaseModel, frozen=True):
    text: str
    source_url: str
    source_title: str
    topic_id: str
    session_id: str
    chunk_index: int

class ChunkResult(BaseModel, frozen=True):
    text: str
    source_url: str
    source_title: str
    score: float
    chunk_index: int

class KnowledgeBaseStats(BaseModel, frozen=True):
    total_chunks: int
    total_documents: int      # Unique source_url count
    collection_name: str
    topic_id: str | None = None  # Which topic these stats are for (None = all)
```

---

## 6. Orchestrator Changes

### New node: `index_findings`

Inserted after `dispatch_agents`, before `evaluate_completeness`:

```
plan_research → dispatch_agents → index_findings → evaluate_completeness → [retry or finalize]
```

The node:
1. Reads `state["findings"]` — contains only the current round's findings (the `dispatch_agents` node returns new findings each round; the additive reducer accumulates them in the overall state, but `index_findings` sees only what `dispatch_agents` just returned)
2. For each `FacetFindings`, iterates `sources`
3. Chunks each `SourceDocument.snippet` via `TokenChunker`
4. Batch embeds all chunks via `EmbeddingService.embed()`
5. Inserts into Milvus via `MilvusService.insert_chunks()`
6. Returns empty dict (indexing is a side effect, no state changes)

> **Note:** No delta tracking is needed. Each round's `dispatch_agents` returns only that round's findings. The `index_findings` node indexes everything it receives — simple and correct.

### Updated `build_graph` signature

```python
def build_graph(
    llm: BaseChatModel,
    dispatcher: TaskDispatcher,
    agent_fn: AgentFunction,
    milvus_service: MilvusService | None = None,
    embedding_service: EmbeddingService | None = None,
    chunker: TokenChunker | None = None,
) -> CompiledStateGraph:
```

`milvus_service`, `embedding_service`, and `chunker` are optional — when `None`, the `index_findings` node is a no-op (logs a warning and skips). This preserves backward compatibility: existing tests that don't provide Milvus still work.

### Graph topology change

```
[START] → plan_research → dispatch_agents → index_findings → evaluate_completeness → [should_retry?]
                                ↑                                                          |
                                |←── retry (weak facets only) ─────────────────────────── yes
                                |                                                          |
                             finalize ←──────────────────────────────────────────────────── no
                                ↓
                             [END]
```

The retry loop goes back to `dispatch_agents` (unchanged), which is followed by `index_findings` again — so retry findings are also indexed.

---

## 7. Error Handling

| Failure | Behavior |
|---------|----------|
| Milvus connection failure | `index_findings` logs error, skips indexing, does not fail the graph |
| Milvus insert failure | Log error, skip that batch, continue with remaining |
| Embedding service failure | Log error, skip indexing for this round |
| Milvus search failure (retriever) | Raise `MilvusServiceError` — caller decides how to handle |
| Empty findings (no sources) | Skip indexing (no-op) |
| tiktoken encoding failure | Log warning, skip that chunk |

The `index_findings` node is **non-critical** — indexing failure should never crash the research pipeline. The research can complete without Milvus; retrieval is a future enhancement.

---

## 8. Configuration

Added to `src/config/settings.py`:

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

All configurable via `COGNIFY_MILVUS_*`, `COGNIFY_CHUNK_*`, `COGNIFY_TOP_K_*` environment variables.

---

## 9. File Structure

```
src/
  services/
    milvus_service.py              # NEW: MilvusService + MilvusServiceError
    milvus_retriever.py            # NEW: MilvusRetriever
    chunker.py                     # NEW: TokenChunker
  models/
    research.py                    # MODIFY: add DocumentChunk, ChunkMetadata, ChunkResult, KnowledgeBaseStats
  agents/
    research/
      orchestrator.py              # MODIFY: add index_findings node, update build_graph signature
  config/
    settings.py                    # MODIFY: add milvus_*, chunk_*, top_k_* settings
tests/
  unit/
    services/
      test_chunker.py              # NEW: pure unit tests
      test_milvus_service.py       # NEW: Milvus Lite integration tests
      test_milvus_retriever.py     # NEW: retrieval tests with Milvus Lite
    agents/
      research/
        test_orchestrator.py       # MODIFY: add index_findings tests
```

### New Dependencies (`pyproject.toml`)

```
pymilvus>=2.4.0
tiktoken>=0.7.0
```

Mypy overrides:

```toml
[[tool.mypy.overrides]]
module = "pymilvus.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tiktoken.*"
ignore_missing_imports = true
```

---

## 10. Testing Strategy

### `test_chunker.py` — Pure unit tests (no mocks, no I/O)
- Short text: single chunk
- Long text: multiple chunks with correct overlap
- Empty text: returns empty list
- Metadata preserved on each chunk
- Token count accuracy (verify chunk boundaries)

### `test_milvus_service.py` — Milvus Lite (real embedded Milvus)
- Collection creation with correct schema
- Insert chunks and verify count
- Search returns correct top-k results
- Topic ID filtering works
- Get stats returns correct counts
- Empty collection returns zero stats
- Duplicate chunk ID handling

### `test_milvus_retriever.py` — Milvus Lite + real embeddings
- Index documents, retrieve by query — verify relevance
- Topic ID filtering — only returns matching topic chunks
- Empty collection — returns empty list
- top_k parameter respected

### `test_orchestrator.py` — Modified (mock Milvus)
- `index_findings` node runs between dispatch and evaluate
- Milvus unavailable — node skips gracefully, graph completes
- Existing tests unchanged (no Milvus params → no-op indexing)

**Note:** Milvus Lite tests use a temp file for the DB (`tmp_path` pytest fixture) and clean up automatically. These are real Milvus operations, not mocks.

---

## 11. Acceptance Criteria Mapping

| Acceptance Criteria | How Addressed |
|---|---|
| Documents chunked (512 tokens, 50-token overlap) | `TokenChunker` with tiktoken, configurable via settings |
| Embedded via sentence-transformers (all-MiniLM-L6-v2) | Existing `EmbeddingService.embed()`, reused directly |
| Stored in Milvus with metadata (source, date, topic) | `MilvusService.insert_chunks()` with full metadata schema |
| Top-k retrieval (k=5) by cosine similarity | `MilvusRetriever.retrieve()` with COSINE metric index |
| Milvus Lite for local dev, Milvus standalone for production | `milvus_uri` setting: `"./milvus_data.db"` vs `"http://host:19530"` |
| Knowledge base stats tracked (doc count, embedding count, storage size) | `MilvusService.get_stats()` returning `KnowledgeBaseStats` |
