# CONTENT-003: SEO & AI Discoverability — Design Spec

> **Ticket**: CONTENT-003
> **Date**: 2026-03-19
> **Status**: Design approved
> **Depends on**: CONTENT-002 (section drafting), ARCH-001 (CanonicalArticle contracts)
> **Blocks**: CONTENT-005 (CanonicalArticle assembly)

---

## 1. Overview

Adds a `seo_optimize` pipeline node that generates traditional SEO metadata and AI discoverability fields. Two LLM calls: one for SEO (meta title, description, keywords), one for AI discoverability (summary, key_claims). JSON-LD structured data and provenance assembled programmatically. AI disclosure is a static template.

### Acceptance Criteria (from BACKLOG.md)

#### Traditional SEO
- Primary keyword in title, H1, first paragraph, meta description
- Meta title 50-60 chars, meta description 150-160 chars
- Keyword density 1-2% for primary keyword
- Headings (H2, H3) contain secondary keywords
- Readability score: Flesch-Kincaid grade 10-12

#### AI Discoverability
- Summary generation (1-2 sentences, max 500 chars) → `CanonicalArticle.summary`
- Key claims extraction (3-5 factual claims with citation indices) → `CanonicalArticle.key_claims`
- JSON-LD Schema.org Article structured data → `SEOMetadata.structured_data`
- Provenance population from runtime config → `CanonicalArticle.provenance`
- AI disclosure static template → drives per-platform rendering

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| JSON-LD location | `SEOMetadata.structured_data` dict | SEO metadata is the single container for all discoverability concerns |
| LLM call strategy | Two calls (SEO + AI discoverability) | Different tasks, cleaner separation, cheaper retries |
| Provenance source | pydantic-settings config | Reliable, follows existing config pattern |
| AI disclosure | Static template constant | Consistency across articles, compliance concern not creative |
| Default LLM models | Both `claude-sonnet-4` | Capable enough for all tasks, cost-effective |

---

## 2. Data Models

### Extend `SEOMetadata` in `src/models/content.py`

Add a typed JSON-LD model and `structured_data` field:

```python
class SchemaOrgAuthor(BaseModel, frozen=True):
    type: str = Field(default="Organization", alias="@type")
    name: str = "Cognify"

class StructuredDataLD(BaseModel, frozen=True):
    """Typed JSON-LD Schema.org Article structured data."""
    context: str = Field(default="https://schema.org", alias="@context")
    type: str = Field(default="Article", alias="@type")
    headline: str
    description: str
    keywords: list[str] = Field(default_factory=list)
    author: SchemaOrgAuthor = Field(default_factory=SchemaOrgAuthor)
    date_published: str = Field(alias="datePublished")
    date_modified: str = Field(alias="dateModified")

    model_config = ConfigDict(populate_by_name=True)

class SEOMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=70)
    description: str = Field(min_length=1, max_length=170)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    canonical_url: str | None = None
    structured_data: StructuredDataLD | None = None
```

None by default for backward compatibility. Platform transformers serialize it via `structured_data.model_dump(by_alias=True)` and render as `<script type="application/ld+json">`.

### New intermediate model in `src/models/content_pipeline.py`

```python
class SEOResult(BaseModel, frozen=True):
    """Output of the seo_optimize pipeline node."""
    seo: SEOMetadata
    summary: str
    key_claims: list[str]
    provenance: Provenance
    ai_disclosure: str
```

### Extend ContentState in `pipeline.py`

```python
    seo_result: NotRequired[SEOResult]
```

### Extend ArticleDraft in `content_pipeline.py`

```python
    seo_result: SEOResult | None = None
```

### Settings extension in `src/config/settings.py`

```python
    primary_model_name: str = "claude-sonnet-4"
    drafting_model_name: str = "claude-sonnet-4"
    # Note: embedding_model already exists in Settings as "all-MiniLM-L6-v2" — reuse it
    embedding_version: str = "v1"
```

---

## 3. SEO Optimizer Module

### New file: `src/agents/content/seo_optimizer.py` (~120 lines)

#### Function 1: `generate_seo_metadata`

```python
async def generate_seo_metadata(
    article_title: str,
    body_text: str,
    llm: BaseChatModel,
) -> SEOMetadata:
```

- System prompt: "You are an SEO specialist. Generate optimized metadata for this article."
- LLM returns JSON: `{"title": "...", "description": "...", "keywords": [...]}`
- Parsed and validated into `SEOMetadata` via Pydantic (title 50-70 chars, description 1-170 chars)
- Retry: max 2 on parse failure

#### New model: `AIDiscoverabilityResult`

```python
class AIDiscoverabilityResult(BaseModel, frozen=True):
    """LLM-extracted summary and key claims."""
    summary: str = Field(max_length=500)
    key_claims: list[str] = Field(min_length=1, max_length=10)
```

Lives in `src/models/content_pipeline.py` alongside other intermediate models.

