# CONTENT-001: Article Outline Generation — Design Spec

> **Date**: 2026-03-18
> **Ticket**: CONTENT-001
> **Status**: Design approved
> **Depends on**: RESEARCH-001 (Orchestrator), RESEARCH-002 (Web Search), RESEARCH-003 (RAG Pipeline)
> **Blocks**: CONTENT-002 (Section-by-Section Drafting), CONTENT-003 (SEO), CONTENT-004 (Citations)

---

## 1. Overview

Build a content pipeline that generates structured article outlines from completed research sessions. This is the first stage of the Writer Agent — it takes research findings (topic, facets, sources, claims) and produces a 4-8 section outline with narrative flow, target word counts, and key points per section.

### Scope

**In scope:**
- `ArticleOutline` and `OutlineSection` Pydantic models
- `ArticleDraft` model for tracking outline generation state
- `generate_outline()` LLM function (Claude Sonnet, FakeLLM in tests)
- Content pipeline LangGraph StateGraph (single `generate_outline` node for CONTENT-001)
- `ContentService` with in-memory repositories
- API endpoint: `POST /api/v1/articles/generate` (triggers outline from research session)
- Comprehensive unit tests with FakeLLM

**Out of scope:**
- Section-by-section drafting with RAG (CONTENT-002)
- SEO optimization (CONTENT-003)
- Citation management (CONTENT-004)
- CanonicalArticle production (CONTENT-002+ compiles the final article)
- MilvusRetriever usage (CONTENT-002 uses RAG for drafting, not outline generation)
- Visual asset generation (Epic 4)

---

## 2. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pipeline location | Separate LangGraph graph (not in research orchestrator) | Architecture separates Research Agents from Writer Agent; content pipeline will grow (CONTENT-001 through 004) |
| RAG for outline | No — use research findings directly | Outline is about *structure*, not detailed content; RAG retrieval is CONTENT-002's job |
| Outline format | Flat section list (no nested subsections) | Matches acceptance criteria; simple for CONTENT-002 to iterate over |
| Trigger mechanism | API endpoint with session_id | Supports "reviewable before drafting" — user triggers, reviews outline, then approves for drafting |
| LLM model | Claude Sonnet (shared instance, FakeLLM in tests) | Consistent with research agents; Sonnet is sufficient for outline generation |

---

## 3. Data Models

### New file: `src/models/content_pipeline.py`

```python
from src.models.content import ContentType  # Reuse existing StrEnum

class DraftStatus(StrEnum):
    """Valid article draft statuses."""
    OUTLINE_GENERATING = "outline_generating"
    OUTLINE_COMPLETE = "outline_complete"
    DRAFTING = "drafting"           # Future: CONTENT-002
    COMPLETE = "complete"           # Future: CONTENT-002+
    FAILED = "failed"

class OutlineSection(BaseModel, frozen=True):
    """A single section in an article outline."""
    index: int
    title: str
    description: str
    key_points: list[str]
    target_word_count: int
    relevant_facets: list[int]

class ArticleOutline(BaseModel, frozen=True):
    """LLM-generated article outline from research findings."""
    title: str
    subtitle: str | None = None
    content_type: ContentType      # Reuses existing StrEnum from content.py
    sections: list[OutlineSection]
    total_target_words: int
    reasoning: str

class ArticleDraft(BaseModel):
    """Tracks article generation state."""
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    topic_id: UUID
    outline: ArticleOutline | None = None
    status: DraftStatus = DraftStatus.OUTLINE_GENERATING
    created_at: datetime
    completed_at: datetime | None = None
```

---

## 4. Content Pipeline Graph

### ContentState (TypedDict)

```python
class ContentState(TypedDict):
    topic: TopicInput
    research_plan: ResearchPlan
    findings: list[FacetFindings]
    session_id: UUID
    outline: ArticleOutline | None
    status: str        # Uses DraftStatus values
    error: str | None
```

### Graph Topology (CONTENT-001)

```
[START] → generate_outline → [END]
```

CONTENT-002 will extend this to:
```
generate_outline → draft_sections → [END]
```

### generate_outline node

1. Reads `topic`, `research_plan`, and `findings` from state
2. Calls `generate_outline()` LLM function
3. Returns `{"outline": outline, "status": "outline_complete"}`
4. On failure: returns `{"status": "failed", "error": str}`

### build_content_graph signature

```python
def build_content_graph(llm: BaseChatModel) -> CompiledStateGraph:
```

