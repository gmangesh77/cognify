# TREND-002: Reddit Trend Source — Design Spec

## 1. Overview

**Ticket**: TREND-002 — Reddit Trend Source [Must], 5 story points
**Branch**: `feature/TREND-002-reddit-trend-source`
**Dependencies**: TREND-006 (Topic Ranking & Dedup) — completed; TREND-003 (Hacker News) — completed (establishes pattern)

**Goal**: Monitor configured subreddits for trending posts via asyncpraw, rank by comment velocity, deduplicate cross-posts, and expose as `RawTopic` objects ready for the TREND-006 ranking pipeline.

## 2. Architecture

```
POST /api/v1/trends/reddit/fetch
        ↓
  trends_router (auth + rate limit)
        ↓
  RedditService (iterate subreddits, dedup, filter, score, normalize)
        ↓
  RedditClient (asyncpraw wrapper, per-subreddit fetch)
        ↓
  Reddit API (OAuth2, application-only read access)
        ↓
  List[RawTopic] → ready for TREND-006 ranking pipeline
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| `RedditClient` | `src/services/reddit_client.py` | Thin asyncpraw wrapper, per-subreddit fetch, error translation |
| `RedditService` | `src/services/reddit.py` | Iterate subreddits → aggregate → dedup crossposts → filter → score → normalize to `RawTopic` |
| `trends_router` | `src/api/routers/trends.py` | API endpoint with auth, rate limiting, error handling |
| Schemas | `src/api/schemas/trends.py` | `RedditFetchRequest`, `RedditFetchResponse` Pydantic models |

### Separation of Concerns

- **Client** handles only asyncpraw interaction: OAuth2 session, subreddit fetching, error wrapping. No business logic.
- **Service** handles only business logic: subreddit iteration, crosspost dedup, domain filtering, scoring, normalization. No API/auth concerns.
- **Router** handles only API concerns: auth, rate limiting, error mapping. Delegates to service.

## 3. Reddit Client

### Library Choice

**asyncpraw** (async Python Reddit API Wrapper) — native async fork of PRAW. Avoids `asyncio.to_thread()` wrapping needed for sync libraries. Reddit's OAuth2 flow is complex enough that a dedicated library saves significant effort.

### Authentication

Application-only OAuth2 (client credentials grant). Read-only access to public subreddits. No Reddit user credentials needed.

Required secrets:
- `reddit_client_id` — from Reddit app registration
- `reddit_client_secret` — from Reddit app registration (stored as `SecretStr`)
- `reddit_user_agent` — identifies the app to Reddit (e.g., `"cognify:v1.0 (by /u/cognify-bot)"`)

### Response Type

```python
class RedditPostResponse(TypedDict):
    id: str
    title: str
    selftext: str
    score: int
    num_comments: int
    created_utc: float
    url: str
    permalink: str
    subreddit: str
    upvote_ratio: float
    crosspost_parent: str | None
```

### Client Interface

```python
class RedditClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        timeout: float,
    ) -> None: ...

    async def fetch_subreddit_posts(
        self,
        subreddit: str,
        sort: str,
        time_filter: str,
        limit: int,
    ) -> list[RedditPostResponse]: ...