#### Function 2: `generate_ai_discoverability`

```python
async def generate_ai_discoverability(
    section_drafts: list[SectionDraft],
    citations: list[CitationRef],
    llm: BaseChatModel,
) -> AIDiscoverabilityResult:
```

- System prompt: "You are a content analyst. Extract a concise summary and key factual claims from this article."
- Input: concatenated section titles + body text + citation list
- LLM returns JSON: `{"summary": "...", "key_claims": ["claim [1]...", ...]}`
- Parsed and validated into `AIDiscoverabilityResult` via Pydantic
- If summary > 500 chars: truncate at sentence boundary before validation, log warning
- Retry: max 2

#### Function 3: `build_structured_data` (pure, no LLM)

```python
def build_structured_data(
    seo: SEOMetadata,
    article_title: str,
    generated_at: str,
) -> StructuredDataLD:
```

Assembles a typed `StructuredDataLD` model from existing data:

```python
StructuredDataLD(
    headline=article_title,
    description=seo.description,
    keywords=seo.keywords,
    date_published=generated_at,
    date_modified=generated_at,
)
```

Pure assembly, no LLM call. Serialized to JSON-LD via `model_dump(by_alias=True)`.

#### Constant

```python
AI_DISCLOSURE_TEXT = (
    "This article was generated using AI research and writing tools. "
    "All claims are sourced and cited."
)
```

---

## 4. Pipeline Integration

### Updated graph topology

```
[START] → generate_outline → [conditional] → generate_queries → draft_sections → validate_article → seo_optimize → [END]
```

The `seo_optimize` node only runs as part of the full drafting pipeline (when `retriever is not None`). Outline-only mode is unaffected.

### Node: `seo_optimize`

Added as a separate `src/agents/content/seo_node.py` file (since `nodes.py` is at 183 lines, adding here would exceed 200). The factory `make_seo_node(llm, settings)` is imported into `pipeline.py`:

1. Read `section_drafts`, `outline`, and `session_id` from state
2. Concatenate section bodies into a single `body_text`
3. Call `generate_seo_metadata(outline.title, body_text, llm)` — first LLM call
4. Collect citations from section_drafts
5. Call `generate_ai_discoverability(section_drafts, citations, llm)` — second LLM call
6. Build `Provenance` from `settings` config + `session_id` from state
7. Call `build_structured_data(seo, outline.title, datetime.now(UTC).isoformat())` — pure, no LLM
8. Set `seo.structured_data = structured_data`
9. Return `{"seo_result": SEOResult(...)}`

On exception: return `{"status": "failed", "error": str(exc)}`

### Graph wiring

```python
graph.add_node("seo_optimize", make_seo_node(llm, settings))
graph.add_edge("validate_article", "seo_optimize")
graph.add_edge("seo_optimize", END)
```

Replaces the current `validate_article → END` edge.

### `build_content_graph` signature

```python
def build_content_graph(
    llm: BaseChatModel,
    retriever: MilvusRetriever | None = None,
    settings: Settings | None = None,
) -> CompiledStateGraph:
```

Settings is optional — when None (tests, outline-only), the `make_seo_node` factory creates `Settings()` with defaults (`claude-sonnet-4`, etc.): `settings = settings or Settings()`.

---

## 5. ContentService Extension

### ContentDeps dataclass

To avoid exceeding max 3 params on `ContentService.__init__`:

```python
@dataclass(frozen=True)
class ContentDeps:
    llm: BaseChatModel
    retriever: MilvusRetriever | None = None
    settings: Settings | None = None

class ContentService:
    def __init__(self, repos: ContentRepositories, deps: ContentDeps) -> None:
        self._repos = repos
        self._deps = deps
```

**Breaking change** — all call sites need updating:
- `src/api/routers/articles.py` (`_get_content_service` factory)
- `tests/unit/services/test_content_service.py` (all `_make_service*` helpers)
- `tests/unit/api/test_article_endpoints.py` (all app fixtures)

**File size**: `content.py` is already at ~200 lines. Move `ContentDeps` into `content_repositories.py` (which already holds the repository protocols). This keeps `content.py` focused on `ContentService` business logic.

### Updated `_store_drafted`

Stores `seo_result` from pipeline output on the `ArticleDraft`.

### API response extension

Extend `ArticleDraftResponse` with optional SEO result fields:

```python
class SEOResultResponse(BaseModel):
    title: str
    description: str
    keywords: list[str]
    summary: str
    key_claims: list[str]
    ai_disclosure: str
    structured_data: StructuredDataLDResponse | None = None

class StructuredDataLDResponse(BaseModel):
    headline: str
    description: str
    keywords: list[str]
    date_published: str
    date_modified: str

class ArticleDraftResponse(BaseModel):
    # existing fields...
    seo_result: SEOResultResponse | None = None
```

