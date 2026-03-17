# RESEARCH-002: Web Search Agent — Design Spec

> **Date**: 2026-03-17
> **Ticket**: RESEARCH-002
> **Status**: Design approved
> **Depends on**: RESEARCH-001 (Agent Orchestrator — merged, PR #15)
> **Blocks**: RESEARCH-005 (Research Session Tracking)

---

## 1. Overview

Build a web search agent that replaces the stub research agent from RESEARCH-001. The agent executes search queries from a research facet via SerpAPI, deduplicates results, and extracts structured claims via LLM. It satisfies the existing `AgentFunction` signature as a callable class.

### Scope

**In scope:**
- `SerpAPIClient` transport layer (httpx-based, follows existing client patterns)
- `WebSearchAgent` callable class implementing `AgentFunction` signature
- SerpAPI snippet-based source documents (no full page fetching)
- LLM-based claims extraction (Claude Sonnet, shared LLM instance)
- URL-based deduplication across multiple queries per facet
- Graceful error handling (partial failures, LLM fallback)
- Configuration via pydantic-settings
- Comprehensive unit tests with mocked httpx and FakeLLM

**Out of scope:**
- Full page content fetching/scraping (deferred to RESEARCH-003 or future ticket)
- Semantic deduplication (orchestrator/evaluator concern)
- Milvus vector storage of findings (RESEARCH-003)
- Celery task dispatch (future infra ticket)

### Stubs Replaced

| Stub | Location | Replaced by |
|------|----------|-------------|
| `stub_research_agent` | `src/agents/research/stub.py` | `WebSearchAgent` in `src/agents/research/web_search.py` |

Note: `stub.py` is kept — it's still used in unit tests for the orchestrator and integration tests.

---

## 2. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Search API | SerpAPI via httpx | Matches architecture docs; structured JSON, no HTML parsing; consistent with existing client patterns |
| Content depth | SerpAPI snippets only | Sufficient for completeness evaluation; full fetch deferred to RESEARCH-003 |
| Claims extraction | LLM-based (Claude Sonnet) | Evaluator judges claims quality; LLM produces structured claims; one extra Sonnet call per facet |
| Results per query | 10 per query, deduplicate by URL | Matches acceptance criteria; 1-3 queries per facet = up to 30 raw, deduped to ~10-15 unique |
| Agent pattern | Callable class with `__call__` | Satisfies `AgentFunction` type alias; closure over SerpAPIClient + LLM dependencies |

---

## 3. Agent Architecture

### WebSearchAgent

A callable class that satisfies `AgentFunction = Callable[[ResearchFacet], Awaitable[FacetFindings]]`:

```python
class WebSearchAgent:
    def __init__(self, serpapi_client: SerpAPIClient, llm: BaseChatModel) -> None:
        self._client = serpapi_client
        self._llm = llm

    async def __call__(self, facet: ResearchFacet) -> FacetFindings:
        # 1. Execute all search queries in parallel
        # 2. Deduplicate results by URL
        # 3. Convert to SourceDocument list
        # 4. Extract claims + summary via LLM
        # 5. Return FacetFindings
```

### Wiring to Orchestrator

Minimal change — only the agent function passed to `build_graph` changes:

```python
# Construction
serpapi_client = SerpAPIClient(api_key=settings.serpapi_api_key)
agent = WebSearchAgent(serpapi_client, llm)
graph = build_graph(llm, dispatcher, agent)  # agent satisfies AgentFunction
```

The orchestrator, dispatcher, evaluator, planner, and all other components are unchanged.

---

## 4. Data Flow

Within a single `__call__` invocation for one facet:

```
ResearchFacet.search_queries (1-3 queries)
    ↓
[parallel] SerpAPIClient.search(query, num=10) per query
    ↓
Raw results: up to 30 SerpAPIResult objects
    ↓
Deduplicate by URL (keep first occurrence)
    ↓
Convert to list[SourceDocument] (url, title, snippet, retrieved_at)
    ↓
LLM call: extract claims + summary from combined snippets
    Input: facet title + all snippets
    Output: {"claims": ["...", ...], "summary": "..."}
    ↓
FacetFindings(facet_index, sources, claims, summary)
```

### Deduplication

URL-based: normalize URLs (strip trailing slash, lowercase), use a set to track seen URLs. Keep first occurrence across all queries.

### LLM Claims Extraction

Single LLM call per facet returning both claims and summary:

```python
# Prompt template
"Given these search results about '{facet_title}':\n\n{snippets}\n\n"
"Extract 3-5 key factual claims and a 2-3 sentence summary.\n"
"Return JSON: {\"claims\": [\"...\"], \"summary\": \"...\"}"
```

**Fallback on LLM failure:** If the LLM call fails (timeout, malformed JSON, ValidationError), fall back to:
- `claims`: first 3 unique snippets (truncated to 200 chars each)
- `summary`: `f"Search results for: {facet.title}"`

---

## 5. SerpAPIClient (Transport Layer)

Follows the existing client pattern (`hackernews_client.py`, `newsapi_client.py`):

```python
class SerpAPIError(Exception):
    """Raised when SerpAPI returns an error or is unreachable."""
    def __init__(self, message: str, status_code: int | None = None) -> None: ...

class SerpAPIResult(BaseModel, frozen=True):
    """Typed search result from SerpAPI organic results."""
    title: str
    link: str
    snippet: str
    position: int

class SerpAPIClient:
    def __init__(self, api_key: str, base_url: str, timeout: float) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    async def search(self, query: str, num_results: int = 10) -> list[SerpAPIResult]:
        """Execute a search query and return parsed organic results."""
        # GET {base_url}?q={query}&num={num_results}&api_key={key}&engine=google
        # Parse response["organic_results"] → list[SerpAPIResult]
        # Raise SerpAPIError on non-200 or missing results
```

- Uses `httpx.AsyncClient` with configurable timeout
- Parses `organic_results` array from SerpAPI JSON response
- Each organic result has: `title`, `link`, `snippet`, `position`
- Missing/empty `snippet` → skip that result
- Non-200 response → raise `SerpAPIError`

---

## 6. Error Handling

The agent is designed to degrade gracefully rather than fail:

| Failure | Behavior |
|---------|----------|
| SerpAPI timeout/error on one query | Skip that query, use results from other queries |
| All queries fail | Return empty `FacetFindings(sources=[], claims=[], summary="")` |
| LLM claims extraction fails | Fallback to snippet-based claims |
| Single result missing snippet | Skip that result |
| No results after dedup | Return empty `FacetFindings` |

The agent never raises exceptions. The `AsyncIODispatcher` already wraps agents in try/except, but the agent handles its own errors internally for better logging and fallback behavior.

---

## 7. Configuration

Added to `src/config/settings.py`:

```python
# SerpAPI
serpapi_api_key: str = ""
serpapi_base_url: str = "https://serpapi.com/search"
serpapi_timeout: float = 10.0
serpapi_results_per_query: int = 10
```

All configurable via `COGNIFY_SERPAPI_*` environment variables.

---

## 8. File Structure

```
src/
  services/
    serpapi_client.py                  # NEW: SerpAPIClient + SerpAPIError + SerpAPIResult
  agents/
    research/
      web_search.py                    # NEW: WebSearchAgent callable class
      stub.py                          # KEPT: still used in orchestrator/integration tests
  config/
    settings.py                        # MODIFY: add serpapi_* settings
tests/
  unit/
    services/
      test_serpapi_client.py           # NEW: client tests with mocked httpx
    agents/
      research/
        test_web_search.py             # NEW: agent tests with mocked client + FakeLLM
```

### New Dependencies

None — `httpx` is already installed. SerpAPI is called via REST, no SDK needed.

### Mypy Overrides

None needed — all new code uses typed Pydantic models and Protocol-compatible patterns.

---

## 9. Testing Strategy

### Unit Tests (mocked httpx, FakeLLM)

**`test_serpapi_client.py`** — Mocked httpx responses:
- Happy path: returns parsed `SerpAPIResult` list from organic_results
- Empty results: query returns no organic_results → empty list
- API error: non-200 status → raises `SerpAPIError`
- Timeout: httpx timeout → raises `SerpAPIError`
- Missing snippet: results with no snippet field → skipped

**`test_web_search.py`** — Mocked `SerpAPIClient` + `FakeLLM`:
- Happy path: 1 query, 3 results → `FacetFindings` with sources + LLM claims
- Multiple queries: 3 queries with overlapping URLs → deduplicates correctly
- Partial query failure: 1 query raises `SerpAPIError`, others succeed → partial results
- All queries fail: returns empty `FacetFindings`
- LLM claims extraction: FakeLLM returns structured JSON → parsed into claims + summary
- LLM fallback: FakeLLM returns malformed JSON → falls back to snippet-based claims
- Callable interface: `isinstance(agent, AgentFunction)` pattern — verify `__call__` works with dispatcher

---

## 10. Acceptance Criteria Mapping

| Acceptance Criteria | How Addressed |
|---|---|
| Executes search queries derived from research plan | `WebSearchAgent.__call__` iterates `facet.search_queries`, calls `SerpAPIClient.search()` per query in parallel |
| Fetches and cleans top 10 results per query | `SerpAPIClient.search(query, num_results=10)` returns typed `SerpAPIResult` with clean title/snippet/link |
| Extracts relevant content, discards boilerplate | SerpAPI returns pre-extracted snippets (Google's own extraction); no HTML boilerplate. Full page fetch deferred. |
| Stores findings with source URL and date | Each result → `SourceDocument(url, title, snippet, retrieved_at=now)` returned in `FacetFindings.sources` |