```

- `sort`: one of `"hot"`, `"top"`, `"new"`, `"rising"`
- `time_filter`: one of `"hour"`, `"day"`, `"week"` (applies to `top` sort only)
- `limit`: max posts to fetch per subreddit (1-100)

The client is **short-lived** — created per request, not stored on `app.state`. asyncpraw session opened and closed per call via `async with`.

**OAuth2 token overhead**: Each per-request client incurs an OAuth2 token exchange round-trip to Reddit's auth endpoint. With the inbound rate limit of 5/minute, this adds at most 5 extra auth requests/minute — acceptable for simplicity. If this becomes a bottleneck (e.g., scheduled cron scanning many subreddits), the client can be moved to `app.state` with lifespan management in a follow-up.

### Error Handling

- asyncpraw HTTP/auth errors → raise `RedditAPIError` with context
- Timeout → raise `RedditAPIError` with timeout context
- Connection error → raise `RedditAPIError` with connection context

`RedditAPIError` is a standalone exception (not extending `OSError`). The trends router catches it and maps to `ServiceUnavailableError(code="reddit_unavailable")`.

### Rate Limiting

Reddit allows 100 requests/minute for OAuth clients. asyncpraw handles this internally with built-in rate limiting. No additional outbound rate limiter needed. The inbound endpoint rate limit of 5/minute provides sufficient protection.

## 4. Scoring & Normalization

### Scoring Formula — Velocity-Heavy

Prioritizes fast-growing discussions over already-popular posts, since trend discovery cares more about *what's gaining traction now*.

```
comment_velocity = num_comments / max(1.0, hours_since_posted)
recency_bonus = 100 * exp(-lambda * hours_since_posted)   # lambda = ln(2)/12, 12h half-life
raw = (score * 0.3) + (comment_velocity * 0.5) + (recency_bonus * 0.2)
trend_score = min(100.0, (raw / score_cap) * 100)
```

- `score_cap` configurable via `reddit_score_cap` setting (default: 1000.0 — Reddit scores run higher than HN)
- A 500-score post, 200 comments in 2 hours: `cv=100`, `rb≈89`, `raw=(150+50+17.8)=217.8`, `score=min(100, 21.8)=21.8`
- A 50-score post, 300 comments in 1 hour: `cv=300`, `rb≈94`, `raw=(15+150+18.8)=183.8`, `score=min(100, 18.4)=18.4`

Note: With `score_cap=1000.0`, most Reddit posts will score in the 10-30 range. This is intentional — TREND-006's composite ranking re-normalizes across sources via min-max normalization on the velocity dimension. The raw `trend_score` serves as relative ordering within Reddit, not an absolute quality measure.

### Upvote Velocity (`RawTopic.velocity` field)

Distinct from `comment_velocity` used in the scoring formula above. This measures upvote accumulation rate and is consumed by TREND-006's velocity dimension scoring:

```
hours = max(1.0, hours_since_posted)
velocity = score / hours
```

- `comment_velocity` (comments/hour) — internal to `calculate_score()`, weights fast-growing discussions
- `velocity` (upvotes/hour) — stored on `RawTopic.velocity`, consumed by TREND-006 ranking

### Crosspost Deduplication

Two-pass dedup within Reddit before domain filtering:

1. **Pass 1 — `crosspost_parent` ID**: Group posts sharing the same `crosspost_parent` value. Free and accurate for Reddit's native crossposts.
2. **Pass 2 — Fuzzy title matching**: For remaining posts, compare titles using `difflib.SequenceMatcher` (stdlib). Ratio > 0.85 → merge into same group. Catches manual reposts with similar titles.

**Complexity note**: Pass 2 is O(n^2) pairwise title comparison. With 4 default subreddits x 100 posts max = 400 posts, worst case is ~80K comparisons which completes in <100ms on short title strings. If subreddit count grows significantly (20+ with 100 posts each), this should be revisited with a more efficient approach (e.g., title hashing or embedding-based clustering).

Per duplicate group:
- Keep the post with the highest `score`
- Track `subreddit_count` (number of subreddits the post appeared in)

### Partial Subreddit Failure

When iterating multiple subreddits, if one fails (e.g., subreddit is private, banned, or rate limited), the service logs the error at WARNING level and continues with remaining subreddits. The response includes only successfully scanned subreddits in `subreddits_scanned`. If *all* subreddits fail, the service raises `RedditAPIError` (propagated as 503).

### Domain Filtering

Pre-filter before TREND-006 ranking:

- Case-insensitive substring match of each domain keyword against: `title`, `selftext`, `subreddit` name
- A post passes if **any** keyword matches
- Matched keywords collected into `domain_keywords` field

### Field Mapping

| Reddit Field | RawTopic Field | Transformation |
|-------------|----------------|----------------|
| `title` | `title` | Direct |
| `selftext` (or empty) | `description` | First 200 chars, fallback to empty string |
| `"reddit"` (literal) | `source` | Constant |
| `permalink` | `external_url` | Prepend `https://www.reddit.com` |
| Computed | `trend_score` | Velocity-heavy formula (see above) |
| `created_utc` | `discovered_at` | Parse Unix timestamp to UTC datetime |
| Computed | `velocity` | `score / max(1.0, hours_since_posted)` |
| Matched keywords | `domain_keywords` | Keywords that matched title/selftext/subreddit |

