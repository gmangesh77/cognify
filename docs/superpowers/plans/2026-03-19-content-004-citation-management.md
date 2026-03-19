# CONTENT-004: Citation Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add global citation management to the content pipeline — renumbering, deduplication, validation, URL checks, and references section generation — with upstream metadata (author/date) flowing from SerpAPI through Milvus to the final Citation model.

**Architecture:** Single `manage_citations` pipeline node after `validate_article`. Upstream metadata extension adds optional `date`/`author` fields through SerpAPIResult → SourceDocument → DocumentChunk → Milvus → ChunkResult → CitationRef → Citation. All new fields are optional with defaults for backward compatibility.

**Tech Stack:** Python 3.12, Pydantic, LangGraph, Milvus (pymilvus), httpx, pytest, structlog

**Spec:** `docs/superpowers/specs/2026-03-19-content-004-citation-management-design.md`

**Note:** `pytest-asyncio` is configured with `asyncio_mode = "auto"` in `pyproject.toml`, so async test methods do NOT need `@pytest.mark.asyncio` decorators.

---

## File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `src/services/serpapi_client.py` | SerpAPI HTTP transport | Add `date`/`author` to `SerpAPIResult`, parse in `_parse_results` |
| `src/models/research.py` | Research data models | Add `published_at`/`author` to `SourceDocument`, `ChunkMetadata`, `DocumentChunk`, `ChunkResult` |
| `src/agents/research/web_search.py` | Web search agent | Map `SerpAPIResult.date` → `datetime`, pass `author` to `SourceDocument` |
| `src/agents/research/orchestrator.py` | Research orchestrator | Pass `published_at`/`author` from `SourceDocument` to `ChunkMetadata` |
| `src/services/chunker.py` | Token chunker | Pass `published_at`/`author` from `ChunkMetadata` to `DocumentChunk` |
| `src/services/milvus_service.py` | Milvus vector DB service | Add schema fields, populate on insert, extract on search |
| `src/models/content_pipeline.py` | Content pipeline models | Add `published_at`/`author` to `CitationRef`, add state fields |
| `src/agents/content/section_drafter.py` | Section drafter | Pass metadata from `ChunkResult` to `CitationRef` |
| `src/agents/content/citation_manager.py` | **NEW** — Citation management node | Build global map, renumber, validate, URL check, references |
| `src/agents/content/pipeline.py` | Content pipeline graph | Add `manage_citations` node and edges |
| `src/agents/content/nodes.py` | Node factory functions | Add `make_citations_node` factory |

---

## Task 1: Extend SerpAPIResult with date/author

**Files:**
- Modify: `src/services/serpapi_client.py:22-91`
- Test: `tests/unit/services/test_serpapi_client.py`

- [ ] **Step 1: Write failing tests for date/author parsing**

Add to `tests/unit/services/test_serpapi_client.py`:

```python
class TestSerpAPIClientDateAuthor:
    def test_parse_results_extracts_date_and_author(self) -> None:
        data = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Article Title",
                    "link": "https://example.com/article",
                    "snippet": "Some snippet text.",
                    "date": "Mar 10, 2026",
                    "author": "Jane Smith",
                },
            ]
        }
        client = _make_client()
        results = client._parse_results(data)

        assert len(results) == 1
        assert results[0].date == "Mar 10, 2026"
        assert results[0].author == "Jane Smith"

    def test_parse_results_handles_missing_date_author(self) -> None:
        data = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "No Date Article",
                    "link": "https://example.com/no-date",
                    "snippet": "Snippet without date or author.",
                },
            ]
        }
        client = _make_client()
        results = client._parse_results(data)

        assert len(results) == 1
        assert results[0].date is None
        assert results[0].author is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/services/test_serpapi_client.py::TestSerpAPIClientDateAuthor -v`
Expected: FAIL — `SerpAPIResult` has no `date` or `author` field

- [ ] **Step 3: Add date/author to SerpAPIResult and _parse_results**

In `src/services/serpapi_client.py`, update `SerpAPIResult` (line 22-28):

```python
class SerpAPIResult(BaseModel, frozen=True):
    """Typed search result from SerpAPI organic results."""

    title: str
    link: str
    snippet: str
    position: int
    date: str | None = None
    author: str | None = None
```

Update `_parse_results` (line 75-91) to extract the new fields:

```python
def _parse_results(self, data: dict[str, object]) -> list[SerpAPIResult]:
    """Parse organic_results, skipping entries without snippet."""
    raw: list[dict[str, object]] = data.get("organic_results", [])  # type: ignore[assignment]
    results: list[SerpAPIResult] = []
    for item in raw:
        snippet = item.get("snippet")
        if not snippet:
            continue
        results.append(
            SerpAPIResult(
                title=str(item["title"]),
                link=str(item["link"]),
                snippet=str(snippet),
                position=int(str(item.get("position", 0))),
                date=str(item["date"]) if item.get("date") else None,
                author=str(item["author"]) if item.get("author") else None,
            )
        )
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/services/test_serpapi_client.py -v`
Expected: ALL PASS (new tests + existing tests unchanged)

- [ ] **Step 5: Commit**

```bash
git add src/services/serpapi_client.py tests/unit/services/test_serpapi_client.py
git commit -m "feat: extract date/author from SerpAPI organic results"
```

---

## Task 2: Extend research models with published_at/author

**Files:**
- Modify: `src/models/research.py:38-44,73-79,82-90,93-100`
- Test: `tests/unit/models/test_research_models.py` (extend existing or verify)

- [ ] **Step 1: Write failing tests for new model fields**

