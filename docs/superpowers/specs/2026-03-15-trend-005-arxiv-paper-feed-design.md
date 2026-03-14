# TREND-005: arXiv Paper Feed — Design Spec

## Overview

Add arXiv as the fifth trend source for Cognify. Monitors arXiv's public API for recent papers in configured categories, extracts metadata (title, abstract, authors, categories), scores by recency and citation potential, and surfaces domain-relevant papers as `RawTopic` items through a REST endpoint.

Follows the established 3-tier trend source pattern: Client → Service → API endpoint.

## arXiv API

- **Base URL**: `https://export.arxiv.org/api/query`
- **Protocol**: HTTPS GET returning Atom XML
- **Auth**: None (public API)
- **Rate limit**: 1 request per 3 seconds (polite use)
- **Query params**:
  - `search_query`: arXiv query syntax (e.g., `cat:cs.CR` for cryptography/security, `cat:cs.AI` for AI)
  - `start`: pagination offset (default 0)
  - `max_results`: number of entries (max 100)
  - `sortBy`: `submittedDate`, `lastUpdatedDate`, or `relevance`
  - `sortOrder`: `descending` (most recent first)

### Response Structure (Atom XML)

Each `<entry>` contains:
- `<title>`: paper title (may contain newlines — normalize)
- `<summary>`: abstract text
- `<author><name>`: one or more authors
- `<published>`: ISO 8601 datetime (e.g., `2026-03-15T12:00:00Z`)
- `<updated>`: last revision datetime
- `<id>`: arXiv URL (e.g., `http://arxiv.org/abs/2603.12345v1`)
- `<link rel="alternate" href="...">`: abstract page URL
- `<link rel="related" title="pdf" href="...">`: PDF URL
- `<arxiv:primary_category term="cs.CR">`: primary category
- `<category term="cs.CR">`: all categories (multiple elements)

## Data Model

### ArxivPaper (TypedDict)

```python
class ArxivPaper(TypedDict):
    arxiv_id: str           # e.g., "2603.12345v1"
    title: str              # whitespace-normalized
    abstract: str           # full abstract text
    authors: list[str]      # author name strings
    published: str          # ISO 8601 datetime string
    updated: str            # ISO 8601 datetime string
    pdf_url: str            # direct PDF link
    abs_url: str            # abstract page URL
    primary_category: str   # e.g., "cs.CR"
    categories: list[str]   # all category tags
```

## Client Layer (`src/services/arxiv_client.py`)

- `ArxivAPIError(Exception)` — raised on HTTP/parse failures
- `ArxivClient.__init__(base_url, timeout)` — no API key needed
- `ArxivClient.fetch_papers(categories, max_results, sort_by)` → `list[ArxivPaper]`
  - Builds query: `cat:{cat1} OR cat:{cat2}` for multiple categories
  - Sorts by `submittedDate` descending
  - Parses Atom XML via `xml.etree.ElementTree`
  - Normalizes title whitespace (arXiv titles contain `\n`)
  - Extracts PDF URL from `<link>` elements
  - Raises `ArxivAPIError` on timeout, connection error, HTTP error, or XML parse error

## Service Layer (`src/services/arxiv.py`)

### Scoring: Recency + Citation Potential

**Score formula** (0–100):
```
score = recency_score * 0.6 + citation_potential * 0.4
```

- **Recency score** (0–100): Exponential decay with 7-day half-life
  - `recency = exp(-λ * days_ago) * 100` where `λ = ln(2) / 7`
  - A paper published today scores ~100; 7 days ago ~50; 14 days ~25

- **Citation potential** (0–100): Heuristic based on:
  - `num_categories * 15` (broader interest = more citations), capped at 60
  - `min(40, len(abstract) / 25)` (longer abstract = more thorough work)

### Velocity

`velocity = 1.0 / max(1.0, days_ago)` — same inverse-time approach as other sources.

### Domain Filtering

`filter_by_domain(papers, domain_keywords)` — case-insensitive search across title, abstract, categories, and author names. Returns `list[tuple[ArxivPaper, list[str]]]`.

### Deduplication

Single-pass: exact `arxiv_id` dedup (keep highest score). No fuzzy title pass needed — arXiv IDs are unique.

### fetch_and_normalize

Orchestrates: fetch → filter → score → map to `RawTopic` → dedup → return `ArxivFetchResponse`.

`RawTopic.source = "arxiv"`, `external_url` = abstract page URL, description = truncated abstract (200 chars).

## Schema Layer (`src/api/schemas/trends.py`)

```python
class ArxivFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    categories: list[str] = Field(default=["cs.CR", "cs.AI", "cs.LG"])
    max_results: int = Field(default=30, ge=1, le=100)

class ArxivFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_filter: int
```

## API Endpoint

- **Route**: `POST /api/v1/trends/arxiv/fetch`
- **Auth**: `require_role("admin", "editor")`
- **Rate limit**: 5/minute
- **Dependency**: `_get_arxiv_service(request)` with test injection via `app.state.arxiv_client`
- **Error handling**: `ArxivAPIError` → 503 `ServiceUnavailableError(code="arxiv_unavailable")`

## Settings (`src/config/settings.py`)

```python
arxiv_api_base_url: str = "https://export.arxiv.org/api/query"
arxiv_request_timeout: float = 15.0
arxiv_default_categories: list[str] = ["cs.CR", "cs.AI", "cs.LG"]
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `src/services/arxiv_client.py` |
| Create | `src/services/arxiv.py` |
| Create | `tests/unit/services/test_arxiv_client.py` |
| Create | `tests/unit/services/test_arxiv.py` |
| Create | `tests/unit/api/test_arxiv_endpoints.py` |
| Modify | `src/config/settings.py` — add arxiv settings |
| Modify | `src/api/schemas/trends.py` — add ArxivFetchRequest/Response |
| Modify | `src/api/routers/trends.py` — add arxiv endpoint |
| Modify | `tests/unit/services/conftest.py` — add MockArxivClient |
