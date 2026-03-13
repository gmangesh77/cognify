# TREND-003: Hacker News Integration — Design Spec

## 1. Overview

**Ticket**: TREND-003 — Hacker News Integration [Must], 3 story points
**Branch**: `feature/TREND-003-hackernews-integration`
**Dependencies**: TREND-006 (Topic Ranking & Dedup) — completed

**Goal**: Fetch trending stories from Hacker News via the Algolia HN Search API, filter by domain relevance, normalize scores, and expose as `RawTopic` objects ready for the TREND-006 ranking pipeline.

## 2. Architecture

```
POST /api/v1/trends/hackernews/fetch
        ↓
  trends_router (auth + rate limit)
        ↓
  HackerNewsService (filter, score, normalize)
        ↓
  HackerNewsClient (HTTP calls to Algolia)
        ↓
  Algolia HN API (https://hn.algolia.com/api/v1)
        ↓
  List[RawTopic] → ready for TREND-006 ranking pipeline
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| `HackerNewsClient` | `src/services/hackernews_client.py` | HTTP calls to Algolia HN API, returns typed story dicts |
| `HackerNewsService` | `src/services/hackernews.py` | Orchestrates fetch → filter → score → normalize into `RawTopic` |
| `trends_router` | `src/api/routers/trends.py` | API endpoint with auth, rate limiting, error handling |
| Schemas | `src/api/schemas/trends.py` | `HNFetchRequest`, `HNFetchResponse` Pydantic models |

### Separation of Concerns

- **Client** handles only HTTP: request construction, response parsing, error wrapping. No business logic.
- **Service** handles only business logic: domain filtering, scoring, normalization. No HTTP concerns.
- **Router** handles only API concerns: auth, rate limiting, error mapping. Delegates to service.

## 3. Algolia HN Client

### Algolia Response Type

The client returns typed dicts instead of `dict[str, Any]` to satisfy strict mypy:

```python
class HNStoryResponse(TypedDict):
    objectID: str
    title: str
    url: str | None
    points: int | None
    num_comments: int | None
    story_text: str | None
    created_at_i: int
```

### API Endpoints Used

| Method | Algolia Endpoint | Purpose |
|--------|-----------------|---------|
| `fetch_stories()` | `GET /api/v1/search` | Search stories by query, tags, filters |

Only `fetch_stories` is implemented. A `fetch_top_stories` (front page) method can be added later if needed — YAGNI for 3 story points since the service always filters by domain keywords anyway.

### Query Parameters

- `query`: Domain keywords (e.g., `"cybersecurity"`)
- `tags`: `story` (filter to stories only)
- `numericFilters`: `points>N` (minimum points threshold)
- `hitsPerPage`: Number of results (default 30, max 100)

### Client Interface

```python
class HackerNewsClient:
    def __init__(self, base_url: str, timeout: float) -> None: ...
    async def fetch_stories(
        self,
        query: str,
        min_points: int,
        num_results: int,
    ) -> list[HNStoryResponse]: ...
```

The client is **short-lived** — created per request, not stored on `app.state`. This avoids lifecycle management complexity (no `close()` needed). `httpx.AsyncClient` is used within an `async with` block inside `fetch_stories`.

### Error Handling

- HTTP 4xx/5xx → raise `HackerNewsAPIError` with status code and message
- Timeout → raise `HackerNewsAPIError` with timeout context
- Connection error → raise `HackerNewsAPIError` with connection context

`HackerNewsAPIError` is a standalone exception (not extending `OSError`). The trends router catches `HackerNewsAPIError` explicitly and maps it to `ServiceUnavailableError(code="hackernews_unavailable")`.

### Algolia Rate Limits

The Algolia HN API allows 10,000 requests/hour on the free tier. The inbound rate limit of 5/minute (300/hour max) provides sufficient protection. No additional outbound rate limiting is needed.

## 4. Scoring & Normalization

### Trend Score (0-100)

Linear normalization combining points and comment count:

```
raw = (points * 0.7) + (num_comments * 0.3)
score = min(100, (raw / points_cap) * 100)
```

- `points_cap` configurable via `hn_points_cap` setting (default: 300.0)
- A 300-point story with 100 comments: `(300*0.7 + 100*0.3) / 300 * 100 = 100`
- A 50-point story with 20 comments: `(50*0.7 + 20*0.3) / 300 * 100 ≈ 13.7`

### Velocity

Points-per-hour since posted:

```
hours = max(1, hours_since_posted)
velocity = points / hours
```

Measures how fast a story is gaining traction. A 100-point story posted 2 hours ago has velocity 50; a 100-point story posted 20 hours ago has velocity 5.

### Domain Filtering

Pre-filter before TREND-006 ranking:

- Case-insensitive substring match of each domain keyword against story title and URL
- A story passes if **any** keyword matches
- Stories with zero matches are excluded
- Matched keywords are collected into `domain_keywords` field

### Field Mapping

| Algolia Response Field | RawTopic Field | Transformation |
|----------------------|----------------|----------------|
| `title` | `title` | Direct |
| `story_text` (or empty) | `description` | First 200 chars, fallback to empty string |
| `"hackernews"` (literal) | `source` | Constant |
| `url` (or HN item URL) | `external_url` | Fallback: `https://news.ycombinator.com/item?id={objectID}` |
| Computed | `trend_score` | `min(100, (points*0.7 + comments*0.3) / cap * 100)` |
| `created_at_i` (Unix timestamp) | `discovered_at` | Parse to UTC datetime |
| Computed | `velocity` | `points / max(1, hours_since_posted)` |
| Matched keywords | `domain_keywords` | Keywords that matched title/URL |