Add to `tests/unit/models/test_research_models.py` (or create if not present):

```python
from datetime import UTC, datetime

from src.models.research import (
    ChunkMetadata,
    ChunkResult,
    DocumentChunk,
    SourceDocument,
)


class TestSourceDocumentMetadata:
    def test_published_at_and_author_default_none(self) -> None:
        doc = SourceDocument(
            url="https://example.com",
            title="Title",
            snippet="Snippet",
            retrieved_at=datetime.now(UTC),
        )
        assert doc.published_at is None
        assert doc.author is None

    def test_published_at_and_author_populated(self) -> None:
        dt = datetime(2026, 3, 10, tzinfo=UTC)
        doc = SourceDocument(
            url="https://example.com",
            title="Title",
            snippet="Snippet",
            retrieved_at=datetime.now(UTC),
            published_at=dt,
            author="Jane Smith",
        )
        assert doc.published_at == dt
        assert doc.author == "Jane Smith"


class TestChunkMetadataMetadata:
    def test_new_fields_default_none(self) -> None:
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Title",
            topic_id="tid",
            session_id="sid",
        )
        assert meta.published_at is None
        assert meta.author is None

    def test_new_fields_populated(self) -> None:
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Title",
            topic_id="tid",
            session_id="sid",
            published_at="2026-03-10T00:00:00+00:00",
            author="Jane Smith",
        )
        assert meta.published_at == "2026-03-10T00:00:00+00:00"
        assert meta.author == "Jane Smith"


class TestDocumentChunkMetadata:
    def test_new_fields_default_none(self) -> None:
        chunk = DocumentChunk(
            text="content",
            source_url="https://example.com",
            source_title="Title",
            topic_id="tid",
            session_id="sid",
            chunk_index=0,
        )
        assert chunk.published_at is None
        assert chunk.author is None


class TestChunkResultMetadata:
    def test_new_fields_default_none(self) -> None:
        result = ChunkResult(
            text="content",
            source_url="https://example.com",
            source_title="Title",
            score=0.9,
            chunk_index=0,
        )
        assert result.published_at is None
        assert result.author is None

    def test_new_fields_populated(self) -> None:
        dt = datetime(2026, 3, 10, tzinfo=UTC)
        result = ChunkResult(
            text="content",
            source_url="https://example.com",
            source_title="Title",
            score=0.9,
            chunk_index=0,
            published_at=dt,
            author="Jane Smith",
        )
        assert result.published_at == dt
        assert result.author == "Jane Smith"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/models/test_research_models.py -v -k "Metadata"`
Expected: FAIL — models don't have `published_at`/`author` fields

- [ ] **Step 3: Add fields to all four models**

In `src/models/research.py`:

`SourceDocument` (line 38-44) — add after `retrieved_at`:
```python
class SourceDocument(BaseModel, frozen=True):
    """A document retrieved during research."""

    url: str
    title: str
    snippet: str
    retrieved_at: datetime
    published_at: datetime | None = None
    author: str | None = None
```

`ChunkMetadata` (line 73-79) — add after `session_id`:
```python
class ChunkMetadata(BaseModel, frozen=True):
    """Metadata for a document chunk (passed to TokenChunker)."""

    source_url: str
    source_title: str
    topic_id: str
    session_id: str
    published_at: str | None = None
    author: str | None = None
```

`DocumentChunk` (line 82-90) — add after `chunk_index`:
```python
class DocumentChunk(BaseModel, frozen=True):
    """A chunked document ready for embedding and Milvus storage."""

    text: str
    source_url: str
    source_title: str
    topic_id: str
    session_id: str
    chunk_index: int
    published_at: str | None = None
    author: str | None = None
```

`ChunkResult` (line 93-100) — add after `chunk_index`:
```python
class ChunkResult(BaseModel, frozen=True):
    """A retrieved chunk from Milvus similarity search."""

    text: str
    source_url: str
    source_title: str
    score: float
    chunk_index: int
    published_at: datetime | None = None
    author: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/models/test_research_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite to verify backward compatibility**

Run: `uv run pytest --tb=short -q`
Expected: ALL PASS (new fields are optional with defaults)

- [ ] **Step 6: Commit**

```bash
git add src/models/research.py tests/unit/models/test_research_models.py
git commit -m "feat: add published_at/author to research pipeline models"
```

---

## Task 3: Flow metadata through WebSearchAgent and orchestrator

**Files:**
- Modify: `src/agents/research/web_search.py:90-103`
- Modify: `src/agents/research/orchestrator.py:202-220`
- Modify: `src/services/chunker.py:58-69`
- Test: `tests/unit/agents/research/test_web_search.py` (extend)
- Test: `tests/unit/services/test_chunker.py` (extend)

- [ ] **Step 1: Write failing test for WebSearchAgent date/author flow**

Add to `tests/unit/agents/research/test_web_search.py`:

```python
class TestWebSearchAgentMetadata:
    async def test_to_source_documents_passes_date_and_author(self) -> None:
        results = [
            SerpAPIResult(
                title="Title",
                link="https://example.com",
                snippet="Snippet",
                position=1,
                date="Mar 10, 2026",
                author="Jane Smith",
            ),
            SerpAPIResult(
                title="Title 2",
                link="https://example2.com",
                snippet="Snippet 2",
                position=2,
                date=None,
                author=None,
            ),
        ]
        agent = WebSearchAgent(serpapi_client=AsyncMock(), llm=AsyncMock())
        docs = agent._to_source_documents(results)

        assert docs[0].author == "Jane Smith"
        assert docs[0].published_at is not None
        assert docs[0].published_at.year == 2026
        assert docs[0].published_at.month == 3
        assert docs[0].published_at.day == 10
        assert docs[1].author is None
        assert docs[1].published_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/agents/research/test_web_search.py::TestWebSearchAgentMetadata -v`
Expected: FAIL

- [ ] **Step 3: Update WebSearchAgent._to_source_documents**

In `src/agents/research/web_search.py`, add a date parsing helper and update `_to_source_documents` (line 90-103):

```python
from dateutil.parser import parse as parse_date