Single parameter for CONTENT-001. CONTENT-002 will add an optional `retriever: MilvusRetriever | None = None` parameter (same pattern as the research orchestrator's `indexing_deps`). The signature is designed to grow via optional keyword params without breaking existing call sites.

---

## 5. Outline Generator

### Function: `generate_outline()`

```python
async def generate_outline(
    topic: TopicInput,
    findings: list[FacetFindings],
    llm: BaseChatModel,
) -> ArticleOutline:
```

**LLM Prompt design:**

System prompt: "You are an expert content strategist. Generate a structured article outline from research findings. Respond with valid JSON only."

User template provides:
- Topic: title, description, domain
- Research facets: for each facet — title, summary, number of sources, claims
- Instructions: 4-8 sections, narrative flow (intro → findings → analysis → conclusion), 200-500 words per section, total 1500-3000 words, map each section to relevant facet indices

Expected JSON output:
```json
{
  "title": "Article Title",
  "subtitle": "Optional subtitle",
  "content_type": "article",
  "sections": [
    {
      "index": 0,
      "title": "Introduction",
      "description": "Set context and introduce the topic",
      "key_points": ["Point 1", "Point 2", "Point 3"],
      "target_word_count": 250,
      "relevant_facets": [0, 1]
    }
  ],
  "total_target_words": 2000,
  "reasoning": "Why this structure was chosen"
}
```

**Error handling:** Retry once on malformed JSON (`json.JSONDecodeError`, `ValidationError`), then raise `ValueError`.

---

## 6. Service Layer

### Findings Persistence (Prerequisite)

Research findings are currently lost after the LangGraph orchestrator completes — `ResearchService.run_and_finalize()` updates session status but does not persist `list[FacetFindings]`. CONTENT-001 needs these findings.

**Solution:** Add a `findings_data: list[dict[str, object]]` field to `ResearchSession` and update `ResearchService.run_and_finalize()` to persist the serialized findings from the orchestrator's final state. This is a small modification to existing code (not a new ticket):

```python
# In ResearchSession (research_db.py):
findings_data: list[dict[str, object]] = Field(default_factory=list)

# In ResearchService.run_and_finalize():
result = await self._orchestrator.run(session_id, topic)
findings_dicts = [f.model_dump() if hasattr(f, 'model_dump') else f for f in result.get("findings", [])]
updated = session.model_copy(update={
    "status": "complete",
    "findings_data": findings_dicts,
    ...
})
```

The `ContentService` then loads `ResearchSession.findings_data` and reconstructs `list[FacetFindings]` via `FacetFindings.model_validate()`.

### ContentService (`src/services/content.py`)

```python
@dataclass(frozen=True)
class ContentRepositories:
    drafts: ArticleDraftRepository
    research: ResearchSessionReader  # Read-only access to research sessions

class ContentService:
    def __init__(
        self, repos: ContentRepositories, llm: BaseChatModel
    ) -> None: ...

    async def generate_outline(self, session_id: UUID) -> ArticleDraft:
        session = await self._load_session(session_id)
        findings = self._reconstruct_findings(session)
        topic = self._build_topic_input(session)
        outline = await self._run_pipeline(topic, findings)
        return await self._store_draft(session, outline)

    async def get_draft(self, draft_id: UUID) -> ArticleDraft: ...

    # Private helpers (keep each under 20 lines):
    async def _load_session(self, session_id: UUID) -> ResearchSession: ...
    def _reconstruct_findings(self, session: ResearchSession) -> list[FacetFindings]: ...
    def _build_topic_input(self, session: ResearchSession) -> TopicInput: ...
    async def _run_pipeline(self, topic: TopicInput, findings: list[FacetFindings]) -> ArticleOutline: ...
    async def _store_draft(self, session: ResearchSession, outline: ArticleOutline) -> ArticleDraft: ...
```

> **Note (Issue #3 fix):** The `generate_outline` method is decomposed into 5 private helpers, each under 20 lines.

> **Note (Issue #9 fix):** `topic_id` for `ArticleDraft` comes from `ResearchSession.topic_id` — no separate topic lookup needed.

### Repository Protocols

```python
class ArticleDraftRepository(Protocol):
    async def create(self, draft: ArticleDraft) -> ArticleDraft: ...
    async def get(self, draft_id: UUID) -> ArticleDraft | None: ...

class ResearchSessionReader(Protocol):
    """Read-only access to research sessions (narrower than ResearchSessionRepository)."""
    async def get(self, session_id: UUID) -> ResearchSession | None: ...
```

> **Note (Issue #5 fix):** Named `ResearchSessionReader` (not `ResearchSessionRepository`) to avoid naming collision with the existing protocol in `src/services/research.py`. The existing `InMemoryResearchSessionRepository` satisfies both protocols.

In-memory `ArticleDraftRepository` for CONTENT-001.

### Structlog Events

The content service and pipeline emit these structured log events:
- `outline_generation_started` — `session_id`, `topic_title`
- `outline_generation_complete` — `session_id`, `draft_id`, `section_count`, `total_words`
- `outline_generation_failed` — `session_id`, `error`
- `outline_parse_failed` — `attempt`, `error` (in the LLM function, same as planner.py)

### app.state Wiring

In `create_app()` (main.py), construct and attach:
```python
content_repos = ContentRepositories(
    drafts=InMemoryArticleDraftRepository(),
    research=app.state.research_service._repos.sessions,  # Share the same in-memory store
)
app.state.content_service = ContentService(content_repos, llm)
```

> **Note (Issue #8 fix):** `ContentService` shares the same `ResearchSessionRepository` instance as `ResearchService` so both see the same in-memory data. The `llm` instance is constructed once and shared. For CONTENT-001, a `FakeLLM` or no-op LLM is used in dev (real LLM requires `ANTHROPIC_API_KEY`). The router accesses `request.app.state.content_service`.

---

## 7. API Endpoint

### Router: `src/api/routers/articles.py`

**`POST /api/v1/articles/generate`**
- Body: `{ "session_id": UUID }`
- Auth: `require_role("admin", "editor")`
- Rate limit: `3/minute`
- Behavior: calls `ContentService.generate_outline()`, returns outline
- Response (201): `ArticleOutlineResponse`

**`GET /api/v1/articles/drafts/{draft_id}`**
- Auth: `require_role("admin", "editor", "viewer")`
- Rate limit: `30/minute`
- Response (200): `ArticleDraftResponse`

### Request/Response Schemas (`src/api/schemas/articles.py`)

```python
class GenerateArticleRequest(BaseModel):
    session_id: UUID

class OutlineSectionResponse(BaseModel):
    index: int
    title: str
    description: str
    key_points: list[str]
    target_word_count: int
    relevant_facets: list[int]

class ArticleOutlineResponse(BaseModel):
    draft_id: UUID
    title: str
    subtitle: str | None
    content_type: str
    sections: list[OutlineSectionResponse]
    total_target_words: int
    reasoning: str              # LLM's explanation for the structure choice
    status: str

class ArticleDraftResponse(BaseModel):
    draft_id: UUID
    session_id: UUID
    status: str
    outline: ArticleOutlineResponse | None
    created_at: datetime
    completed_at: datetime | None
```

---

## 8. File Structure

```
src/
  agents/
    content/
      __init__.py
      outline_generator.py           # generate_outline() LLM function
      pipeline.py                    # ContentState TypedDict + build_content_graph()
  models/
    content_pipeline.py              # OutlineSection, ArticleOutline, ArticleDraft
  services/
    content.py                       # ContentService, ContentRepositories, in-memory repos
  api/
    routers/
      articles.py                    # POST /articles/generate, GET /articles/drafts/{id}
    schemas/
      articles.py                    # Request/response schemas
    main.py                          # Register articles router (modify)
tests/
  unit/
    agents/
      content/
        test_outline_generator.py
        test_pipeline.py
    services/
      test_content_service.py
    api/
      test_article_endpoints.py
    models/
      test_content_pipeline_models.py
```

### New Dependencies

None — all required packages (langgraph, langchain-core, pydantic) are already installed.

---

## 9. Testing Strategy

### `test_outline_generator.py` — FakeLLM
- Happy path: returns valid 5-section outline from findings
- Each section has title, key_points (3-5), target_word_count (200-500), relevant_facets
- Sections sum to 1500-3000 total words
- Narrative flow: first section is intro-like, last section is conclusion-like
- Handles malformed LLM JSON (retry + succeed)
- Raises ValueError on repeated failures

### `test_pipeline.py` — FakeLLM + graph
- Content graph completes with outline
- State transitions: outline_generating → outline_complete
- Graph handles generation failure (status → failed)

### `test_content_service.py` — Mocked deps
- generate_outline loads session, runs pipeline, stores draft
- Rejects invalid session_id (NotFoundError)
- Rejects incomplete research session (status != "complete")
- get_draft returns stored draft

### `test_article_endpoints.py` — API tests
- POST returns 201 with outline
- Auth: editor/admin can generate, viewer cannot
- Invalid session_id returns 404

### `test_content_pipeline_models.py` — Pydantic
- OutlineSection, ArticleOutline, ArticleDraft construction and serialization
- Frozen immutability tests
- Edge cases: empty sections list, boundary word counts

---

## 10. Acceptance Criteria Mapping

| Acceptance Criteria | How Addressed |
|---|---|
| LLM generates outline with 4-8 sections from research findings | `generate_outline()` prompts LLM with topic + findings, instructs 4-8 sections |
| Sections ordered for narrative flow (intro → findings → analysis → conclusion) | LLM prompt instructs narrative flow; test verifies first section is intro, last is conclusion |
| Each section has target word count and key points to cover | `OutlineSection` model has `target_word_count` (200-500) and `key_points: list[str]` |
| Outline reviewable before drafting proceeds | API returns outline immediately; drafting (CONTENT-002) is a separate future action |