## 5. API Endpoint

### `POST /api/v1/trends/hackernews/fetch`

- **Auth**: `require_role("admin", "editor")`
- **Rate limit**: `5/minute`
- **Tags**: `["trends"]`

### Request Schema — `HNFetchRequest`

```python
class HNFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    max_results: int = Field(default=30, ge=1, le=100)
    min_points: int = Field(default=10, ge=0)
```

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `domain_keywords` | `list[str]` | Required | min 1 item | Keywords to filter stories by |
| `max_results` | `int` | 30 | 1-100 | Max stories to fetch from Algolia |
| `min_points` | `int` | 10 | >= 0 | Minimum HN points threshold |

### Response Schema — `HNFetchResponse`

```python
class HNFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_filter: int
```

| Field | Type | Description |
|-------|------|-------------|
| `topics` | `list[RawTopic]` | Filtered, scored topics |
| `total_fetched` | `int` | Stories fetched from Algolia before filtering |
| `total_after_filter` | `int` | Stories that passed domain keyword filter |

### Error Responses

| Condition | Status | Error Code |
|-----------|--------|------------|
| No auth token | 401 | `authentication_required` |
| Insufficient role | 403 | `insufficient_permissions` |
| Invalid request body | 422 | Pydantic validation error |
| Algolia API unreachable | 503 | `hackernews_unavailable` |

No stories matching filter returns 200 with empty `topics` list.

## 6. Settings

New fields in `src/config/settings.py`:

```python
# Hacker News integration
hn_api_base_url: str = "https://hn.algolia.com/api/v1"
hn_default_max_results: int = 30
hn_default_min_points: int = 10
hn_points_cap: float = 300.0
hn_request_timeout: float = 10.0
```

All overridable via `COGNIFY_HN_*` environment variables.

## 7. Router Registration

The `trends_router` is registered in `src/api/main.py`:

```python
from src.api.routers.trends import trends_router

app.include_router(
    trends_router,
    prefix=settings.api_v1_prefix,
    tags=["trends"],
)
```

This establishes the pattern for all future trend source integrations (TREND-001, 002, 004, 005). Each source gets a sub-path under `/trends/` (e.g., `/trends/reddit/fetch`, `/trends/googlenews/fetch`), all served by the same `trends_router`.

## 8. Structured Logging

| Event | Level | Fields |
|-------|-------|--------|
| `hackernews_fetch_started` | INFO | `domain_keywords`, `max_results`, `min_points` |
| `hackernews_fetch_completed` | INFO | `total_fetched`, `total_after_filter`, `duration_ms` |
| `hackernews_api_error` | ERROR | `error`, `status_code` (if available) |
| `hackernews_stories_filtered` | DEBUG | `before_count`, `after_count`, `domain_keywords` |

## 9. Testing Strategy

### Unit Tests

**`tests/unit/services/test_hackernews_client.py`**:
- Successful fetch returns parsed stories
- Timeout raises `HackerNewsAPIError`
- HTTP error raises `HackerNewsAPIError` with status code
- Empty results return empty list

**`tests/unit/services/test_hackernews.py`**:
- Score normalization: various point/comment combinations
- Score capping at 100
- Velocity calculation: points-per-hour
- Domain filtering: matching, non-matching, case-insensitive
- Field mapping: all Algolia fields mapped correctly
- Edge cases: zero points, missing URL, missing story_text, very old stories
- Empty input returns empty output

**`tests/unit/api/test_trend_schemas.py`**:
- Valid request passes validation
- Empty domain_keywords rejected (422)
- max_results out of range rejected
- min_points negative rejected
- Response schema shape

**`tests/unit/api/test_trend_endpoints.py`**:
- No token → 401
- Viewer role → 403
- Editor/admin → 200
- Invalid body → 422
- Algolia unavailable → 503
- Successful fetch → correct response shape

### Test Infrastructure

- `MockHackerNewsClient`: Returns canned Algolia JSON responses for deterministic service testing
- Realistic Algolia response fixture with representative story data
- Uses existing auth test helpers from `tests/unit/api/conftest.py`

### Coverage Target

80%+ on all new files, consistent with project standards.

## 10. File Inventory

### New Files

| File | Purpose |
|------|---------|
| `src/services/hackernews_client.py` | Algolia HN API HTTP client |
| `src/services/hackernews.py` | HN business logic service |
| `src/api/routers/trends.py` | Trends API endpoint |
| `src/api/schemas/trends.py` | Request/response Pydantic models |
| `tests/unit/services/test_hackernews_client.py` | Client unit tests |
| `tests/unit/services/test_hackernews.py` | Service unit tests |
| `tests/unit/api/test_trend_schemas.py` | Schema validation tests |
| `tests/unit/api/test_trend_endpoints.py` | Endpoint tests |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Promote `httpx` from dev to prod dependency |
| `src/config/settings.py` | Add `hn_*` settings fields |
| `src/api/main.py` | Register `trends_router` |

## 11. Future Integration Points

- **Trend Detection Agent** (RESEARCH-001+): Will call `HackerNewsService` directly as part of multi-source polling loop
- **Redis caching**: Raw HN signals cached with TTL (15min) once Redis infrastructure is built
- **Other trend sources** (TREND-001, 002, 004, 005): Will follow the same Client + Service + Router pattern established here