def _parse_serpapi_date(date_str: str | None) -> datetime | None:
    """Best-effort parse of SerpAPI date string. Returns None on failure."""
    if not date_str:
        return None
    try:
        return parse_date(date_str)
    except (ValueError, OverflowError):
        logger.warning("serpapi_date_parse_failed", date_string=date_str)
        return None
```

Update `_to_source_documents`:
```python
def _to_source_documents(
    self, results: list[SerpAPIResult]
) -> list[SourceDocument]:
    """Convert SerpAPI results to SourceDocument models."""
    now = datetime.now(UTC)
    return [
        SourceDocument(
            url=r.link,
            title=_sanitize(r.title),
            snippet=_sanitize(r.snippet),
            retrieved_at=now,
            published_at=_parse_serpapi_date(r.date),
            author=r.author,
        )
        for r in results
    ]
```

Note: `python-dateutil` is available transitively (via existing dependencies). Verified with `uv run python -c "from dateutil.parser import parse"`. No need to add it explicitly.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/agents/research/test_web_search.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing test for chunker metadata passthrough**

Add to `tests/unit/services/test_chunker.py`:

```python
class TestTokenChunkerMetadata:
    def test_make_chunk_passes_published_at_and_author(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Title",
            topic_id="tid",
            session_id="sid",
            published_at="2026-03-10T00:00:00+00:00",
            author="Jane Smith",
        )
        chunks = chunker.chunk("Some short text for testing.", meta)

        assert len(chunks) == 1
        assert chunks[0].published_at == "2026-03-10T00:00:00+00:00"
        assert chunks[0].author == "Jane Smith"

    def test_make_chunk_handles_none_metadata(self) -> None:
        chunker = TokenChunker(chunk_size=512, overlap=50)
        meta = ChunkMetadata(
            source_url="https://example.com",
            source_title="Title",
            topic_id="tid",
            session_id="sid",
        )
        chunks = chunker.chunk("Some short text for testing.", meta)

        assert len(chunks) == 1
        assert chunks[0].published_at is None
        assert chunks[0].author is None
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/unit/services/test_chunker.py::TestTokenChunkerMetadata -v`
Expected: FAIL

- [ ] **Step 7: Update TokenChunker._make_chunk**

In `src/services/chunker.py`, update `_make_chunk` (line 58-69):

```python
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
        published_at=metadata.published_at,
        author=metadata.author,
    )
```

- [ ] **Step 8: Update orchestrator._chunk_findings**

In `src/agents/research/orchestrator.py`, update `_chunk_findings` (line 213-218) to pass metadata:

```python
metadata = ChunkMetadata(
    source_url=source.url,
    source_title=source.title,
    topic_id=str(topic.id),
    session_id=session_id,
    published_at=source.published_at.isoformat() if source.published_at else None,
    author=source.author,
)
```

- [ ] **Step 9: Run all tests to verify**

Run: `uv run pytest tests/unit/services/test_chunker.py tests/unit/agents/research/ -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add src/agents/research/web_search.py src/agents/research/orchestrator.py src/services/chunker.py tests/unit/agents/research/test_web_search.py tests/unit/services/test_chunker.py
git commit -m "feat: flow published_at/author through research pipeline"
```

---

## Task 4: Extend Milvus schema and search

**Files:**
- Modify: `src/services/milvus_service.py:58-100,132-152,178-208`
- Test: `tests/unit/services/test_milvus_service.py` (extend)

- [ ] **Step 1: Write failing tests for Milvus metadata fields**

Add to `tests/unit/services/test_milvus_service.py`:

```python
class TestMilvusServiceMetadataFields:
    def test_schema_includes_published_at_and_author(self) -> None:
        service = MilvusService(uri="./test_milvus.db", collection_name="test_col")
        schema = service._build_schema()
        field_names = [f.name for f in schema.fields]
        assert "published_at" in field_names
        assert "author" in field_names

    def test_prepare_insert_data_includes_metadata(self) -> None:
        chunk = DocumentChunk(
            text="content",
            source_url="https://example.com",
            source_title="Title",
            topic_id="tid",
            session_id="sid",
            chunk_index=0,
            published_at="2026-03-10T00:00:00+00:00",
            author="Jane Smith",
        )
        service = MilvusService(uri="./test_milvus.db", collection_name="test_col")
        data = service._prepare_insert_data([chunk], [[0.1] * 384])
        assert data[0]["published_at"] == "2026-03-10T00:00:00+00:00"
        assert data[0]["author"] == "Jane Smith"

    def test_prepare_insert_data_handles_none_metadata(self) -> None:
        chunk = DocumentChunk(
            text="content",
            source_url="https://example.com",
            source_title="Title",
            topic_id="tid",
            session_id="sid",
            chunk_index=0,
        )
        service = MilvusService(uri="./test_milvus.db", collection_name="test_col")
        data = service._prepare_insert_data([chunk], [[0.1] * 384])
        assert data[0]["published_at"] == ""
        assert data[0]["author"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/services/test_milvus_service.py::TestMilvusServiceMetadataFields -v`
Expected: FAIL

- [ ] **Step 3: Add schema fields**

In `src/services/milvus_service.py`, add to `_build_schema` (after line 98, before the return):

```python
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
```

- [ ] **Step 4: Update _prepare_insert_data**

In `src/services/milvus_service.py`, update the dict in `_prepare_insert_data` (line 139-152):

```python
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
        "published_at": chunk.published_at or "",
        "author": chunk.author or "",
    }
    for chunk, emb in zip(chunks, embeddings, strict=True)
]
```

- [ ] **Step 5: Update _sync_search output_fields and ChunkResult construction**

In `src/services/milvus_service.py`, update `_sync_search` (line 190-208):

```python
output_fields=[
    "text",
    "source_url",
    "source_title",
    "chunk_index",
    "published_at",
    "author",
],
```

And update the `ChunkResult` construction:

```python
from datetime import datetime as dt_class

