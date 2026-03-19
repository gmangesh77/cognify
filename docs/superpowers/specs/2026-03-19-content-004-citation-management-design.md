# CONTENT-004: Citation Management — Design Spec

> **Date**: 2026-03-19
> **Ticket**: CONTENT-004
> **Status**: Draft
> **Blocks**: CONTENT-005 (CanonicalArticle Assembly)
> **Story Points**: 5

---

## 1. Overview

Citation Management ensures every article produced by the content pipeline has globally consistent citation numbering, validated source metadata, and a generated references section. It bridges the gap between lightweight `CitationRef` records (created during section drafting) and full `Citation` models (required by `CanonicalArticle`).

### Goals

- Every factual claim has an inline citation `[1]`, `[2]`, etc. with globally unique numbering
- References section generated at article end with full source details
- `CitationRef` upgraded to `Citation` with `authors` and `published_at` from upstream metadata
- Minimum 5 unique sources enforced as a hard gate
- Duplicate citation indices across sections merged and renumbered
- Source URLs validated via async HEAD check (best-effort, non-blocking)

### Non-Goals

- Changing how the section drafter creates citations (existing `extract_citations` logic is reused)
- Assembling the final `CanonicalArticle` (CONTENT-005)
- Switching search providers (stays on SerpAPI)
- Author/date enrichment via HTML scraping or LLM extraction

---

## 2. Decisions Record

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Metadata source for authors/dates | SerpAPI fields (already in response) | Zero extra cost, no latency, no new dependencies |
| Upstream metadata flow | Extend SerpAPIResult → SourceDocument → Milvus → ChunkResult → CitationRef | Data flows from source of truth through existing pipeline layers |
| Citation renumbering strategy | Global renumber + rewrite section markdown | Produces clean, publication-ready markdown with consistent numbering |
| Minimum sources enforcement | Hard fail with configurable threshold (`_MIN_UNIQUE_SOURCES = 5`) | Honors backlog requirement; constant is easy to tune |
| Pipeline node placement | After `validate_article`, before `humanize` (CONTENT-006) | Downstream nodes work with clean, globally-numbered citations |
| Architecture | Single pipeline node with composable internal functions | Follows established pattern; avoids graph complexity |
| URL validation behavior | Best-effort HEAD check with warning logging | HEAD requests are unreliable signals; logging gives visibility without risking article quality |

---

## 3. Upstream Metadata Extension

Flows `date` and `author` from SerpAPI through the entire pipeline. All new fields are optional with defaults, ensuring backward compatibility.

### Layer 1: SerpAPIClient (`src/services/serpapi_client.py`)

```python
class SerpAPIResult(BaseModel, frozen=True):
    title: str
    link: str
    snippet: str
    position: int
    date: str | None = None       # NEW — e.g. "Mar 10, 2026"
    author: str | None = None     # NEW — e.g. "John Smith"
```

`_parse_results` updated to extract `date` and `author` from the raw organic results dict. Both are optional in SerpAPI responses.

### Layer 2: SourceDocument (`src/models/research.py`)

```python
class SourceDocument(BaseModel, frozen=True):
    url: str
    title: str
    snippet: str
    retrieved_at: datetime
    published_at: datetime | None = None  # NEW — parsed from SerpAPI date string
    author: str | None = None             # NEW
```

`WebSearchAgent` maps `SerpAPIResult.date` → `datetime` via best-effort parsing (`None` on failure) and passes `SerpAPIResult.author` through.

### Layer 3: DocumentChunk + ChunkMetadata + Milvus Schema

Both `DocumentChunk` and `ChunkMetadata` in `src/models/research.py` get new fields (they have overlapping field sets — both carry source metadata):

```python
# Added to both DocumentChunk and ChunkMetadata
published_at: str | None = None   # ISO 8601 string for Milvus VARCHAR storage
author: str | None = None
```

`DocumentChunk` is what gets inserted into Milvus (via `_prepare_insert_data`). `ChunkMetadata` is the input to `TokenChunker` — it must carry the fields so they flow into `DocumentChunk` during chunking.

Milvus collection schema in `src/services/milvus_service.py` gets two new `VARCHAR` fields: `published_at`, `author`. Populated on insert, extracted on search.

**Migration note**: Milvus does not support `ALTER COLLECTION` to add fields. Existing dev collections must be dropped and recreated. This only affects local dev environments with indexed data — no production data exists yet.

### Layer 4: ChunkResult (`src/models/research.py`)

```python
class ChunkResult(BaseModel, frozen=True):
    text: str
    source_url: str
    source_title: str
    score: float
    chunk_index: int
    published_at: datetime | None = None  # NEW
    author: str | None = None             # NEW
```

### Layer 5: CitationRef (`src/models/content_pipeline.py`)

```python
class CitationRef(BaseModel, frozen=True):
    index: int
    source_url: str
    source_title: str
    published_at: datetime | None = None  # NEW
    author: str | None = None             # NEW
```

