# RESEARCH-004: Literature Review Agent — Design Spec

## 1. Overview

The Literature Review Agent adds academic paper search to Cognify's multi-agent research pipeline. It searches Semantic Scholar's API (which indexes arXiv, PubMed, ACL, IEEE, and 200M+ papers), extracts abstracts and key findings, and returns structured findings that flow into the existing RAG pipeline.

**Backlog acceptance criteria:**
- Searches arXiv API by topic keywords
- Extracts abstracts and key findings
- Summarizes relevant papers with citations

**Scope:** Semantic Scholar search only (search endpoint returns all needed fields). No recommendation engine, no citation graph traversal (future enhancement).

**Acceptance criteria note:** The backlog states "Searches arXiv API by topic keywords." This is satisfied transitively via Semantic Scholar, which indexes all arXiv papers plus 200M+ additional papers. A separate ArxivClient call would produce duplicates. The existing ArxivClient remains in TREND-005 trend discovery.

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Academic source | Semantic Scholar API only | Indexes arXiv + 200M papers; separate ArxivClient call would produce duplicates. ArxivClient stays in TREND-005 trend discovery. Backlog criterion "Searches arXiv API" is satisfied transitively. |
| Orchestrator integration | Planner tags facets with `source_type`; dispatcher routes to correct agent | Efficient — avoids wasting API calls on academic searches for news-type facets. No graph structure changes needed. |
| Semantic Scholar API scope | Search only (no separate details call) | The search endpoint with `fields=` parameter returns all needed fields (abstract, authors, year, citationCount, venue). A separate `get_paper_details()` call is unnecessary and would waste rate limit budget. |
| Results per query | Configurable, default 5 | Papers are information-dense; fewer results yield comparable depth to web search's 10. Constructor parameter for flexibility. |
| `citation_count` handling | Intentionally dropped in SourceDocument mapping | `SourceDocument` is a shared contract across agents; `citation_count` is academic-specific. Could be logged or added to snippet metadata in future. |

## 3. Agent Architecture

### 3.1 LiteratureReviewAgent

Follows the same `AgentFunction` protocol as `WebSearchAgent`:

```python
class LiteratureReviewAgent:
    def __init__(
        self,
        client: SemanticScholarClient,
        llm: BaseChatModel,
        max_results_per_query: int = 5,
    ) -> None: ...

    async def __call__(self, facet: ResearchFacet) -> FacetFindings: ...
```

**Internal flow per facet:**

1. Execute all `facet.search_queries` against Semantic Scholar search endpoint in parallel via `asyncio.gather()`
2. Deduplicate by `paper_id`
3. Filter out papers with no abstract (unusable for extraction)
4. Sanitize abstracts and titles (strip control characters — RISK-005 prompt injection mitigation, same as `WebSearchAgent._sanitize()`)
5. Convert to `SourceDocument` list
6. LLM extraction: claims + summary from abstracts (single call per facet)
7. Return `FacetFindings(facet_index, sources, claims, summary)`

**Graceful degradation:**

| Failure | Behavior |
|---------|----------|
| Semantic Scholar API timeout | Skip that query, use results from others |
| All queries fail | Return empty `FacetFindings(sources=[], claims=[], summary="")` |
| LLM extraction fails | Fallback to abstract-based claims (first sentence of each abstract) |
| Paper has no abstract | Skip that paper |
| Dedup yields nothing | Return empty findings |

### 3.2 SemanticScholarClient

Transport-layer client, same pattern as `SerpAPIClient`:

```python
class SemanticScholarClient:
    def __init__(
        self,
        base_url: str = "https://api.semanticscholar.org",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None: ...

    async def search(
        self, query: str, max_results: int = 5,
    ) -> list[ScholarPaper]: ...
```

**API details:**
- Free tier: 100 requests per 5 minutes (no key required)
- Authenticated tier: 1 request/second (optional API key for higher rate limits)
- Search endpoint: `GET /graph/v1/paper/search?query=...&fields=paperId,title,abstract,authors,year,citationCount,venue,externalIds,url&limit=N`
- No separate details call needed — search endpoint with `fields=` returns all required data
- Rate limiting: `asyncio.Semaphore` with configurable concurrency (default 3 concurrent requests) + per-request sleep for authenticated tier
- `base_url` is configurable for testability (consistent with `serpapi_base_url`, `newsapi_base_url`, etc.)
- Error handling: raises `SemanticScholarError` on API failures (consistent with `SerpAPIClient` raising `SerpAPIError`). The agent's `_safe_search()` wrapper catches and returns empty results — same pattern as `WebSearchAgent._safe_search()`