return [
    ChunkResult(
        text=hit["entity"]["text"],
        source_url=hit["entity"]["source_url"],
        source_title=hit["entity"]["source_title"],
        score=hit["distance"],
        chunk_index=hit["entity"]["chunk_index"],
        published_at=_parse_iso_datetime(hit["entity"].get("published_at", "")),
        author=hit["entity"].get("author", "") or None,
    )
    for hit in results[0]
]
```

Add a helper at module level:

```python
def _parse_iso_datetime(value: str) -> datetime | None:
    """Parse ISO 8601 datetime string from Milvus. Returns None for empty."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
```

Note: Import `datetime` from the top — already imported as `from datetime import UTC, datetime`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/services/test_milvus_service.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/services/milvus_service.py tests/unit/services/test_milvus_service.py
git commit -m "feat: add published_at/author to Milvus schema and search"
```

---

## Task 5: Extend CitationRef and section drafter passthrough

**Files:**
- Modify: `src/models/content_pipeline.py:49-54`
- Modify: `src/agents/content/section_drafter.py:147-152`
- Test: `tests/unit/agents/content/test_section_drafter.py` (extend)

- [ ] **Step 1: Write failing test for CitationRef metadata passthrough**

Add to `tests/unit/agents/content/test_section_drafter.py`:

```python
class TestExtractCitationsMetadata:
    def test_passes_through_published_at_and_author(self) -> None:
        dt = datetime(2026, 3, 10, tzinfo=UTC)
        chunks = [
            ChunkResult(
                text="Chunk content",
                source_url="https://example.com",
                source_title="Source",
                score=0.9,
                chunk_index=0,
                published_at=dt,
                author="Jane Smith",
            ),
        ]
        text = "Some claim [1] in the article."
        citations = extract_citations(text, chunks)

        assert len(citations) == 1
        assert citations[0].published_at == dt
        assert citations[0].author == "Jane Smith"

    def test_handles_none_metadata(self) -> None:
        chunks = [
            ChunkResult(
                text="Chunk content",
                source_url="https://example.com",
                source_title="Source",
                score=0.9,
                chunk_index=0,
            ),
        ]
        text = "Some claim [1] in the article."
        citations = extract_citations(text, chunks)

        assert len(citations) == 1
        assert citations[0].published_at is None
        assert citations[0].author is None
```

Add necessary imports at top of test file: `from datetime import UTC, datetime`

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/agents/content/test_section_drafter.py::TestExtractCitationsMetadata -v`
Expected: FAIL — `CitationRef` has no `published_at`/`author`

- [ ] **Step 3: Add fields to CitationRef**

In `src/models/content_pipeline.py` (line 49-54):

```python
class CitationRef(BaseModel, frozen=True):
    """Lightweight citation reference collected during drafting."""

    index: int
    source_url: str
    source_title: str
    published_at: datetime | None = None
    author: str | None = None
```

Add `from datetime import datetime` import at the top (already has `datetime` imported).

- [ ] **Step 4: Update extract_citations in section_drafter.py**

In `src/agents/content/section_drafter.py` (line 147-152):

```python
refs.append(
    CitationRef(
        index=num,
        source_url=chunk.source_url,
        source_title=chunk.source_title,
        published_at=chunk.published_at,
        author=chunk.author,
    )
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_section_drafter.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/models/content_pipeline.py src/agents/content/section_drafter.py tests/unit/agents/content/test_section_drafter.py
git commit -m "feat: extend CitationRef with published_at/author metadata"
```

---

## Task 6: Build citation manager — core functions

**Files:**
- Create: `src/agents/content/citation_manager.py`
- Create: `tests/unit/agents/content/test_citation_manager.py`

- [ ] **Step 1: Write failing tests for build_global_citation_map**

Create `tests/unit/agents/content/test_citation_manager.py`:

```python
"""Tests for citation manager — global renumbering, validation, references."""

from datetime import UTC, datetime

import pytest

from src.models.content import Citation
from src.models.content_pipeline import CitationRef, SectionDraft


class TestBuildGlobalCitationMap:
    def test_deduplicates_by_url(self) -> None:
        from src.agents.content.citation_manager import build_global_citation_map

        drafts = [
            SectionDraft(
                section_index=0,
                title="Sec 1",
                body_markdown="Claim [1] and [2].",
                word_count=10,
                citations_used=[
                    CitationRef(index=1, source_url="https://a.com", source_title="A"),
                    CitationRef(index=2, source_url="https://b.com", source_title="B"),
                ],
            ),
            SectionDraft(
                section_index=1,
                title="Sec 2",
                body_markdown="Claim [1].",
                word_count=10,
                citations_used=[
                    CitationRef(index=1, source_url="https://a.com", source_title="A"),
                ],
            ),
        ]
        citations, remap = build_global_citation_map(drafts)

        assert len(citations) == 2
        urls = {c.url for c in citations}
        assert urls == {"https://a.com", "https://b.com"}

    def test_assigns_sequential_global_indices(self) -> None:
        from src.agents.content.citation_manager import build_global_citation_map

        drafts = [
            SectionDraft(
                section_index=0,
                title="Sec 1",
                body_markdown="[1][2]",
                word_count=5,
                citations_used=[
                    CitationRef(index=1, source_url="https://a.com", source_title="A"),
                    CitationRef(index=2, source_url="https://b.com", source_title="B"),
                ],
            ),
        ]
        citations, _ = build_global_citation_map(drafts)

        assert citations[0].index == 1
        assert citations[1].index == 2

    def test_preserves_author_and_published_at(self) -> None:
        from src.agents.content.citation_manager import build_global_citation_map

        dt = datetime(2026, 3, 10, tzinfo=UTC)
        drafts = [
            SectionDraft(
                section_index=0,
                title="Sec 1",
                body_markdown="[1]",
                word_count=5,
                citations_used=[
                    CitationRef(
                        index=1,
                        source_url="https://a.com",
                        source_title="A",
                        published_at=dt,
                        author="Jane Smith",
                    ),
                ],
            ),
        ]
        citations, _ = build_global_citation_map(drafts)

        assert citations[0].published_at == dt
        assert citations[0].authors == ["Jane Smith"]

    def test_empty_drafts(self) -> None:
        from src.agents.content.citation_manager import build_global_citation_map

        citations, remap = build_global_citation_map([])
        assert citations == []
        assert remap == {}

    def test_remap_table_maps_section_local_to_global(self) -> None:
        from src.agents.content.citation_manager import build_global_citation_map

        drafts = [
            SectionDraft(
                section_index=0,
                title="Sec 1",
                body_markdown="[1]",
                word_count=5,
                citations_used=[
                    CitationRef(index=1, source_url="https://a.com", source_title="A"),
                ],
            ),
            SectionDraft(
                section_index=1,
                title="Sec 2",
                body_markdown="[1][2]",
                word_count=5,
                citations_used=[
                    CitationRef(index=1, source_url="https://c.com", source_title="C"),
                    CitationRef(index=2, source_url="https://a.com", source_title="A"),
                ],
            ),
        ]
        citations, remap = build_global_citation_map(drafts)

        # a.com=1, b.com doesn't exist, c.com=2 (first seen order)
        assert remap[(0, 1)] == 1  # sec 0, local [1] (a.com) -> global 1
        assert remap[(1, 1)] == 2  # sec 1, local [1] (c.com) -> global 2
        assert remap[(1, 2)] == 1  # sec 1, local [2] (a.com) -> global 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/agents/content/test_citation_manager.py::TestBuildGlobalCitationMap -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement build_global_citation_map**

Create `src/agents/content/citation_manager.py`:

```python
"""Citation manager — global renumbering, validation, URL checks, references.

