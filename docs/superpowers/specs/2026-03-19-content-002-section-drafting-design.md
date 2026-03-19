# CONTENT-002: Section-by-Section Drafting with RAG — Design Spec

> **Ticket**: CONTENT-002
> **Date**: 2026-03-19
> **Status**: Design approved
> **Depends on**: CONTENT-001 (outline generation), RESEARCH-003 (RAG pipeline), ARCH-001 (CanonicalArticle contracts)

---

## 1. Overview

Extends the content pipeline to draft each article section sequentially using RAG-retrieved context from Milvus. Each section is grounded in research findings via top-k chunk retrieval, with inline citations. The LLM drafts sections in order, receiving a summary of prior sections for narrative coherence.

### Acceptance Criteria (from BACKLOG.md)

- Each section drafted with top-k RAG context (k=5 relevant chunks)
- All factual claims include inline citations
- Word count targets met per section (200-500 words each)
- Total article length >= 1500 words

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| RAG query strategy | LLM-generated queries | Higher quality retrieval for high-stakes content |
| Output model | Intermediate SectionDraft models | CanonicalArticle assembly deferred to CONTENT-003/004 |
| Word count enforcement | Soft per-section, hard total >= 1500 | Avoids expensive retries, catches genuinely short articles |
| Drafting order | Sequential with prior context | Better narrative coherence for long-form |

---

## 2. Data Models

### New models in `src/models/content_pipeline.py`

```python
class CitationRef(BaseModel, frozen=True):
    """Lightweight citation reference collected during drafting."""
    index: int          # [1], [2], etc.
    source_url: str
    source_title: str


class SectionQueries(BaseModel, frozen=True):
    """Retrieval queries generated for one outline section."""
    section_index: int
    queries: list[str]  # 1-2 focused retrieval queries


class SectionDraft(BaseModel, frozen=True):
    """Drafted content for one article section."""
    section_index: int
    title: str
    body_markdown: str
    word_count: int
    citations_used: list[CitationRef]
```

### Extended ContentState (in `pipeline.py`)

```python
class ContentState(TypedDict):
    # existing (CONTENT-001)
    topic: TopicInput
    research_plan: ResearchPlan | None
    findings: list[FacetFindings]
    session_id: UUID
    outline: ArticleOutline | None
    status: str
    error: str | None
    # new (CONTENT-002) — NotRequired so outline-only invocations don't need them
    section_queries: NotRequired[list[SectionQueries]]
    section_drafts: NotRequired[list[SectionDraft]]
    total_word_count: NotRequired[int]
```

### Extended ArticleDraft

```python
class ArticleDraft(BaseModel):
    # existing fields...
    section_drafts: list[SectionDraft] = Field(default_factory=list)
    citations: list[CitationRef] = Field(default_factory=list)
    total_word_count: int = 0
```

### DraftStatus — clarification

The existing `DraftStatus` enum already has `DRAFTING = "drafting"` and `COMPLETE = "complete"`. CONTENT-002 adds one new value: `DRAFT_COMPLETE = "draft_complete"` to distinguish "sections drafted but not yet SEO-optimized" from the final `COMPLETE` state.

Full status progression across content pipeline tickets:
```
OUTLINE_GENERATING → OUTLINE_COMPLETE → DRAFTING → DRAFT_COMPLETE → COMPLETE → FAILED
                     (CONTENT-001)       (CONTENT-002)               (CONTENT-003/004)
```

`DRAFT_COMPLETE` means: all sections drafted with RAG context and citations, but SEO optimization (CONTENT-003) and citation validation (CONTENT-004) have not yet run. `COMPLETE` is reserved for the fully finished article.

---

## 3. LangGraph Pipeline Extension

### Updated graph topology

```
[START] → generate_outline → [conditional] → generate_queries → draft_sections → validate_article → [END]
                                  ↓ (no retriever)
                                [END]
```

### Graph builder signature

```python
def build_content_graph(
    llm: BaseChatModel,
    retriever: MilvusRetriever | None = None,
) -> CompiledStateGraph:
```