### 3.3 ScholarPaper Model

```python
class ScholarPaper(BaseModel, frozen=True):
    paper_id: str
    title: str
    abstract: str | None
    authors: list[str]
    year: int | None
    citation_count: int
    venue: str | None
    url: str
    doi: str | None
```

## 4. Orchestrator Integration

### 4.1 ResearchFacet Extension

Add `source_type` field with backward-compatible default:

```python
class ResearchFacet(BaseModel, frozen=True):
    index: int
    title: str
    description: str
    search_queries: list[str]
    source_type: Literal["web", "academic", "both"] = "web"
```

Uses `Literal` for compile-time type safety — mypy strict mode catches invalid values.

### 4.2 Research Planner Prompt Update

The `generate_research_plan()` prompt gets an addition instructing the LLM to tag each facet:

- `"academic"` — research findings, methodologies, theoretical foundations, empirical studies
- `"web"` — current events, industry news, practical guides, tutorials, opinions
- `"both"` — facets that benefit from both web and scholarly perspectives

Default fallback: if the LLM omits `source_type`, default to `"web"` (backward compatible).

**Example planner output with `source_type`:**

```json
{
  "facets": [
    {
      "index": 0,
      "title": "Recent zero-day exploits in 2026",
      "description": "Current incidents and vendor responses",
      "search_queries": ["zero-day exploits 2026", "CVE critical 2026"],
      "source_type": "web"
    },
    {
      "index": 1,
      "title": "Academic research on zero-day detection methods",
      "description": "ML-based detection techniques and formal verification approaches",
      "search_queries": ["zero-day detection machine learning", "vulnerability discovery formal methods"],
      "source_type": "academic"
    },
    {
      "index": 2,
      "title": "Industry best practices for zero-day mitigation",
      "description": "Both vendor recommendations and research-backed strategies",
      "search_queries": ["zero-day mitigation strategies", "vulnerability response framework"],
      "source_type": "both"
    }
  ]
}
```

### 4.3 Dispatcher Routing

The `dispatch_agents` node splits facets by `source_type` and calls the dispatcher separately for each group, preserving the existing `TaskDispatcher` protocol (which takes a single `agent_fn`):

```python
# Split facets by source_type
web_facets = [f for f in facets if f.source_type in ("web", "both")]
academic_facets = [f for f in facets if f.source_type in ("academic", "both")]

# Dispatch each group through the existing dispatcher protocol
results: list[FacetFindings] = []
if web_facets:
    results.extend(await dispatcher.dispatch(web_facets, web_agent_fn))
if academic_facets and literature_agent_fn is not None:
    results.extend(await dispatcher.dispatch(academic_facets, literature_agent_fn))
elif academic_facets:
    # Fallback: no literature agent configured, route to web
    results.extend(await dispatcher.dispatch(academic_facets, web_agent_fn))
```

This preserves the `TaskDispatcher.dispatch(facets, agent_fn)` contract, keeping the abstraction intact for future Celery migration. When `source_type == "both"`, the facet appears in both groups and both agents process it independently. Results from both are appended to `findings` (additive reducer handles this).

**Note on duplicate `facet_index`:** When `source_type == "both"`, two `FacetFindings` entries will share the same `facet_index`. The evaluator's `_summarize_findings()` and the content generation pipeline handle this correctly — they iterate the findings list without assuming unique facet indices. The additive reducer simply concatenates all results.

**Evaluator edge case:** The evaluator's `_apply_guardrails()` checks for zero-source facets via `[f.facet_index for f in findings if len(f.sources) == 0]`. When `source_type == "both"`, if one agent returns results but the other returns zero sources for the same facet, this would flag the facet as weak and potentially trigger an unnecessary retry round. This is acceptable — the retry is bounded (max 2 rounds) and the system converges. No evaluator changes needed for this ticket.

### 4.4 build_graph Signature Update

```python
def build_graph(
    llm: BaseChatModel,
    dispatcher: AsyncIODispatcher,
    agent_fn: AgentFunction,  # Existing param name preserved
    literature_agent_fn: AgentFunction | None = None,  # NEW, optional
    indexing_deps: IndexingDeps | None = None,
) -> CompiledGraph:
```

Parameter name `agent_fn` is preserved (not renamed to `web_agent_fn`) to maintain backward compatibility with all existing callers. If `literature_agent_fn` is `None`, all facets route to `agent_fn` regardless of `source_type`. This preserves backward compatibility with existing tests and deployments without the Semantic Scholar client configured.