Runs as a pipeline node after validate_article. Bridges CitationRef
(section-level, lightweight) to Citation (global, publication-ready).
"""

import asyncio
import re

import httpx
import structlog

from src.models.content import Citation
from src.models.content_pipeline import SectionDraft

logger = structlog.get_logger()

_MIN_UNIQUE_SOURCES = 5
_URL_CHECK_TIMEOUT = 3.0
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


class CitationValidationError(Exception):
    """Raised when citation validation fails."""


def build_global_citation_map(
    drafts: list[SectionDraft],
) -> tuple[list[Citation], dict[tuple[int, int], int]]:
    """Deduplicate citations by URL, assign global indices, build remap table."""
    url_to_global: dict[str, int] = {}
    url_to_citation: dict[str, Citation] = {}
    remap: dict[tuple[int, int], int] = {}
    next_index = 1

    for draft in drafts:
        for ref in draft.citations_used:
            if ref.source_url not in url_to_global:
                url_to_global[ref.source_url] = next_index
                url_to_citation[ref.source_url] = Citation(
                    index=next_index,
                    title=ref.source_title,
                    url=ref.source_url,
                    authors=[ref.author] if ref.author else [],
                    published_at=ref.published_at,
                )
                next_index += 1
            remap[(draft.section_index, ref.index)] = url_to_global[ref.source_url]

    return list(url_to_citation.values()), remap
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_citation_manager.py::TestBuildGlobalCitationMap -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing tests for renumber_section_markdown**

Add to `tests/unit/agents/content/test_citation_manager.py`:

```python
class TestRenumberSectionMarkdown:
    def test_replaces_citation_indices(self) -> None:
        from src.agents.content.citation_manager import renumber_section_markdown

        md = "This claim [1] and another [2] are important."
        remap = {1: 3, 2: 5}
        result = renumber_section_markdown(md, remap)

        assert "[3]" in result
        assert "[5]" in result
        assert "[1]" not in result
        assert "[2]" not in result

    def test_handles_consecutive_citations(self) -> None:
        from src.agents.content.citation_manager import renumber_section_markdown

        md = "Multiple sources [1][2] confirm this."
        remap = {1: 4, 2: 7}
        result = renumber_section_markdown(md, remap)

        assert "[4][7]" in result

    def test_skips_citations_in_code_blocks(self) -> None:
        from src.agents.content.citation_manager import renumber_section_markdown

        md = "Normal [1] text.\n```\ncode [2] here\n```\nMore [2] text."
        remap = {1: 10, 2: 20}
        result = renumber_section_markdown(md, remap)

        assert "Normal [10] text." in result
        assert "code [2] here" in result  # unchanged in code block
        assert "More [20] text." in result

    def test_no_remap_needed(self) -> None:
        from src.agents.content.citation_manager import renumber_section_markdown

        md = "No citations here."
        result = renumber_section_markdown(md, {})

        assert result == "No citations here."
```

- [ ] **Step 6: Implement renumber_section_markdown**

Add to `src/agents/content/citation_manager.py`:

```python
def renumber_section_markdown(
    markdown: str, remap: dict[int, int]
) -> str:
    """Replace [N] citation indices using the local->global remap.

    Skips citations inside fenced code blocks (``` ... ```).
    """
    if not remap:
        return markdown

    lines = markdown.split("\n")
    result: list[str] = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue
        if in_code_block:
            result.append(line)
            continue
        result.append(
            _CITATION_PATTERN.sub(
                lambda m: f"[{remap.get(int(m.group(1)), int(m.group(1)))}]",
                line,
            )
        )

    return "\n".join(result)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_citation_manager.py::TestRenumberSectionMarkdown -v`
Expected: ALL PASS

- [ ] **Step 8: Write failing tests for validate_citation_count**

Add to `tests/unit/agents/content/test_citation_manager.py`:

```python
class TestValidateCitationCount:
    def test_passes_with_five_sources(self) -> None:
        from src.agents.content.citation_manager import validate_citation_count

        citations = [
            Citation(index=i, title=f"T{i}", url=f"https://{i}.com")
            for i in range(1, 6)
        ]
        validate_citation_count(citations, 5)  # should not raise

    def test_fails_with_four_sources(self) -> None:
        from src.agents.content.citation_manager import (
            CitationValidationError,
            validate_citation_count,
        )

        citations = [
            Citation(index=i, title=f"T{i}", url=f"https://{i}.com")
            for i in range(1, 5)
        ]
        with pytest.raises(CitationValidationError):
            validate_citation_count(citations, 5)

    def test_passes_above_minimum(self) -> None:
        from src.agents.content.citation_manager import validate_citation_count

        citations = [
            Citation(index=i, title=f"T{i}", url=f"https://{i}.com")
            for i in range(1, 9)
        ]
        validate_citation_count(citations, 5)  # should not raise
```

- [ ] **Step 9: Implement validate_citation_count**

Add to `src/agents/content/citation_manager.py`:

```python
def validate_citation_count(
    citations: list[Citation], min_sources: int
) -> None:
    """Raise CitationValidationError if below minimum unique sources."""
    if len(citations) < min_sources:
        msg = (
            f"Insufficient citations: found {len(citations)}, "
            f"required {min_sources}"
        )
        raise CitationValidationError(msg)
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_citation_manager.py::TestValidateCitationCount -v`
Expected: ALL PASS

- [ ] **Step 11: Commit**

```bash
git add src/agents/content/citation_manager.py tests/unit/agents/content/test_citation_manager.py
git commit -m "feat: add citation manager core — build map, renumber, validate"
```

---

## Task 7: Add URL checking and references generation

**Files:**
- Modify: `src/agents/content/citation_manager.py`
- Modify: `tests/unit/agents/content/test_citation_manager.py`

- [ ] **Step 1: Write failing tests for check_urls**

Add to `tests/unit/agents/content/test_citation_manager.py`:

```python
from unittest.mock import AsyncMock, patch


class TestCheckUrls:
    async def test_returns_citations_unchanged(self) -> None:
        from src.agents.content.citation_manager import check_urls

        citations = [
            Citation(index=1, title="T1", url="https://example.com"),
        ]
        with patch("src.agents.content.citation_manager.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.head.return_value = AsyncMock(status_code=200)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_urls(citations)

        assert result == citations

    async def test_logs_warning_for_unreachable_url(self) -> None:
        from src.agents.content.citation_manager import check_urls

        citations = [
            Citation(index=1, title="T1", url="https://unreachable.example"),
        ]
        with patch("src.agents.content.citation_manager.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.head.side_effect = httpx.ConnectError("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_urls(citations)

        assert len(result) == 1  # unchanged
```

Add `import httpx` to the test file imports.

- [ ] **Step 2: Implement check_urls**

Add to `src/agents/content/citation_manager.py`:

```python
async def check_urls(citations: list[Citation]) -> list[Citation]:
    """Async HEAD check on each citation URL. Logs warnings, never removes."""
    async with httpx.AsyncClient(timeout=_URL_CHECK_TIMEOUT) as client:
        tasks = [_check_one_url(client, c) for c in citations]
        await asyncio.gather(*tasks, return_exceptions=True)
    return citations


async def _check_one_url(
    client: httpx.AsyncClient, citation: Citation
) -> None:
    """HEAD-check a single URL, log warning on failure."""
    try:
        resp = await client.head(citation.url)
        if resp.status_code >= 400:
            logger.warning(
                "citation_url_check_failed",
                index=citation.index,
                url=citation.url,
                status_code=resp.status_code,
            )
    except (httpx.HTTPError, httpx.StreamError) as exc:
        logger.warning(
            "citation_url_unreachable",
            index=citation.index,
            url=citation.url,
            error=str(exc),
        )
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_citation_manager.py::TestCheckUrls -v`
Expected: ALL PASS

- [ ] **Step 4: Write failing tests for generate_references_markdown**

Add to `tests/unit/agents/content/test_citation_manager.py`:

```python
class TestGenerateReferencesMarkdown:
    def test_formats_with_all_fields(self) -> None:
        from src.agents.content.citation_manager import generate_references_markdown

        dt = datetime(2026, 3, 15, tzinfo=UTC)
        citations = [
            Citation(
                index=1,
                title="Full Article",
                url="https://example.com/article",
                authors=["Jane Smith"],
                published_at=dt,
            ),
        ]
        result = generate_references_markdown(citations)

        assert "## References" in result
        assert "[1]" in result
        assert "Full Article" in result
        assert "Jane Smith" in result
        assert "2026-03-15" in result
        assert "https://example.com/article" in result

    def test_omits_author_and_date_when_none(self) -> None:
        from src.agents.content.citation_manager import generate_references_markdown

        citations = [
            Citation(index=1, title="Simple", url="https://example.com"),
        ]
        result = generate_references_markdown(citations)

        assert "[1] Simple." in result
        assert "https://example.com" in result
```

- [ ] **Step 5: Implement generate_references_markdown**

Add to `src/agents/content/citation_manager.py`:

```python
def generate_references_markdown(citations: list[Citation]) -> str:
    """Generate a ## References section from global citations."""
    lines = ["## References", ""]
    for c in sorted(citations, key=lambda x: x.index):
        parts = [f"[{c.index}] {c.title}"]
        meta: list[str] = []
        if c.authors:
            meta.append(", ".join(c.authors))
        if c.published_at:
            meta.append(c.published_at.strftime("%Y-%m-%d"))
        if meta:
            parts.append(f" — {', '.join(meta)}")
        parts.append(f". {c.url}")
        lines.append("".join(parts))
    return "\n".join(lines)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_citation_manager.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/agents/content/citation_manager.py tests/unit/agents/content/test_citation_manager.py
