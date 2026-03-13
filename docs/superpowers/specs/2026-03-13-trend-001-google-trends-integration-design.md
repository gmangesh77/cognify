# TREND-001: Google Trends Integration — Design Spec

## 1. Overview

**Ticket**: TREND-001 — Google Trends Integration [Must], 5 story points
**Branch**: `feature/TREND-001-google-trends-integration`
**Dependencies**: TREND-006 (Topic Ranking & Dedup) — completed

**Goal**: Fetch trending searches and related queries from Google Trends via pytrends, filter by domain relevance, normalize scores, and expose as `RawTopic` objects ready for the TREND-006 ranking pipeline.

## 2. Architecture

```
POST /api/v1/trends/google/fetch
        ↓
  trends_router (auth + rate limit)
        ↓
  GoogleTrendsService (combine, filter, score, normalize)
        ↓
  GoogleTrendsClient (wraps pytrends library)
        ↓
  Google Trends (via pytrends scraping)
        ↓
  List[RawTopic] → ready for TREND-006 ranking pipeline
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| `GoogleTrendsClient` | `src/services/google_trends_client.py` | Wraps pytrends — `fetch_trending_searches()` and `fetch_related_queries()`. No business logic. |
| `GoogleTrendsService` | `src/services/google_trends.py` | Combines both data sources, filters by domain, scores, normalizes into `RawTopic` |
| `trends_router` | `src/api/routers/trends.py` (existing) | New route added alongside HN endpoint |
| Schemas | `src/api/schemas/trends.py` (existing) | Add `GTFetchRequest`, `GTFetchResponse` |

### Separation of Concerns

- **Client** handles only pytrends interaction: constructing requests, parsing responses, error wrapping. No business logic.
- **Service** handles only business logic: combining data sources, domain filtering, scoring, normalization. No pytrends concerns.
- **Router** handles only API concerns: auth, rate limiting, error mapping. Delegates to service.

### Threading

pytrends is a **synchronous** library. To avoid blocking the FastAPI async event loop, all pytrends calls are wrapped with `asyncio.to_thread()`:

```python
result = await asyncio.to_thread(self._fetch_trending_sync, country)
```

The client is **short-lived** — created per request, not stored on `app.state`. This avoids lifecycle management complexity.

## 3. GoogleTrendsClient

### Typed Responses

```python
class GTTrendingSearch(TypedDict):
    title: str

class GTRelatedQuery(TypedDict):
    title: str
    value: int
    query_type: str       # "rising" or "top"
    seed_keyword: str
```

### Client Interface

```python
class GoogleTrendsClient:
    def __init__(
        self, language: str, timezone_offset: int, timeout: float,
    ) -> None: ...

    async def fetch_trending_searches(
        self, country: str,
    ) -> list[GTTrendingSearch]: ...

    async def fetch_related_queries(
        self, keywords: list[str],
    ) -> list[GTRelatedQuery]: ...
```

- The constructor creates a `TrendReq(hl=language, tz=timezone_offset, requests_args={'timeout': timeout})` instance.
- `fetch_trending_searches` calls `pytrends.trending_searches(pn=country)` via `asyncio.to_thread()`. Returns up to 20 trending search terms.
- `fetch_related_queries` calls `pytrends.build_payload(kw_list=keywords[:5])` then `pytrends.related_queries()` via `asyncio.to_thread()`. Returns rising and top related queries for each keyword. **Note**: pytrends supports a maximum of 5 keywords per `build_payload` call — the client takes only the first 5 keywords silently.

### "Breakout" Value Handling

pytrends may return the string `"Breakout"` instead of an integer for rising queries with extreme growth. The client converts `"Breakout"` to the sentinel value `5000` when constructing `GTRelatedQuery`, ensuring the `value` field is always `int`.

### Error Handling

- pytrends `ResponseError` → raise `GoogleTrendsAPIError` with context
- `requests.ConnectionError` → raise `GoogleTrendsAPIError` with connection context
- `requests.Timeout` → raise `GoogleTrendsAPIError` with timeout context
- Any other `Exception` during pytrends calls → raise `GoogleTrendsAPIError`

`GoogleTrendsAPIError` is a standalone exception (not extending `OSError`). The trends router catches it explicitly and maps to `ServiceUnavailableError(code="google_trends_unavailable")`.

### pytrends Rate Limits

Google imposes implicit rate limits on trends scraping. The inbound rate limit of 5/minute provides protection. A 15-second timeout per request allows for pytrends' slower response times.

## 4. GoogleTrendsService

### Service Interface

```python
class GoogleTrendsService:
    def __init__(self, client: GoogleTrendsClient) -> None: ...

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        country: str,
        max_results: int,
    ) -> GTFetchResponse: ...

    @staticmethod
    def calculate_score(query_type: str, value: int) -> float: ...

    @staticmethod
    def calculate_velocity(query_type: str, value: int) -> float: ...

    @staticmethod
    def filter_by_domain(
        items: list[GTTrendingSearch | GTRelatedQuery],
        domain_keywords: list[str],
    ) -> list[tuple[GTTrendingSearch | GTRelatedQuery, list[str]]]: ...

    @staticmethod
    def map_to_raw_topic(
        title: str,
        query_type: str,
        value: int,
        matched_keywords: list[str],
    ) -> RawTopic: ...