## 5. Data Flow & Mapping

### 5.1 ScholarPaper to SourceDocument

| ScholarPaper field | SourceDocument field | Transform |
|---|---|---|
| `url` (fallback: DOI URL) | `url` | Use `url`; if empty, construct `https://doi.org/{doi}` |
| `title` | `title` | Direct |
| `abstract` (truncated 500 chars) | `snippet` | Truncate at word boundary |
| — | `retrieved_at` | `datetime.now(UTC)` |
| `year` | `published_at` | `datetime(year, 1, 1, tzinfo=UTC)` if year present, else `None` |
| First author | `author` | `authors[0]` if non-empty, else `None` |

### 5.2 Downstream Pipeline Compatibility

Findings flow through the existing pipeline unchanged:
- **Milvus indexing:** `index_findings` node chunks snippets (abstracts) and indexes them with metadata
- **RAG retrieval:** Content generation retrieves academic chunks alongside web chunks via `MilvusRetriever`
- **Citation management:** `SourceDocument.url` carries the paper URL; CONTENT-004 citation pipeline produces proper references

### 5.3 Deduplication

Within the agent: by `paper_id` (Semantic Scholar's canonical ID). Cross-agent deduplication (web search may find the same paper) is handled at the evaluator/content generation layer via URL comparison — consistent with existing architecture.

### 5.4 LLM Extraction Prompt

Similar to web search but tuned for academic content:
- Focus on methodology, key findings, and statistical results
- Extract claims that are citable with author/year (e.g., "Smith et al. (2025) found that...")
- Summary emphasizes research contributions and implications

## 6. File Structure

### New Files

| File | Purpose | ~Lines |
|---|---|---|
| `src/services/semantic_scholar.py` | `SemanticScholarClient` + `ScholarPaper` model | ~90 |
| `src/agents/research/literature_review.py` | `LiteratureReviewAgent` | ~100 |
| `tests/unit/services/test_semantic_scholar.py` | Client unit tests | ~80 |
| `tests/unit/agents/research/test_literature_review.py` | Agent unit tests | ~100 |

### Modified Files

| File | Change |
|---|---|
| `src/models/research.py` | Add `source_type: Literal["web", "academic", "both"] = "web"` to `ResearchFacet` |
| `src/agents/research/orchestrator.py` | Update `dispatch_agents` to route by `source_type`; `build_graph` takes optional `literature_agent_fn` |
| `src/agents/research/planner.py` | Update prompt to emit `source_type` per facet |
| `tests/unit/agents/research/test_orchestrator.py` | Tests for dual-agent routing, backward compat |
| `tests/unit/agents/research/test_planner.py` | Tests for `source_type` in plan output |

## 7. Testing Strategy

### SemanticScholarClient (unit)
- Mock `httpx` responses for search endpoint
- Test successful search returns typed `ScholarPaper` list
- Test empty results return empty list
- Test API error (500, timeout) returns empty list with structlog warning
- Test rate limiting (semaphore concurrency)
- Test papers with missing fields (no abstract, no DOI)
- Test configurable `base_url` for testability

### LiteratureReviewAgent (unit)
- Mock `SemanticScholarClient` + `FakeLLM`
- Happy path: queries return papers, LLM extracts claims/summary
- Empty results: all queries return no papers, returns empty `FacetFindings`
- LLM failure: extraction fails, fallback to abstract-based claims
- Deduplication: same paper from multiple queries appears once
- No-abstract filtering: papers without abstracts are skipped
- Sanitization: control characters in abstracts/titles are stripped

### Orchestrator Routing (unit)
- Mock both agents, verify `source_type="web"` calls web agent only
- Verify `source_type="academic"` calls literature agent only
- Verify `source_type="both"` calls both agents for same facet
- Verify `literature_agent_fn=None` routes all to web agent (backward compat)
- Verify findings from both agents are merged via additive reducer

### Planner (unit)
- Verify LLM output includes `source_type` field
- Verify default fallback to `"web"` when field missing
- Verify mixed facets (some web, some academic) in single plan

## 8. Configuration

```python
# In pydantic-settings config
semantic_scholar_base_url: str = "https://api.semanticscholar.org"  # Configurable for testing
semantic_scholar_api_key: str | None = None  # Optional, for higher rate limits
semantic_scholar_timeout: float = 30.0
literature_review_max_results: int = 5  # Per query
```

No API key is required for basic usage. Key is optional for production deployments needing higher throughput. `base_url` follows the pattern of other external API clients (`serpapi_base_url`, `newsapi_base_url`, etc.) for testability.