No new endpoints — existing `POST /articles/drafts/{draft_id}/sections` now returns seo_result data.

---

## 6. Error Handling & Logging

### Error scenarios

| Error | Handling | Impact |
|---|---|---|
| SEO LLM call fails (after 2 retries) | Node sets `status: "failed"` | Draft stays at DRAFT_COMPLETE |
| AI discoverability LLM call fails (after 2 retries) | Node sets `status: "failed"` | No summary/key_claims |
| SEO title outside 50-60 chars | Accept with warning | Minor quality issue |
| Summary > 500 chars | Truncate at sentence boundary, log warning | Pydantic would reject otherwise |
| key_claims < 3 or > 5 | Accept (1-10 range), log warning | Soft target |
| Settings not provided | Use default model names | Works in tests and dev |

### Structured logging events

```python
# seo_optimizer.py
logger.info("seo_metadata_generated", title_len=N, description_len=N, keyword_count=N)
logger.info("ai_discoverability_generated", summary_len=N, key_claims_count=N)
logger.info("structured_data_assembled", schema_type="Article")

# seo node in nodes.py
logger.info("seo_optimize_complete", has_seo=True, has_summary=True, has_key_claims=True)
logger.error("seo_optimize_failed", error=str)
logger.warning("seo_title_outside_range", title_len=N)
logger.warning("summary_truncated", original_len=N, truncated_len=N)
```

### Retry strategy

Same pattern as `outline_generator.py` and `query_generator.py`: max 2 retries on JSON parse and validation errors.

---

## 7. Testing Strategy

### Unit tests (~12 tests)

**`test_seo_optimizer.py`** (~10 tests):
- `test_generate_seo_metadata_happy_path` — valid title, description, keywords
- `test_seo_metadata_retries_on_bad_json`
- `test_seo_metadata_raises_after_max_retries`
- `test_generate_ai_discoverability_happy_path` — summary + key_claims
- `test_ai_discoverability_retries_on_bad_json`
- `test_ai_discoverability_raises_after_max_retries`
- `test_build_structured_data` — JSON-LD has @context, @type, headline, author
- `test_build_structured_data_includes_keywords`
- `test_summary_truncated_if_over_500_chars`
- `test_ai_disclosure_constant`

**`test_content_pipeline_models.py`** (extend, ~2 tests):
- `test_seo_result_construct`
- `test_seo_result_frozen`

### Pipeline tests (~2 tests)

**`test_pipeline.py`** (extend):
- `test_full_graph_produces_seo_result` — state has seo_result after full run
- `test_seo_failure_sets_failed_status`

### Service tests (~2 tests)

**`test_content_service.py`** (extend):
- `test_draft_article_includes_seo_result`
- `test_content_deps_replaces_constructor`

**Total: ~18 new tests.** All use FakeLLM, consistent with existing patterns.

---

## 8. File Impact Summary

| File | Action | Est. Lines |
|---|---|---|
| `src/models/content.py` | Modify — add StructuredDataLD, SchemaOrgAuthor, structured_data field | +25 |
| `src/models/content_pipeline.py` | Modify — add AIDiscoverabilityResult, SEOResult, extend ArticleDraft | +20 |
| `src/config/settings.py` | Modify — add 4 model name fields | +4 |
| `src/agents/content/seo_optimizer.py` | **New** — two LLM functions + JSON-LD assembler + constant | ~120 |
| `src/agents/content/seo_node.py` | **New** — make_seo_node factory (extracted from nodes.py) | ~50 |
| `src/agents/content/pipeline.py` | Modify — add seo_optimize node, settings param | +10 |
| `src/services/content.py` | Modify — use ContentDeps, store seo_result | +15 |
| `src/services/content_repositories.py` | Modify — add ContentDeps dataclass | +10 |
| `src/api/schemas/articles.py` | Modify — add SEOResultResponse, extend ArticleDraftResponse | +15 |
| Tests (5 files) | New + extend | ~300 |
| **Total** | | ~570 |

---

## 9. Out of Scope

- **CanonicalArticle assembly** — CONTENT-005
- **Citation validation / URL checking** — CONTENT-004
- **Content humanization** — CONTENT-006
- **Prompt engineering for citation-optimized headings** — deferred to CONTENT-006 (overlaps with humanization style rules)
- **`llms.txt` generation** — publishing service concern (Epic 5)
- **`robots.txt` AI crawler policies** — platform adapter concern (Epic 5)
- **Programmatic SEO verification** — The following acceptance criteria are addressed via LLM prompt instructions but NOT independently verified with code in CONTENT-003. They can be added as lightweight validation functions in a future SEO-hardening ticket:
  - Keyword density 1-2% for primary keyword (word-count ratio)
  - Readability score: Flesch-Kincaid grade 10-12 (standard formula)
  - Primary keyword in title, H1, first paragraph, meta description (string search)
  - Headings (H2, H3) contain secondary keywords (keyword intersection)