```

- Constructor takes only `client` (no scoring config needed — formulas are fixed).
- `fetch_and_normalize` orchestrates: fetch both sources → combine → filter → score → deduplicate → return.
- `map_to_raw_topic` is a `@staticmethod` with 4 params: `title`, `query_type` (`"trending"`, `"rising"`, `"top"`), `value` (score input), and `matched_keywords`. The `query_type` discriminator drives which scoring/velocity formula is applied. Note: the project standard is max 3 params, but `@staticmethod` has no `self`, and grouping these into a container would be over-engineering for a mapping function.

### Deduplication

Since trending searches and related queries can overlap, the service deduplicates by title (case-insensitive) before returning. When duplicates exist, the higher-scoring entry is kept. On equal scores, the first encountered entry is kept.

## 5. Scoring & Normalization

**Note**: Scoring formulas handle the "Breakout" sentinel value (5000) correctly — rising score caps at 100, velocity caps at 100.

### Trend Score (0-100)

**Trending searches** — Currently trending by Google's definition:
- Base score: `70` (fixed — no numeric ranking data available)

**Related queries (rising)** — Have a percentage growth value:
```
score = min(100, 50 + (value / 100) * 10)
```
- A 500%+ rising query gets score 100
- A 100% rising query gets score 60

**Related queries (top)** — Have a relative volume 0-100:
```
score = value
```
- Maps directly to our 0-100 scale

### Velocity

Since pytrends doesn't provide per-query timestamps:
- Trending searches: `velocity = 50.0` (high — currently trending)
- Rising related queries: `velocity = min(100.0, value / 10.0)` (higher rise % = higher velocity)
- Top related queries: `velocity = 5.0` (stable, not fast-moving)

### Domain Filtering

Pre-filter before TREND-006 ranking:
- Case-insensitive substring match of each domain keyword against query title
- A query passes if **any** keyword matches
- Queries with zero matches are excluded
- Matched keywords collected into `domain_keywords` field

### Field Mapping

| Source Data | RawTopic Field | Transformation |
|------------|----------------|----------------|
| Query text | `title` | Direct |
| `""` | `description` | Empty (queries are short) |
| `"google_trends"` | `source` | Constant |
| Constructed URL | `external_url` | `https://trends.google.com/trends/explore?q={url_encoded_query}` |
| Computed | `trend_score` | Per formula above |
| `datetime.now(UTC)` | `discovered_at` | Current time (no per-query timestamps) |
| Computed | `velocity` | Per formula above |
| Matched keywords | `domain_keywords` | Keywords that matched |

## 6. API Endpoint

### `POST /api/v1/trends/google/fetch`

- **Auth**: `require_role("admin", "editor")`
- **Rate limit**: `5/minute`
- **Tags**: `["trends"]`

### Request Schema — `GTFetchRequest`

```python
class GTFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    country: str = Field(default="united_states")
    max_results: int = Field(default=30, ge=1, le=100)
```

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `domain_keywords` | `list[str]` | Required | min 1 item | Keywords to filter results and seed related queries |
| `country` | `str` | `"united_states"` | — | Country for trending searches (pytrends country code) |
| `max_results` | `int` | 30 | 1-100 | Max topics to return after filtering |

### Response Schema — `GTFetchResponse`

```python
class GTFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_trending: int
    total_related: int
    total_after_filter: int
```