git commit -m "feat: add URL checking and references markdown generation"
```

---

## Task 8: Add manage_citations pipeline node and wire into graph

**Files:**
- Modify: `src/agents/content/citation_manager.py` (add node function)
- Modify: `src/agents/content/nodes.py` (add factory)
- Modify: `src/agents/content/pipeline.py` (add node + edges + state fields)
- Modify: `tests/unit/agents/content/test_pipeline.py` (extend)

- [ ] **Step 1: Add manage_citations node function**

Add to `src/agents/content/citation_manager.py`:

```python
from src.agents.content.pipeline import ContentState


async def manage_citations(state: ContentState) -> dict[str, object]:
    """Pipeline node: normalize, renumber, validate, and check citations."""
    drafts = list(state.get("section_drafts", []))
    if not drafts:
        return {"status": "failed", "error": "No section drafts to process"}

    # Coerce dicts back to SectionDraft if needed (LangGraph serialization)
    coerced = [
        d if isinstance(d, SectionDraft) else SectionDraft.model_validate(d)
        for d in drafts
    ]

    citations, remap = build_global_citation_map(coerced)

    # Renumber each section's markdown
    updated_drafts: list[SectionDraft] = []
    for draft in coerced:
        section_remap = {
            local: remap[(draft.section_index, local)]
            for sec_idx, local in remap
            if sec_idx == draft.section_index
        }
        new_md = renumber_section_markdown(draft.body_markdown, section_remap)
        updated_drafts.append(
            draft.model_copy(update={"body_markdown": new_md})
        )

    try:
        validate_citation_count(citations, _MIN_UNIQUE_SOURCES)
    except CitationValidationError as exc:
        logger.error("citation_validation_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}

    await check_urls(citations)

    refs_md = generate_references_markdown(citations)

    logger.info(
        "citation_management_complete",
        unique_sources=len(citations),
        sections_renumbered=len(updated_drafts),
    )

    return {
        "section_drafts": updated_drafts,
        "global_citations": [c.model_dump() for c in citations],
        "references_markdown": refs_md,
    }
```

**Circular import note:** `citation_manager.py` must already have `from __future__ import annotations` at the top (added in Task 6). `ContentState` is only used in the type annotation, not at runtime (the function accesses `state` as a plain dict). Use a `TYPE_CHECKING` guard:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.content.pipeline import ContentState
```

This is the same pattern used in `src/agents/content/nodes.py:26-27`.

- [ ] **Step 2: Update ContentState with new fields**

In `src/agents/content/pipeline.py`, add to `ContentState` (after line 44):

```python
global_citations: NotRequired[list[dict[str, object]]]
references_markdown: NotRequired[str]
```

- [ ] **Step 3: Add make_citations_node factory to nodes.py**

In `src/agents/content/nodes.py`, add:

```python
def make_citations_node() -> Any:  # noqa: ANN401
    """Factory for the citation management node."""
    from src.agents.content.citation_manager import manage_citations
    return manage_citations
```

- [ ] **Step 4: Wire manage_citations into the graph**

In `src/agents/content/pipeline.py`, make two changes to `build_content_graph`:

1. Add import at top with other node imports:
```python
from src.agents.content.nodes import make_citations_node
```

2. After `graph.add_node("validate_article", ...)` (line 62), add:
```python
graph.add_node("manage_citations", make_citations_node())
```

3. Remove the existing edge on line 75:
```python
# REMOVE: graph.add_edge("validate_article", END)
```

4. Add two new edges in its place:
```python
graph.add_edge("validate_article", "manage_citations")
graph.add_edge("manage_citations", END)
```

Note: Using a simple edge to END for now. When CONTENT-006 adds `humanize`, the `manage_citations -> END` edge will be replaced with `manage_citations -> humanize`.

- [ ] **Step 5: Write test for pipeline graph with manage_citations**

Add to `tests/unit/agents/content/test_pipeline.py`:

```python
class TestManageCitationsInGraph:
    def test_graph_includes_manage_citations_node(self) -> None:
        llm = FakeListChatModel(responses=["test"])
        retriever = MagicMock()
        graph = build_content_graph(llm, retriever)
        node_names = list(graph.get_graph().nodes.keys())
        assert "manage_citations" in node_names

    def test_validate_article_routes_to_manage_citations(self) -> None:
        llm = FakeListChatModel(responses=["test"])
        retriever = MagicMock()
        graph = build_content_graph(llm, retriever)
        edges = graph.get_graph().edges
        # Find edge from validate_article
        validate_targets = [
            e.target for e in edges if e.source == "validate_article"
        ]
        assert "manage_citations" in validate_targets
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest --tb=short -q`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/agents/content/citation_manager.py src/agents/content/nodes.py src/agents/content/pipeline.py tests/unit/agents/content/test_pipeline.py
git commit -m "feat: wire manage_citations node into content pipeline graph"
```

---

## Task 9: Integration test — full citation pipeline

**Files:**
- Create: `tests/integration/agents/content/test_citation_pipeline.py`

- [ ] **Step 1: Write integration test for manage_citations node**

Create `tests/integration/agents/content/test_citation_pipeline.py`:

```python
"""Integration tests for the citation management pipeline node."""

from datetime import UTC, datetime

import pytest

from src.agents.content.citation_manager import manage_citations
from src.models.content_pipeline import CitationRef, SectionDraft


@pytest.fixture
def _five_source_drafts() -> list[SectionDraft]:
    """Section drafts with 5+ unique sources for passing validation."""
    return [
        SectionDraft(
            section_index=0,
            title="Section 1",
            body_markdown="Claim [1] and [2] and [3].",
            word_count=50,
            citations_used=[
                CitationRef(
                    index=1,
                    source_url="https://a.com",
                    source_title="Source A",
                    published_at=datetime(2026, 1, 1, tzinfo=UTC),
                    author="Alice",
                ),
                CitationRef(index=2, source_url="https://b.com", source_title="Source B"),
                CitationRef(index=3, source_url="https://c.com", source_title="Source C"),
            ],
        ),
        SectionDraft(
            section_index=1,
            title="Section 2",
            body_markdown="More claims [1] and [2].",
            word_count=50,
            citations_used=[
                CitationRef(index=1, source_url="https://a.com", source_title="Source A"),
                CitationRef(index=2, source_url="https://d.com", source_title="Source D"),
            ],
        ),
        SectionDraft(
            section_index=2,
            title="Section 3",
            body_markdown="Final [1].",
            word_count=50,
            citations_used=[
                CitationRef(index=1, source_url="https://e.com", source_title="Source E"),
            ],
        ),
    ]


class TestManageCitationsIntegration:
    async def test_produces_globally_renumbered_markdown(
        self, _five_source_drafts: list[SectionDraft]
    ) -> None:
        state = {
            "section_drafts": _five_source_drafts,
            "status": "draft_complete",
        }
        result = await manage_citations(state)

        assert result.get("status") != "failed"
        assert "global_citations" in result
        assert "references_markdown" in result
        assert len(result["global_citations"]) == 5

        # Check references section has all sources
        refs = result["references_markdown"]
        assert "## References" in refs
        assert "https://a.com" in refs
        assert "https://e.com" in refs

    async def test_fails_with_insufficient_sources(self) -> None:
        drafts = [
            SectionDraft(
                section_index=0,
                title="Sec",
                body_markdown="[1][2]",
                word_count=10,
                citations_used=[
                    CitationRef(index=1, source_url="https://a.com", source_title="A"),
                    CitationRef(index=2, source_url="https://b.com", source_title="B"),
                ],
            ),
        ]
        state = {"section_drafts": drafts, "status": "draft_complete"}
        result = await manage_citations(state)

        assert result["status"] == "failed"
        assert "Insufficient citations" in str(result["error"])

    async def test_preserves_upstream_metadata(
        self, _five_source_drafts: list[SectionDraft]
    ) -> None:
        state = {
            "section_drafts": _five_source_drafts,
            "status": "draft_complete",
        }
        result = await manage_citations(state)

        citations = result["global_citations"]
        a_citation = next(c for c in citations if c["url"] == "https://a.com")
        assert a_citation["authors"] == ["Alice"]
        assert a_citation["published_at"] is not None
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/integration/agents/content/test_citation_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/agents/content/test_citation_pipeline.py
git commit -m "test: add integration tests for citation management pipeline"
```

---

## Task 10: Final verification and lint

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest --cov=src --cov-report=term-missing --tb=short`
Expected: ALL PASS, coverage maintained or improved

- [ ] **Step 2: Run linter**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
Expected: No errors

- [ ] **Step 3: Run type checker**

Run: `uv run mypy src/agents/content/citation_manager.py src/services/serpapi_client.py src/models/research.py src/models/content_pipeline.py`
Expected: No errors

- [ ] **Step 4: Fix any issues found in steps 1-3**

Address any lint, type, or test failures.

- [ ] **Step 5: Final commit if fixes were needed**

```bash
git add -A
git commit -m "chore: fix lint and type issues from CONTENT-004"
```

- [ ] **Step 6: Verify commit history**

Run: `git log --oneline -10`
Expected: Clean conventional commit history for CONTENT-004
