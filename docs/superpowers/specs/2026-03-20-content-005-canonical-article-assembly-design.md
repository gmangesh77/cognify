# CONTENT-005: CanonicalArticle Assembly — Design Spec

> **Ticket**: CONTENT-005
> **Date**: 2026-03-20
> **Status**: Design approved
> **Depends on**: CONTENT-003 (SEO & AI Discoverability), CONTENT-004 (Citation Management), CONTENT-006 (Content Humanization)
> **Completes**: Epic 3 (Content Generation Pipeline)

---

## 1. Overview

Assembles all intermediate pipeline outputs (section drafts, SEO metadata, citations, provenance) into a complete, validated `CanonicalArticle` — the platform-neutral contract between content generation and publishing (ADR-003). This is a service-layer operation, not a pipeline node.

### Acceptance Criteria (from BACKLOG.md)

- Article body assembly: concatenate section drafts into `body_markdown` with H2 heading hierarchy and references section
- All `CanonicalArticle` fields populated — title, subtitle, body_markdown, summary, key_claims, content_type, seo, citations, visuals (empty), authors, domain, generated_at, provenance, ai_generated
- Pydantic validation of assembled `CanonicalArticle` — all required fields present, summary <= 500 chars, key_claims >= 1, citations >= 1, body_markdown non-empty
- ContentService method: `finalize_article(draft_id) -> CanonicalArticle`
- API endpoint: `GET /api/v1/articles/{article_id}` returns finalized CanonicalArticle
- Status transition: `DRAFT_COMPLETE` -> `COMPLETE`

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Assembly location | Service method, not pipeline node | **Deviation from BACKLOG** which says "compile_article pipeline node". Justified: assembly is not an LLM operation, doesn't need LangGraph state machine. CanonicalArticle is the boundary between generation and publishing (ADR-003). Service owns the boundary crossing. BACKLOG to be updated before implementation. |
| Status value | Reuse existing `COMPLETE` | Already in DraftStatus enum, YAGNI on new values |
| Return type | `CanonicalArticle` directly | The article IS the product, not the draft |
| Storage | New `ArticleRepository` protocol | Separate from draft storage; articles are the published contract |

---

## 2. Assembly Logic

### New file: `src/agents/content/article_assembler.py` (~80 lines)

Pure function, no LLM, no I/O.

**`assemble_canonical_article(draft, topic) -> CanonicalArticle`** (2 params — accesses `draft.seo_result` internally)

Field mapping:

| CanonicalArticle Field | Source | Logic |
|---|---|---|
| `id` | — | `uuid4()` |
| `title` | `draft.outline.title` | Direct |
| `subtitle` | `draft.outline.subtitle` | Direct (may be None) |
| `body_markdown` | `draft.section_drafts` | Compile: H2 per section + references section |
| `summary` | `seo_result.summary` | Direct |
| `key_claims` | `seo_result.key_claims` | Direct |
| `content_type` | `draft.outline.content_type` | Direct |
| `seo` | `seo_result.seo` | Direct (includes structured_data) |
| `citations` | `draft.citations` or `global_citations` | Transform CitationRef -> Citation |
| `visuals` | — | `[]` (VISUAL-001 future) |
| `authors` | — | `["Cognify"]` |
| `domain` | `topic.domain` | Direct |
| `generated_at` | — | `datetime.now(UTC)` |
| `provenance` | `seo_result.provenance` | Direct |
| `ai_generated` | — | `True` |

### Helper functions

- `_compile_body(section_drafts, references_md) -> str` — H2 headings + section bodies + references section at end
- `_build_references(citations) -> str` — regenerate markdown references list: `[1] Title - url` (using same logic as `citation_manager.generate_references_markdown()`)
- `_transform_citations(global_citations) -> list[Citation]` — deserialize `global_citations` (list of Citation dicts from the citation manager, already deduplicated and renumbered) into `Citation` models. This is the primary source — NOT `draft.citations` which contains pre-renumbered `CitationRef` objects.

**Note on `global_citations`**: The pipeline state's `global_citations` field (populated by `citation_manager.py`) contains the authoritative, globally-renumbered citation list. The `_store_drafted` method in `content.py` must be updated to persist `global_citations` and `references_markdown` on the `ArticleDraft` model so `finalize_article` can access them without re-running the pipeline.

### Validation

Two levels:

1. **Business rule validation** (before Pydantic construction):
   - `body_markdown` word count >= 1500 — raise `ValueError` if under
   - `citations` >= 5 unique sources — raise `ValueError` if under (defense-in-depth; citation_manager already enforces this, but assembly re-validates)

2. **Pydantic validation** on `CanonicalArticle(...)` construction — validates field types, `summary <= 500 chars`, `key_claims >= 1`, `citations >= 1`, `body_markdown` not empty. If validation fails, it raises `ValidationError` which the service catches and wraps as `ValueError` with descriptive message.

Helper: `_validate_assembly(body_markdown, citations) -> None` — raises ValueError if business rules violated.

---

## 3. ContentService Extension

### New method

```python
async def finalize_article(self, draft_id: UUID) -> CanonicalArticle:
```

Flow:
1. Load draft via `get_draft(draft_id)` — validate status is `DRAFT_COMPLETE`
2. Validate `draft.seo_result` is not None
3. Load research session — reconstruct `TopicInput` for domain
4. Call `assemble_canonical_article(draft, draft.seo_result, topic)`
5. Store `CanonicalArticle` via `ArticleRepository.create()`
6. Update draft: `status = COMPLETE`, `article_id = article.id`
7. Return the `CanonicalArticle`

### New repository protocol (in `content_repositories.py`)