## 5. API Endpoint

### `POST /api/v1/trends/reddit/fetch`

- **Auth**: `require_role("admin", "editor")`
- **Rate limit**: `5/minute`
- **Tags**: `["trends"]`

### Request Schema — `RedditFetchRequest`

```python
class RedditFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    subreddits: list[str] | None = Field(default=None, max_length=20)
    max_results: int = Field(default=20, ge=1, le=100)
    sort: Literal["hot", "top", "new", "rising"] = "hot"
    time_filter: Literal["hour", "day", "week"] = "day"
```

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `domain_keywords` | `list[str]` | Required | min 1 item | Keywords to filter posts by |
| `subreddits` | `list[str] \| None` | `None` (use settings default) | max 20 items | Subreddits to scan; falls back to `reddit_default_subreddits` |
| `max_results` | `int` | 20 | 1-100 | Max posts to fetch per subreddit |
| `sort` | `Literal` | `"hot"` | hot/top/new/rising | Reddit sort order |
| `time_filter` | `Literal` | `"day"` | hour/day/week | Time window for `top` sort |

### Response Schema — `RedditFetchResponse`

```python
class RedditFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_dedup: int
    total_after_filter: int
    subreddits_scanned: int
```

| Field | Type | Description |
|-------|------|-------------|
| `topics` | `list[RawTopic]` | Filtered, deduped, scored topics |
| `total_fetched` | `int` | Posts fetched across all subreddits before dedup |
| `total_after_dedup` | `int` | Posts remaining after crosspost dedup |
| `total_after_filter` | `int` | Posts that passed domain keyword filter |
| `subreddits_scanned` | `int` | Number of subreddits queried |

### Error Responses

| Condition | Status | Error Code |
|-----------|--------|------------|
| No auth token | 401 | `authentication_required` |
| Insufficient role | 403 | `insufficient_permissions` |
| Invalid request body | 422 | Pydantic validation error |
| Reddit API unreachable | 503 | `reddit_unavailable` |

No posts matching filter returns 200 with empty `topics` list.

## 6. Settings

New fields in `src/config/settings.py`:

```python
# Reddit integration
reddit_client_id: str = ""
reddit_client_secret: SecretStr = SecretStr("")
reddit_user_agent: str = "cognify:v1.0 (by /u/cognify-bot)"
reddit_default_subreddits: list[str] = [
    "cybersecurity", "programming", "netsec", "technology",
]
reddit_score_cap: float = 1000.0
reddit_request_timeout: float = 15.0
```

All overridable via `COGNIFY_REDDIT_*` environment variables.

**`SecretStr` note**: This introduces the `SecretStr` pattern for new secrets. Existing secrets (`jwt_private_key`, `jwt_public_key`) use plain `str` and should be migrated to `SecretStr` in a follow-up tech-debt ticket.

## 7. Dependency Injection

```python
def _get_reddit_service(request: Request) -> RedditService:
    settings = request.app.state.settings
    if hasattr(request.app.state, "reddit_client"):
        client = request.app.state.reddit_client
    else:
        client = RedditClient(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret.get_secret_value(),
            user_agent=settings.reddit_user_agent,
            timeout=settings.reddit_request_timeout,
        )
    return RedditService(
        client=client,
        score_cap=settings.reddit_score_cap,
    )
```

Per-request service creation, with test injection via `app.state.reddit_client`.

## 8. Structured Logging