Section drafter's `extract_citations` passes through `published_at` and `author` from `ChunkResult`.

### Data Flow

```
SerpAPI response {date, author}
  -> SerpAPIResult {date, author}
    -> SourceDocument {published_at, author}
      -> DocumentChunk/ChunkMetadata {published_at, author}
        -> Milvus VARCHAR fields
          -> ChunkResult {published_at, author}
            -> CitationRef {published_at, author}
              -> Citation {published_at, authors}
```

---

## 4. Citation Manager Node

### File: `src/agents/content/citation_manager.py` (~150 lines)

New pipeline node with composable internal functions.

### 4.1 `build_global_citation_map`

```
build_global_citation_map(section_drafts: list[SectionDraft])
  -> tuple[list[Citation], dict[tuple[int, int], int]]
```

- Iterates all `CitationRef` across all section drafts
- Deduplicates by URL (exact string match)
- Assigns sequential global indices (1, 2, 3...) to each unique URL
- Builds a composite remap table: `(section_index, local_index) -> global_index`
- Converts each unique `CitationRef` -> `Citation`:
  - `author` (single string or None) -> `authors` (list — `[author]` if present, else `[]`)
  - `published_at` passed through directly
  - `source_url` -> `url`, `source_title` -> `title`
- Returns: list of global `Citation` objects + composite remap table

The caller (`manage_citations`) slices the composite remap into per-section flat maps (`dict[int, int]`, i.e., `local_index -> global_index`) before passing to `renumber_section_markdown`.

### 4.2 `renumber_section_markdown`

```
renumber_section_markdown(markdown: str, remap: dict[int, int]) -> str
```