When `retriever` is None, the graph stops after `generate_outline` (backward compatible with CONTENT-001). When provided, the full drafting pipeline runs.

### Conditional edge

```python
def _should_draft(state: ContentState) -> str:
    """Route to drafting if outline exists and retriever is available."""
    if state.get("outline") is not None:
        return "generate_queries"
    return END
```

The retriever availability is captured via closure when building the graph — the conditional checks only whether an outline was produced.

### Node: generate_queries

- **Input**: `outline.sections` from state
- **Output**: `{"section_queries": list[SectionQueries]}`
- Single LLM call with all sections at once (cheaper than per-section calls, avoids redundant queries)
- Retry: max 2 on JSON parse / validation errors

### Node: draft_sections

- **Input**: `outline`, `section_queries`, `findings` from state
- **Logic**: Sequential loop over sections (in order for narrative coherence):
  1. Retrieve chunks per query via `retriever.retrieve(query, topic_id, top_k=5)`
  2. Deduplicate by `(source_url, chunk_index)`, keep highest score
  3. Take top 5 unique chunks after dedup
  4. Build prompt with section outline, RAG chunks, prior sections summary
  5. Call LLM to draft section with inline citations
  6. Parse output, extract citation refs, count words
  7. Append SectionDraft to list
- **Output**: `{"section_drafts": list[SectionDraft], "status": "draft_complete"}`

### Node: validate_article

- **Input**: `section_drafts` from state
- **Logic**:
  1. Sum word counts across all sections
  2. If total < 1500: re-draft shortest section with "expand" instruction (one retry only)
  3. Log per-section word counts, warn if outside 200-500 range
  4. Collect and deduplicate all CitationRefs by URL
- **Output**: `{"total_word_count": int, "section_drafts": list[SectionDraft], "citations": list[CitationRef], "status": "draft_complete"}`

---

## 4. Section Drafter Module

### New file: `src/agents/content/section_drafter.py` (~100 lines)

Dependencies bundled into a context object to respect the max 3 params rule:

```python
@dataclass(frozen=True)
class DraftingContext:
    """Shared dependencies for section drafting."""
    retriever: MilvusRetriever
    topic_id: str
    llm: BaseChatModel
    prior_drafts: list[SectionDraft]


async def draft_section(
    section: OutlineSection,
    queries: SectionQueries,
    ctx: DraftingContext,
) -> SectionDraft:
```

The caller (the `draft_sections` graph node) constructs a `DraftingContext` once and updates `prior_drafts` after each section is drafted.

### Retrieval strategy

1. Run all queries from SectionQueries through `retriever.retrieve(query, topic_id, top_k=5)`
2. Merge results, deduplicate by `(source_url, chunk_index)` — keep highest score
3. Take top 5 unique chunks after dedup
4. Format as numbered context blocks for the prompt

### Prompt structure

**System prompt:**
> You are an expert long-form writer. Draft a section of an article using the provided research context. Every factual claim must include an inline citation like [1], [2] referencing the numbered sources. Write in a clear, authoritative tone. Target approximately {target_word_count} words.

**User prompt includes:**
- Section title and description (from outline)
- Key points to cover (from outline)
- Target word count
- RAG context: numbered chunks with source attribution
  ```
  [1] Source: "Title" (url)
  Content: chunk text...
  ```
- Prior sections summary: title + first sentence of each prior draft (for narrative continuity)

**Output:** Raw markdown text for the section body.

### Citation extraction

Post-LLM, parse drafted text for `[N]` references using regex. Map each N to the corresponding RAG chunk's source_url and source_title. Build `list[CitationRef]`. Invalid references (number doesn't map to a provided source) are stripped and logged as warnings.

### Query Generator

### New file: `src/agents/content/query_generator.py` (~60 lines)

```python
async def generate_section_queries(
    outline: ArticleOutline,
    llm: BaseChatModel,
) -> list[SectionQueries]:
```

Single LLM call with all sections. Prompt asks for 1-2 retrieval queries per section optimized for semantic similarity search. Returns JSON, validated into `list[SectionQueries]` via Pydantic. Retry: max 2 on parse/validation errors.

