# Design Spec: TREND-004 — NewsAPI Integration

## Overview

Integrate NewsAPI Top Headlines as a trend source for Cognify's trend discovery engine. Follows the established client/service/router pattern used by Google Trends, Reddit, and Hacker News integrations.

## Decisions

- **Endpoint used**: Top Headlines only (`/v2/top-headlines`). The Everything endpoint is out of scope — it's better suited for research (RESEARCH-002) than trend discovery.
- **Scoring**: Hybrid formula combining position rank, recency, and keyword match count. NewsAPI articles lack engagement metrics (no likes/comments), so position and freshness are the primary signals.
- **Deduplication**: Two-pass — exact by URL, then fuzzy title matching (`SequenceMatcher` ratio > 0.85) to catch syndicated articles covering the same story from different outlets. Mirrors the Reddit dedup approach.
- **Request parameters**: Expose `category` and `country` per-request with defaults from settings. `language` and `sources` omitted to keep scope small (3 SP).

## Component Design

### 1. Client Layer — `src/services/newsapi_client.py`

**`NewsAPIArticle`** (TypedDict):
- `title: str`
- `description: str | None`
- `url: str`
- `urlToImage: str | None`
- `publishedAt: str` (ISO 8601)
- `source: dict` (keys: `id`, `name`)
- `author: str | None`
- `content: str | None` (truncated to 200 chars by NewsAPI free tier; used for domain keyword matching when title/description are short)

**`NewsAPIError`** (Exception):
- Wraps all HTTP, connection, timeout, and API-level errors.
- Constructor: `__init__(self, message: str)`.

**`NewsAPIClient`**:
- Constructor: `__init__(self, api_key: str, base_url: str, timeout: float)`.
- Method: `async fetch_top_headlines(category: str, country: str, page_size: int) -> list[NewsAPIArticle]`.
- Uses `httpx.AsyncClient` (short-lived, created per call).
- Filters out articles with `title == "[Removed]"` before returning.
- Error mapping:
  - `httpx.TimeoutException` → `NewsAPIError("NewsAPI timed out: ...")`
  - `httpx.ConnectError` → `NewsAPIError("NewsAPI connection failed: ...")`
  - Non-2xx HTTP → `NewsAPIError(f"NewsAPI returned {status_code}: ...")`
  - API response `status != "ok"` → `NewsAPIError(f"NewsAPI error: {code}")`

### 2. Service Layer — `src/services/newsapi.py`

**`NewsAPIService`**:
- Constructor: `__init__(self, client: NewsAPIClient)`.
- Main method: `async fetch_and_normalize(domain_keywords: list[str], category: str, country: str, max_results: int) -> NewsAPIFetchResponse`.
- Note: Unlike Reddit/HN, no `score_cap` needed — the hybrid formula self-normalizes via bounded position, recency, and keyword components.

**Pipeline**:
1. Fetch via `client.fetch_top_headlines(category, country, page_size=max_results)`.
2. `filter_by_domain(articles, domain_keywords)` — match keywords against title + description + source name + content (case-insensitive). Returns `list[tuple[NewsAPIArticle, list[str]]]`.
3. `calculate_score(index, total, published_at, matched_keywords)` — hybrid scoring.
4. `calculate_velocity(published_at)` — recency-based.
5. `map_to_raw_topic(article, score, velocity, matched_keywords)` — map to `RawTopic`.
6. `_deduplicate(topics)` — two-pass: exact by URL, then fuzzy title matching (SequenceMatcher ratio > 0.85). Keep higher score.

**Scoring formula** (`@staticmethod`, uses `math.exp` and `math.log`):
```python
position_score = max(0, 100 - (index * (100 / total)))
recency_bonus = math.exp(-math.log(2) / 6 * hours)  # 6-hour half-life
keyword_bonus = min(20, len(matched_keywords) * 5)
trend_score = min(100, position_score * 0.5 + recency_bonus * 30 + keyword_bonus)
```

**Worked examples**:
- **Position 0/20, 1h old, 2 keywords**: `position=100, recency=0.891, keyword=10` → `min(100, 50 + 26.7 + 10)` = **86.7**
- **Position 10/20, 12h old, 1 keyword**: `position=50, recency=0.25, keyword=5` → `min(100, 25 + 7.5 + 5)` = **37.5**
- **Position 19/20, 48h old, 1 keyword**: `position=5, recency=0.003, keyword=5` → `min(100, 2.5 + 0.1 + 5)` = **7.6**

**Velocity formula** (`@staticmethod`):
```python
velocity = 1.0 / max(1.0, hours_since_published)
```

**RawTopic mapping** (`@staticmethod`):
- `title` = article title
- `description` = article description truncated to 200 chars (or `""` if None)
- `source` = `"newsapi"`
- `external_url` = article URL
- `trend_score` = calculated score
- `velocity` = calculated velocity
- `discovered_at` = `datetime.now(UTC)`
- `domain_keywords` = matched keywords

**Deduplication**: Two-pass — (1) exact by URL, keep highest score; (2) fuzzy title matching via `difflib.SequenceMatcher` with ratio > 0.85, keep highest score. Handles syndicated articles from different outlets.