- Takes a per-section flat remap (`local_index -> global_index`), NOT the composite remap
- Regex replaces all `[N]` with `[M]` using the local->global remap
- Skips `[N]` patterns inside inline code (`` `...` ``) and fenced code blocks (`` ``` ``)
- Handles consecutive citations like `[1][2]`
- Returns rewritten markdown

### 4.3 `validate_citation_count`

```
validate_citation_count(citations: list[Citation], min_sources: int) -> None
```

- `_MIN_UNIQUE_SOURCES = 5` module-level constant
- Checks `len(citations) >= min_sources`
- Raises `CitationValidationError` if below threshold

### 4.4 `check_urls`

```
async check_urls(citations: list[Citation]) -> list[Citation]
```

- Async HEAD request on each unique URL with 3-second timeout using `httpx.AsyncClient` (consistent with SerpAPI client pattern)
- Uses `asyncio.gather` with `return_exceptions=True` for parallel checks
- Logs warning via structlog for unreachable URLs (citation index, URL, status/error)
- Returns citations unchanged — purely observational

### 4.5 `generate_references_markdown`

```
generate_references_markdown(citations: list[Citation]) -> str
```

Produces:

```markdown
## References

[1] Title — Author Name, 2026-03-15. https://example.com/article
[2] Title. https://example.com/other
```

- Omits author/date when not available
- Each entry on its own line

### 4.6 Pipeline Node Function

```
async manage_citations(state: ContentState) -> dict
```

Orchestrates all functions in sequence:

1. `build_global_citation_map(state["section_drafts"])`
2. For each section draft: `renumber_section_markdown(draft.content, section_remap)`
3. `validate_citation_count(citations, _MIN_UNIQUE_SOURCES)` — on failure, returns `{"status": "failed", "error": "..."}`
4. `await check_urls(citations)`
5. `generate_references_markdown(citations)`
6. Returns updated state with rewritten section drafts, global citations, references markdown

### Error Handling

- `CitationValidationError` — defined in `citation_manager.py`
- On validation failure: returns `{"status": "failed", "error": "Insufficient citations: found N, required 5"}` (lowercase `"failed"` matches existing pipeline convention in `nodes.py`)
- On unexpected errors: caught, logged, re-raised (pipeline graph handles via existing error pattern)

---

## 5. Pipeline Graph Integration

### Updated Pipeline Order

```
generate_outline -> generate_queries -> draft_sections -> validate_article -> manage_citations -> END
```

Future tickets extend to:
```
... -> validate_article -> manage_citations -> humanize -> seo_optimize -> compile_article -> END
```

### Conditional Edge

Same pattern as `validate_article`:

- `status == "failed"` -> route to END
- `status != "failed"` -> route to next node (currently END, later `humanize`)

### State Changes

Two new fields on `ContentState` (TypedDict in `pipeline.py`):

```python
class ContentState(TypedDict):
    # ... existing fields ...
    global_citations: list[dict[str, object]]    # Serialized Citation list
    references_markdown: str                      # Generated references section
```

### Section Drafter Change

Minimal change in `extract_citations` — pass through `published_at` and `author` from `ChunkResult` when constructing `CitationRef`:

```python
CitationRef(
    index=ref_index,
    source_url=chunk.source_url,
    source_title=chunk.source_title,
    published_at=chunk.published_at,  # NEW
    author=chunk.author,              # NEW
)
```

### ContentService

No changes. `_aggregate_citations()` and `_store_drafted()` remain unchanged. The `manage_citations` node operates on pipeline state after draft storage, performing global normalization as a separate concern.

---

## 6. Testing Strategy

### Unit Tests (~12 tests)

**`tests/unit/agents/content/test_citation_manager.py`** (NEW)

| # | Test | Function |
|---|------|----------|
| 1 | Deduplicates citations sharing same URL across sections | `build_global_citation_map` |
| 2 | Assigns sequential global indices starting at 1 | `build_global_citation_map` |
| 3 | Preserves author/published_at when available | `build_global_citation_map` |
| 4 | Handles empty citations (no sections, no citations) | `build_global_citation_map` |
| 5 | Replaces `[1]` -> `[3]` correctly based on remap | `renumber_section_markdown` |
| 6 | Handles multiple citations in one sentence `[1][2]` | `renumber_section_markdown` |
| 7 | Skips `[N]` patterns inside code blocks | `renumber_section_markdown` |
| 8 | Passes with exactly 5 unique sources | `validate_citation_count` |
| 9 | Raises `CitationValidationError` with 4 sources | `validate_citation_count` |
| 10 | Logs warning for unreachable URLs, returns unchanged | `check_urls` |
| 11 | Formats citation with all fields (title, author, date, URL) | `generate_references_markdown` |
| 12 | Omits author/date when None | `generate_references_markdown` |

**`tests/unit/services/test_serpapi_client.py`** (extend existing)

| # | Test |
|---|------|
| 13 | Parses `date` and `author` from organic results |
| 14 | Handles missing `date`/`author` fields gracefully (None) |

### Integration Tests (~3 tests)

**`tests/integration/agents/content/test_citation_pipeline.py`** (NEW)

| # | Test |
|---|------|
| 15 | Full pipeline run — `manage_citations` produces globally renumbered markdown with references |
| 16 | Pipeline fails gracefully when < 5 unique sources |
| 17 | Upstream metadata flows: SerpAPIResult date/author -> CitationRef -> Citation |

### Upstream Extension Tests (~4 tests)

Extend existing test files for `SourceDocument`, `DocumentChunk`, `ChunkResult`, `CitationRef` to verify new optional fields serialize/deserialize correctly. Existing tests pass unchanged since new fields have defaults.

### Coverage Target

- `citation_manager.py`: >= 90%
- Modified files: existing coverage maintained

---

## 7. Files Changed

| File | Change | Description |
|------|--------|-------------|
| `src/agents/content/citation_manager.py` | **NEW** | Core citation management: build map, renumber, validate, URL check, generate references (~150 lines) |
| `src/agents/content/pipeline.py` | Modify | Add `manage_citations` node, update graph edges |
| `src/agents/content/section_drafter.py` | Modify | Pass `published_at`/`author` from `ChunkResult` to `CitationRef` (~2 lines) |
| `src/services/serpapi_client.py` | Modify | Add `date`/`author` to `SerpAPIResult`, parse in `_parse_results` |
| `src/agents/research/web_search.py` | Modify | Map `SerpAPIResult.date` -> parsed datetime, pass `author` to `SourceDocument` |
| `src/agents/research/orchestrator.py` | Modify | Pass `published_at`/`author` from `SourceDocument` to `ChunkMetadata` in `index_findings` node |
| `src/models/research.py` | Modify | Add `published_at`/`author` to `SourceDocument`, `DocumentChunk`, `ChunkMetadata`, `ChunkResult` |
| `src/models/content_pipeline.py` | Modify | Add `published_at`/`author` to `CitationRef`, add state fields |
| `src/services/milvus_service.py` | Modify | Add `published_at`/`author` VARCHAR fields to schema, populate on insert (`_prepare_insert_data`), extract on search (`_sync_search` output_fields + `ChunkResult` construction) |
| `src/services/chunker.py` | Modify | Pass `published_at`/`author` from `ChunkMetadata` to `DocumentChunk` in `_make_chunk` |
| `tests/unit/agents/content/test_citation_manager.py` | **NEW** | ~12 unit tests |
| `tests/integration/agents/content/test_citation_pipeline.py` | **NEW** | ~3 integration tests |
| `tests/unit/services/test_serpapi_client.py` | Modify | Add tests for date/author parsing |
| Various existing test files | Modify | Verify backward compat of new optional fields |

**No changes to:** `ContentService`, `content.py` (Citation model), API layer, `MilvusRetriever` (thin pass-through, automatically picks up new `ChunkResult` fields).

**Total new code:** ~150 lines (citation_manager.py) + ~200 lines (tests)
**Total modified:** ~60 lines across 9 existing files