---

## 5. ContentService & API Extension

### ContentService changes (`src/services/content.py`)

**Extended constructor:**
```python
class ContentService:
    def __init__(
        self,
        repos: ContentRepositories,
        llm: BaseChatModel,
        retriever: MilvusRetriever | None = None,
    ) -> None:
```

**New method:**
```python
async def draft_article(self, draft_id: UUID) -> ArticleDraft:
    """Load an outline-complete draft, run section drafting, return updated draft."""
```

Flow:
1. Load draft via `repos.drafts.get(draft_id)` — validate status is `OUTLINE_COMPLETE`
2. Load research session via `repos.research.get(draft.session_id)` — reconstruct findings
3. Build content graph with retriever: `build_content_graph(self._llm, self._retriever)`
4. Invoke graph with existing outline + findings in state
5. Store updated draft with section_drafts, citations, total_word_count, status `DRAFT_COMPLETE`
6. Return updated draft

**Repository extension:**
```python
class ArticleDraftRepository(Protocol):
    async def create(self, draft: ArticleDraft) -> ArticleDraft: ...
    async def get(self, draft_id: UUID) -> ArticleDraft | None: ...
    async def update(self, draft: ArticleDraft) -> ArticleDraft: ...  # new
```

### API endpoint (`src/api/routers/articles.py`)

```
POST /api/v1/articles/drafts/{draft_id}/sections
```
- Auth: `require_editor_or_above`
- Rate limit: 3/minute
- Status: 201 Created
- Response: `ArticleDraftResponse` (extended with section drafts)

### API schema extension (`src/api/schemas/articles.py`)

**New schemas:**
```python
class CitationRefResponse(BaseModel):
    index: int
    source_url: str
    source_title: str

class SectionDraftResponse(BaseModel):
    section_index: int
    title: str
    body_markdown: str
    word_count: int
    citations_used: list[CitationRefResponse]
```

**Extended ArticleDraftResponse:**
```python
class ArticleDraftResponse(BaseModel):
    # existing fields...
    section_drafts: list[SectionDraftResponse] = []
    citations: list[CitationRefResponse] = []
    total_word_count: int = 0
```

Backward compatible — existing outline-only drafts return empty lists and zero word count.

### Retriever wiring note

For tests, `MilvusRetriever` is mocked (AsyncMock). Production wiring of `MilvusRetriever` (requires `MilvusService` + `EmbeddingService`) is deferred to a future infrastructure ticket. The API endpoint factory follows the same `app.state` test-injection pattern used in CONTENT-001.

---

## 6. Error Handling & Logging

### Error scenarios

| Error | Handling | HTTP Status |
|---|---|---|
| Draft not found | `NotFoundError` | 404 |
| Draft not in `OUTLINE_COMPLETE` status | `ValueError("draft not ready for drafting")` | 400 |
| Retriever not configured | `ValueError("retriever required for drafting")` | 500 |
| LLM fails to generate queries (after 2 retries) | `ValueError`, draft status → `FAILED` | 500 |
| LLM fails to draft a section (after 2 retries) | Skip section, log error, continue. If >50% fail → `FAILED` | 500 |
| RAG retrieval returns 0 chunks for a section | Draft without RAG context (findings-only fallback), log warning | — |
| Total word count < 1500 after validation retry | Accept draft, log warning. Human reviewer decides | — |

### Structured logging events

```python
# query_generator.py
logger.info("section_queries_generated", section_count=N, total_queries=M)

# section_drafter.py (per section)
logger.info("section_draft_started", section_index=i, title=title)
logger.info("section_chunks_retrieved", section_index=i, chunk_count=N, unique_sources=M)
logger.info("section_draft_complete", section_index=i, word_count=W, citations_count=C)
logger.warning("section_word_count_outside_range", section_index=i, word_count=W, target=T)
logger.warning("citation_reference_invalid", section_index=i, ref_number=N)

# validate node
logger.info("article_draft_validated", total_words=W, section_count=N, unique_citations=C)
logger.warning("article_below_word_target", total_words=W, target=1500, shortest_section=i)
logger.info("section_redraft_triggered", section_index=i, previous_words=W)

# content service
logger.info("article_drafting_started", draft_id=id, section_count=N)
logger.info("article_drafting_complete", draft_id=id, total_words=W, duration_seconds=D)
logger.error("article_drafting_failed", draft_id=id, error=str)
```