| Field | Type | Description |
|-------|------|-------------|
| `topics` | `list[RawTopic]` | Filtered, scored, deduplicated topics (capped at `max_results`) |
| `total_trending` | `int` | Trending searches fetched from pytrends |
| `total_related` | `int` | Related queries fetched from pytrends |
| `total_after_filter` | `int` | Topics remaining after domain filter + dedup (before `max_results` cap) |

### Error Responses

| Condition | Status | Error Code |
|-----------|--------|------------|
| No auth token | 401 | `authentication_required` |
| Insufficient role | 403 | `insufficient_permissions` |
| Invalid request body | 422 | Pydantic validation error |
| pytrends unavailable | 503 | `google_trends_unavailable` |

No stories matching filter returns 200 with empty `topics` list.

## 7. Settings

New fields in `src/config/settings.py`:

```python
# Google Trends integration
gt_language: str = "en-US"
gt_timezone_offset: int = 360
gt_default_country: str = "united_states"
gt_default_max_results: int = 30
gt_request_timeout: float = 15.0
```

All overridable via `COGNIFY_GT_*` environment variables.

## 8. Structured Logging

| Event | Level | Fields |
|-------|-------|--------|
| `google_trends_fetch_started` | INFO | `domain_keywords`, `country`, `max_results` |
| `google_trends_fetch_completed` | INFO | `total_trending`, `total_related`, `total_after_filter`, `duration_ms` |
| `google_trends_api_error` | ERROR | `error` |
| `google_trends_results_filtered` | DEBUG | `before_count`, `after_count`, `domain_keywords` |

## 9. Testing Strategy

### Unit Tests

**`tests/unit/services/test_google_trends_client.py`** (~5 tests):
- Successful trending searches fetch returns parsed results
- Successful related queries fetch returns parsed results
- Empty results return empty lists
- pytrends error raises `GoogleTrendsAPIError`
- Timeout raises `GoogleTrendsAPIError`

**`tests/unit/services/test_google_trends.py`** (~15 tests):
- Score calculation: trending searches (fixed 70), rising queries, top queries
- Score capping at 100
- Velocity assignment by query type
- Domain filtering: matching, non-matching, case-insensitive
- Field mapping: all fields mapped correctly to RawTopic
- Deduplication: overlapping results between trending + related (higher score wins)
- Empty input returns empty output
- `fetch_and_normalize` full pipeline with mock client

**`tests/unit/api/test_google_trends_schemas.py`** (~6 tests):
- Valid request passes validation
- Empty domain_keywords rejected (422)
- max_results out of range rejected
- Default values applied correctly
- Response schema shape

**`tests/unit/api/test_google_trends_endpoints.py`** (~8 tests):
- No token → 401
- Viewer role → 403
- Editor/admin → 200
- Invalid body → 422
- pytrends unavailable → 503
- Successful fetch → correct response shape
- No matches → empty topics

### Test Infrastructure

- `MockGoogleTrendsClient` in `tests/unit/services/conftest.py`: Returns canned trending searches and related queries for deterministic service testing
- Uses existing auth test helpers from `tests/unit/api/conftest.py`

### Coverage Target

80%+ on all new files, consistent with project standards.

## 10. File Inventory

### New Files

| File | Purpose |
|------|---------|
| `src/services/google_trends_client.py` | pytrends wrapper client |
| `src/services/google_trends.py` | Google Trends business logic service |
| `tests/unit/services/test_google_trends_client.py` | Client unit tests |
| `tests/unit/services/test_google_trends.py` | Service unit tests |
| `tests/unit/api/test_google_trends_schemas.py` | Schema validation tests |
| `tests/unit/api/test_google_trends_endpoints.py` | Endpoint tests |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `pytrends>=4.10.0` to prod dependencies |
| `src/config/settings.py` | Add `gt_*` settings fields |
| `src/api/schemas/trends.py` | Add `GTFetchRequest`, `GTFetchResponse` |
| `src/api/routers/trends.py` | Add `POST /trends/google/fetch` route |

## 11. Future Integration Points

- **Polling/Cron**: When Celery infrastructure is built, `GoogleTrendsService` will be called on a configurable interval (default 30 min) by the Trend Detection Agent
- **Redis caching**: Raw Google Trends signals cached with TTL (15 min) once Redis infrastructure is built
- **Other trend sources** (TREND-002, 004, 005): Follow the same Client + Service + Router pattern
- **SerpAPI upgrade**: If pytrends becomes unreliable, swap `GoogleTrendsClient` internals to use SerpAPI without changing the service or router layers