**Structured logging**:
- `newsapi_fetch_started` (INFO) — domain_keywords, category, country, max_results
- `newsapi_fetch_completed` (INFO) — total_fetched, total_after_filter, total_after_dedup, duration_ms
- `newsapi_items_filtered` (DEBUG) — before_count, after_count, domain_keywords
- `newsapi_api_error` (ERROR) — error message, category, country

### 3. API Layer

**Schemas** (extend `src/api/schemas/trends.py`):

`NewsAPIFetchRequest`:
- `domain_keywords: list[str]` — min_length=1, required
- `max_results: int` — ge=1, le=100, default=30
- `category: str` — default=`"technology"`
- `country: str` — default=`"us"`

`NewsAPIFetchResponse`:
- `topics: list[RawTopic]`
- `total_fetched: int`
- `total_after_filter: int`

**Endpoint** (extend `src/api/routers/trends.py`):
- `POST /api/v1/trends/newsapi/fetch`
- Auth: `require_role("admin", "editor")`
- Rate limit: `5/minute`
- Catch `NewsAPIError` → raise `ServiceUnavailableError(code="newsapi_unavailable", message="NewsAPI is not available")`.

**Dependency injection** — `_get_newsapi_service(request)` helper function:
```python
def _get_newsapi_service(request: Request) -> NewsAPIService:
    settings = request.app.state.settings
    if hasattr(request.app.state, "newsapi_client"):
        client = request.app.state.newsapi_client
    else:
        client = NewsAPIClient(
            api_key=settings.newsapi_api_key,
            base_url=settings.newsapi_base_url,
            timeout=settings.newsapi_request_timeout,
        )
    return NewsAPIService(client=client)
```

Mirrors `_get_hn_service()` and `_get_reddit_service()` in the same file.

**Settings** (extend `src/config/settings.py`):
- `newsapi_api_key: str = ""`
- `newsapi_base_url: str = "https://newsapi.org/v2"`
- `newsapi_request_timeout: float = 10.0`
- `newsapi_default_category: str = "technology"`
- `newsapi_default_country: str = "us"`

### 4. Error Handling

Same pattern as all other trend sources:

| Error | Client behavior | Router behavior |
|-------|----------------|-----------------|
| HTTP timeout | Raise `NewsAPIError` | → 503 |
| Connection failure | Raise `NewsAPIError` | → 503 |
| Non-2xx response | Raise `NewsAPIError` | → 503 |
| API error (status != "ok") | Raise `NewsAPIError` | → 503 |

### 5. Tests

**`MockNewsAPIClient`** in `tests/unit/services/conftest.py`:
- Subclass of `NewsAPIClient`, returns canned `list[NewsAPIArticle]`.

**`tests/unit/services/test_newsapi_client.py`** (~6 tests):
- Successful fetch returns parsed articles
- Empty results → empty list
- API error response → `NewsAPIError`
- HTTP timeout → `NewsAPIError`
- Non-2xx status → `NewsAPIError`
- `[Removed]` articles filtered out

**`tests/unit/services/test_newsapi.py`** (~25 tests):
- `calculate_score`: parametrized — first/last position, fresh/old article, multiple keywords
- `calculate_velocity`: fresh vs old, zero-hours edge case
- `filter_by_domain`: match, no match, case-insensitive, multi-keyword
- `map_to_raw_topic`: all fields, `source="newsapi"`, None description → `""`
- `_deduplicate`: duplicate URLs keep higher score, fuzzy title match deduplicates syndicated articles
- `fetch_and_normalize`: full pipeline, empty input, max_results capping

**`tests/unit/api/test_newsapi_schemas.py`** (~6 tests):
- Valid request passes
- Missing domain_keywords → 422
- max_results out of range → 422
- Defaults applied for category and country

**`tests/unit/api/test_newsapi_endpoints.py`** (~7 tests):
- No auth → 401
- Viewer role → 403
- Admin/editor → 200
- Invalid body → 422
- API unavailable → 503
- Successful response shape
- No matches → empty topics

## File Inventory

**New files**:
- `src/services/newsapi_client.py` — HTTP client
- `src/services/newsapi.py` — business logic
- `tests/unit/services/test_newsapi_client.py` — client tests
- `tests/unit/services/test_newsapi.py` — service tests
- `tests/unit/api/test_newsapi_schemas.py` — schema validation tests
- `tests/unit/api/test_newsapi_endpoints.py` — endpoint tests

**Modified files**:
- `src/config/settings.py` — add NewsAPI settings
- `src/api/schemas/trends.py` — add request/response schemas
- `src/api/routers/trends.py` — add endpoint and DI helper
- `tests/unit/services/conftest.py` — add `MockNewsAPIClient`

## Out of Scope

- Everything endpoint (`/v2/everything`) — for RESEARCH-002
- Redis caching — infrastructure concern, not source-specific
- `language` and `sources` request parameters — can be added later
- Base class extraction across trend sources — separate tech-debt ticket
