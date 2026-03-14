# Design Spec: TREND-004 — NewsAPI Integration

## Overview

Integrate NewsAPI Top Headlines as a trend source for Cognify's trend discovery engine. Follows the established client/service/router pattern used by Google Trends, Reddit, and Hacker News integrations.

## Decisions

- **Endpoint used**: Top Headlines only (`/v2/top-headlines`). The Everything endpoint is out of scope — it's better suited for research (RESEARCH-002) than trend discovery.
- **Scoring**: Hybrid formula combining position rank, recency, and keyword match count. NewsAPI articles lack engagement metrics (no likes/comments), so position and freshness are the primary signals.
- **Deduplication**: By URL (exact match). News articles have unique URLs, making this simple and sufficient.
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
- Constructor: `__init__(self, client: NewsAPIClient, score_cap: float)`.
- Main method: `async fetch_and_normalize(domain_keywords: list[str], category: str, country: str, max_results: int) -> NewsAPIFetchResponse`.

**Pipeline**:
1. Fetch via `client.fetch_top_headlines(category, country, page_size=max_results)`.
2. `filter_by_domain(articles, domain_keywords)` — match keywords against title + description (case-insensitive). Returns `list[tuple[NewsAPIArticle, list[str]]]`.
3. `calculate_score(index, total, published_at, matched_keywords)` — hybrid scoring.
4. `calculate_velocity(published_at)` — recency-based.
5. `map_to_raw_topic(article, score, velocity, matched_keywords)` — map to `RawTopic`.
6. `_deduplicate(topics)` — by URL, keep higher score.

**Scoring formula** (`@staticmethod`):
```python
position_score = max(0, 100 - (index * (100 / total)))
recency_bonus = exp(-lambda * hours)  # lambda = ln(2) / 6, 6-hour half-life
keyword_bonus = min(20, len(matched_keywords) * 5)
trend_score = min(100, position_score * 0.5 + recency_bonus * 30 + keyword_bonus)
```

**Velocity formula** (`@staticmethod`):
```python
velocity = 1.0 / max(1.0, hours_since_published)
```

**RawTopic mapping** (`@staticmethod`):
- `title` = article title
- `description` = article description (or `""` if None)
- `source` = `"newsapi"`
- `external_url` = article URL
- `trend_score` = calculated score
- `velocity` = calculated velocity
- `discovered_at` = `datetime.now(UTC)`
- `domain_keywords` = matched keywords

**Deduplication**: Group by URL, keep highest-scoring entry.

**Structured logging**:
- `newsapi_fetch_started` — domain_keywords, category, country, max_results
- `newsapi_fetch_completed` — total_fetched, total_after_filter, duration_ms
- `newsapi_items_filtered` (DEBUG) — before_count, after_count, domain_keywords

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
- Dependency injection: check `request.app.state.newsapi_client` for test mock, else create `NewsAPIClient` from settings.
- Catch `NewsAPIError` → raise `ServiceUnavailableError(code="newsapi_unavailable", message="NewsAPI is not available")`.

**Settings** (extend `src/config/settings.py`):
- `newsapi_api_key: str = ""`
- `newsapi_base_url: str = "https://newsapi.org/v2"`
- `newsapi_request_timeout: float = 10.0`
- `newsapi_default_category: str = "technology"`
- `newsapi_default_country: str = "us"`
- `newsapi_score_cap: float = 100.0`

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
- `_deduplicate`: duplicate URLs keep higher score
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

## Out of Scope

- Everything endpoint (`/v2/everything`) — for RESEARCH-002
- Redis caching — infrastructure concern, not source-specific
- `language` and `sources` request parameters — can be added later
- Base class extraction across trend sources — separate tech-debt ticket