| Event | Level | Fields |
|-------|-------|--------|
| `reddit_fetch_started` | INFO | `domain_keywords`, `subreddits`, `max_results`, `sort` |
| `reddit_fetch_completed` | INFO | `total_fetched`, `total_after_dedup`, `total_after_filter`, `subreddits_scanned`, `duration_ms` |
| `reddit_api_error` | ERROR | `error`, `subreddit` (if available) |
| `reddit_posts_filtered` | DEBUG | `before_count`, `after_count`, `domain_keywords` |
| `reddit_crossposts_deduped` | DEBUG | `before_count`, `after_count`, `groups_merged` |

## 9. Testing Strategy

### Mock Infrastructure

`MockRedditClient(RedditClient)` added to `tests/unit/services/conftest.py`:
- Constructor calls `super().__init__("mock", "mock", "mock", 1.0)` with dummy values (safe since `__init__` only stores parameters, no real connections)
- Constructor takes `posts: dict[str, list[RedditPostResponse]]` keyed by subreddit name
- Returns canned posts per subreddit for deterministic testing
- No real asyncpraw calls

### Unit Tests

**`tests/unit/services/test_reddit_client.py`**:
- Client calls asyncpraw correctly (mocked asyncpraw instance)
- Translates asyncpraw exceptions to `RedditAPIError`
- Timeout handling
- Empty subreddit returns empty list

**`tests/unit/services/test_reddit.py`**:
- `TestScoreNormalization` — parametrized: standard score, zero comments, high score capped at 100, zero score
- `TestVelocityCalculation` — parametrized: standard, very recent post (< 1 hour floors to 1), old post
- `TestCrosspostDedup` — posts with same `crosspost_parent` merged (highest score kept); fuzzy title match merges near-duplicates; unique posts preserved; `subreddit_count` tracked correctly
- `TestDomainFiltering` — matches title, selftext, subreddit name; case-insensitive; no match returns empty
- `TestMapToRawTopic` — all `RawTopic` fields populated, source = `"reddit"`, external_url has full Reddit permalink
- `TestFetchAndNormalize` — full pipeline with MockRedditClient, verifies end-to-end flow, correct counts in response metadata

### Integration Tests

**`tests/integration/api/test_trends_reddit.py`**:
- Endpoint returns 200 with valid request (mocked client via `app.state`)
- Endpoint returns 401 without auth
- Endpoint returns 403 for viewer role
- Endpoint returns 503 when Reddit API unavailable
- Validates response schema matches `RedditFetchResponse`

### Coverage Target

80%+ on all new files, consistent with project standards.

## 10. File Inventory

### New Files

| File | Purpose |
|------|---------|
| `src/services/reddit_client.py` | asyncpraw Reddit API client |
| `src/services/reddit.py` | Reddit business logic service |
| `tests/unit/services/test_reddit_client.py` | Client unit tests |
| `tests/unit/services/test_reddit.py` | Service unit tests |
| `tests/integration/api/test_trends_reddit.py` | Endpoint integration tests |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `asyncpraw` dependency; add `[[tool.mypy.overrides]]` for `asyncpraw.*` (lacks complete type stubs, similar to existing `pytrends` override) |
| `src/config/settings.py` | Add `reddit_*` settings fields |
| `src/api/routers/trends.py` | Add `POST /api/v1/trends/reddit/fetch` endpoint |
| `src/api/schemas/trends.py` | Add `RedditFetchRequest`, `RedditFetchResponse` |
| `tests/unit/services/conftest.py` | Add `MockRedditClient` |

## 11. Future Integration Points

- **Trend Detection Agent** (RESEARCH-001+): Will call `RedditService` directly as part of multi-source polling loop
- **Redis caching**: Raw Reddit signals cached with TTL (15min) once Redis infrastructure is built
- **Subreddit discovery**: Future enhancement — auto-discover relevant subreddits based on domain keywords
- **Comment analysis**: Future enhancement — analyze top comments for sentiment and key points