### Retry strategy

Same pattern as `outline_generator.py`: max 2 retries on JSON parse and validation errors, with logged warnings per attempt. Applied to `generate_section_queries` and `draft_section`.

---

## 7. Testing Strategy

### Unit tests (~17 tests)

**`test_query_generator.py`** (~5 tests):
- Happy path: generates 1-2 queries per section from a 5-section outline
- Validates output structure (list of SectionQueries, correct indices)
- Malformed JSON retry and eventual failure
- Single-section edge case

**`test_section_drafter.py`** (~8 tests):
- Happy path: drafts section with 5 RAG chunks, output contains citations
- Citation extraction: [1], [2] mapped to correct sources
- Invalid citation reference stripped and warned
- Zero chunks fallback: drafts without RAG context
- Deduplication: 2 queries returning overlapping chunks → top 5 unique
- Prior context summary included in prompt (verify via LLM call args)
- Word count calculated correctly

**`test_content_pipeline_models.py`** (extend, ~4 tests):
- SectionDraft, SectionQueries, CitationRef construction and frozen immutability
- DraftStatus new enum values

### Pipeline tests (~4 tests)

**`test_pipeline.py`** (extend):
- Full graph with retriever: outline → queries → drafts → validate → done
- Graph without retriever: stops after outline (backward compat)
- Failure in query generation sets status to failed
- Failure in >50% sections sets status to failed

### Service tests (~5 tests)

**`test_content_service.py`** (extend):
- `draft_article()` happy path: loads draft, runs pipeline, stores updated draft
- Rejects draft not in `OUTLINE_COMPLETE` status
- Rejects unknown draft_id (NotFoundError)
- Validates retriever is required
- Draft status transitions: `OUTLINE_COMPLETE` → `DRAFT_COMPLETE`

### API tests (~4 tests)

**`test_article_endpoints.py`** (extend):
- POST drafts/{id}/sections returns 201 with section drafts
- Auth: editor can draft, viewer cannot (403)
- Invalid draft_id returns 404
- Draft not ready returns 400

### Validation tests (~3 tests)

**`test_validate_article.py`**:
- Total >= 1500 words passes
- Total < 1500 triggers re-draft of shortest section
- Per-section warnings logged for out-of-range word counts

**Total: ~33 new tests.** All use FakeLLM and mocked MilvusRetriever, consistent with existing patterns.

---

## 8. File Impact Summary

| File | Action | Est. Lines |
|---|---|---|
| `src/models/content_pipeline.py` | Extend — add CitationRef, SectionQueries, SectionDraft, DraftStatus values | +30 |
| `src/agents/content/query_generator.py` | **New** — LLM query generation | ~60 |
| `src/agents/content/section_drafter.py` | **New** — DraftingContext + RAG retrieval + LLM drafting + citation extraction | ~100 |
| `src/agents/content/pipeline.py` | Extend — add 3 nodes, conditional edge, retriever param | +50 |
| `src/services/content.py` | Extend — add `draft_article()`, update constructor, add repo.update | +40 |
| `src/api/routers/articles.py` | Extend — add POST drafts/{id}/draft endpoint | +25 |
| `src/api/schemas/articles.py` | Extend — add CitationRefResponse, SectionDraftResponse, extend ArticleDraftResponse | +20 |
| Tests (6 files) | New + extend | ~400 |
| **Total** | | ~715 |

---

## 9. Out of Scope

- **CanonicalArticle assembly** — deferred to CONTENT-003/004
- **SEO metadata generation** — CONTENT-003
- **Citation validation (broken URLs, minimum 5 sources)** — CONTENT-004
- **Visual asset references** — VISUAL-001+
- **Celery background execution** — future infra ticket
- **PostgreSQL persistence** — future infra ticket (in-memory repos for now)