```python
class ArticleRepository(Protocol):
    async def create(self, article: CanonicalArticle) -> CanonicalArticle: ...
    async def get(self, article_id: UUID) -> CanonicalArticle | None: ...
```

Plus `InMemoryArticleRepository` (dict-based, same pattern as existing repos).

### Extended `ContentRepositories`

```python
@dataclass(frozen=True)
class ContentRepositories:
    drafts: ArticleDraftRepository
    research: ResearchSessionReader
    articles: ArticleRepository  # new
```

**Breaking change** — all call sites constructing `ContentRepositories` need updating (tests, API factory).

### Extended `ArticleDraft`

```python
    article_id: UUID | None = None           # links to finalized CanonicalArticle
    global_citations: list[dict[str, object]] = Field(default_factory=list)  # from citation manager
    references_markdown: str = ""            # from citation manager
```

---

## 4. API Endpoints & Response Schema

### POST `/api/v1/articles/drafts/{draft_id}/finalize`

- Auth: `require_editor_or_above`
- Rate limit: 3/minute
- Status: 201 Created
- Response: `CanonicalArticleResponse`
- Action: `ContentService.finalize_article(draft_id)`

### GET `/api/v1/articles/{article_id}`

- Auth: `require_viewer_or_above`
- Rate limit: 30/minute
- Response: `CanonicalArticleResponse`
- Action: load from `ArticleRepository`

### New response schema: `CanonicalArticleResponse`

```python
class CitationResponse(BaseModel):
    index: int
    title: str
    url: str
    authors: list[str]
    published_at: datetime | None

class ProvenanceResponse(BaseModel):
    research_session_id: UUID
    primary_model: str
    drafting_model: str
    embedding_model: str
    embedding_version: str

class ImageAssetResponse(BaseModel):
    id: UUID
    url: str
    caption: str | None
    alt_text: str | None

class CanonicalArticleResponse(BaseModel):
    id: UUID
    title: str
    subtitle: str | None
    body_markdown: str
    summary: str
    key_claims: list[str]
    content_type: str
    seo: SEOMetadataResponse  # mirrors SEOMetadata, not SEOResult
    citations: list[CitationResponse]
    visuals: list[ImageAssetResponse]
    authors: list[str]
    domain: str
    generated_at: datetime
    provenance: ProvenanceResponse
    ai_generated: bool
```

---

## 5. Error Handling & Logging

### Error scenarios

| Error | Handling | HTTP Status |
|---|---|---|
| Draft not found | `NotFoundError` | 404 |
| Draft not in `DRAFT_COMPLETE` status | `ValueError("draft not ready for finalization")` | 400 |
| `seo_result` is None | `ValueError("SEO optimization not completed")` | 400 |
| Pydantic validation fails on CanonicalArticle | `ValueError` with field details | 400 |
| Article not found (GET) | `NotFoundError` | 404 |

### Structured logging

```python
logger.info("article_finalization_started", draft_id=id)
logger.info("article_assembled", article_id=id, title=title, word_count=N, citation_count=N)
logger.info("article_finalization_complete", draft_id=id, article_id=id)
logger.error("article_finalization_failed", draft_id=id, error=str)
```

---

## 6. Testing Strategy

### Unit tests (~18 tests)

**`test_article_assembler.py`** (~8 tests):
- Happy path: assembles valid CanonicalArticle
- Body markdown has H2 headings per section
- Body markdown has references section at end
- Citations transformed from CitationRef to Citation
- Summary and key_claims from seo_result
- Provenance from seo_result
- Visuals default to empty list
- Validation fails if required fields missing (no outline)

**`test_content_service.py`** (extend, ~4 tests):
- `finalize_article` happy path: returns CanonicalArticle, draft status -> COMPLETE
- Rejects draft not in DRAFT_COMPLETE status
- Rejects unknown draft_id
- Rejects draft with no seo_result

**`test_article_endpoints.py`** (extend, ~4 tests):
- POST finalize returns 201 with CanonicalArticleResponse
- GET article returns 200 with full article
- Auth: viewer cannot POST finalize (403)
- Invalid IDs return 404

**`test_content_pipeline_models.py`** (extend, ~2 tests):
- ArticleDraft with article_id field
- ContentRepositories with articles field

**Total: ~18 new tests.**

---

## 7. File Impact Summary

| File | Action | Est. Lines |
|---|---|---|
| `src/agents/content/article_assembler.py` | **New** — assembly logic, body compilation, citation transform | ~80 |
| `src/services/content.py` | Modify — add `finalize_article()`, delegate to helpers. File is at 207 lines — extract `_store_drafted` and `_aggregate_citations` helpers to reduce, or split finalize into `content_finalize.py` | +15 (net after extraction) |
| `src/services/content_repositories.py` | Modify — add ArticleRepository protocol, InMemory impl, extend ContentRepositories | +25 |
| `src/models/content_pipeline.py` | Modify — add `article_id` to ArticleDraft | +1 |
| `src/api/schemas/articles.py` | Modify — add CanonicalArticleResponse, CitationResponse, ProvenanceResponse, ImageAssetResponse | +35 |
| `src/api/routers/articles.py` | Modify — add POST finalize + GET article endpoints. File is at 184 lines — if exceeds 200, extract finalize/get endpoints to `src/api/routers/canonical_articles.py` | +30 |
| Tests (4 files) | New + extend | ~200 |
| **Total** | | ~396 |

---

## 8. Out of Scope

- **Visual asset generation** — VISUAL-001+ (visuals field is `[]` for now)
- **Publishing pipeline** — Epic 5 (consumes CanonicalArticle via Transformer/Adapter)
- **PostgreSQL persistence** — future infra ticket (in-memory repos for now)
- **S3 storage for markdown/assets** — future infra ticket
- **Article editing/versioning** — not in current backlog
