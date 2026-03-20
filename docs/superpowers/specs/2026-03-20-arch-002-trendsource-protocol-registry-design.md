# ARCH-002: TrendSource Protocol & Registry — Design Specification

> **Date**: 2026-03-20
> **Ticket**: ARCH-002
> **Type**: Refactoring (internal logic preserved; API endpoint URLs change — see Section 4.8)
> **Branch**: `feature/ARCH-002-trendsource-protocol-registry`

---

## 1. Problem Statement

All 5 trend sources follow the same two-layer pattern (client + service) and normalize to `RawTopic`, but there is no formal contract enforcing this. The `src/api/routers/trends.py` router has 276 lines of copy-pasted boilerplate: 5 factory functions and 5 near-identical endpoint handlers. Each new source would add ~50 lines with zero new logic.

Additionally, there is no way to write generic code like "run all active sources in parallel" — each must be called individually with source-specific request/response schemas.

## 2. Goals

1. Define a `TrendSource` protocol formalizing the common interface
2. Create a `TrendSourceRegistry` for runtime source management
3. Replace 5 copy-paste router handlers with a single registry-driven endpoint
4. Move all 10 trend source files into `src/services/trends/` package
5. Preserve all existing internal behavior — same filtering, scoring, dedup logic (API endpoint URLs change; no current consumers are affected)

## 3. Non-Goals

- No new trend sources added
- No changes to scoring algorithms or dedup logic
- No changes to `TopicRankingService` (downstream consumer)
- No changes to Settings field names (only how they're read at init time)

---

## 4. Design

### 4.1 Protocol & Core Models

**File: `src/services/trends/protocol.py`** (~40 lines)

```python
from typing import Protocol

from pydantic import BaseModel, Field

from src.api.schemas.topics import RawTopic


class TrendFetchConfig(BaseModel):
    """Common parameters passed to every trend source."""

    domain_keywords: list[str] = Field(min_length=1)
    max_results: int = Field(default=30, ge=1, le=100)


class TrendSourceError(Exception):
    """Base error for all trend source failures."""

    def __init__(self, source_name: str, message: str) -> None:
        self.source_name = source_name
        super().__init__(f"[{source_name}] {message}")


class TrendSource(Protocol):
    """Contract that all trend sources must satisfy."""

    @property
    def source_name(self) -> str: ...

    async def fetch_and_normalize(
        self, config: TrendFetchConfig
    ) -> list[RawTopic]: ...
```

**Design decisions:**

- `TrendFetchConfig` contains only universal parameters (`domain_keywords`, `max_results`). Source-specific params (subreddits, categories, country, min_points) are set on the service at construction time from Settings.
- `TrendSourceError` provides a common base for all source errors. Existing error classes (`HackerNewsAPIError`, `RedditAPIError`, etc.) will subclass it. The router handler catches `TrendSourceError` generically.
- `source_name` is a `@property` on the protocol rather than a class attribute, because Python protocols support properties but not class-level attribute enforcement on instances without `__init_subclass__` tricks. Each service implements it as a simple property returning a string constant.

### 4.2 Response Models

**File: `src/api/schemas/trends.py`** (replaces current 77-line file, ~40 lines)

```python
from pydantic import BaseModel, Field

from src.api.schemas.topics import RawTopic


class TrendFetchRequest(BaseModel):
    """Request body for the unified trend fetch endpoint."""

    domain_keywords: list[str] = Field(min_length=1)
    max_results: int = Field(default=30, ge=1, le=100)
    sources: list[str] | None = Field(
        default=None,
        description="Sources to query. None = all active sources.",
    )


class SourceResult(BaseModel):
    """Per-source result metadata."""

    source_name: str
    topics: list[RawTopic]
    topic_count: int
    duration_ms: int
    error: str | None = None


class TrendFetchResponse(BaseModel):
    """Unified response combining results from multiple sources."""

    topics: list[RawTopic]
    sources_queried: list[str]
    source_results: dict[str, SourceResult]
```

**What's deleted:** `HNFetchRequest`, `HNFetchResponse`, `GTFetchRequest`, `GTFetchResponse`, `RedditFetchRequest`, `RedditFetchResponse`, `NewsAPIFetchRequest`, `NewsAPIFetchResponse`, `ArxivFetchRequest`, `ArxivFetchResponse` — all 10 schemas replaced by the 3 above.

### 4.3 Registry

**File: `src/services/trends/registry.py`** (~35 lines)

```python
class TrendSourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, TrendSource] = {}

    def register(self, source: TrendSource) -> None:
        """Register a trend source. Overwrites if name already registered."""
        self._sources[source.source_name] = source

    def get(self, name: str) -> TrendSource:
        """Get a source by name. Raises KeyError if not found."""
        return self._sources[name]

    def get_all(self) -> dict[str, TrendSource]:
        """Return all registered sources."""
        return dict(self._sources)

    def available_sources(self) -> list[str]:
        """Return sorted list of registered source names."""
        return sorted(self._sources.keys())
```

No auto-discovery — explicit registration only.

### 4.4 Registry Initialization

**File: `src/services/trends/__init__.py`** (~90 lines)

Each source has a small factory function (< 20 lines each). The top-level `init_registry` calls them all:

```python
def _register_hackernews(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = HackerNewsClient(
        base_url=settings.hn_api_base_url,
        timeout=settings.hn_request_timeout,
    )
    registry.register(HackerNewsService(
        client=client,
        points_cap=settings.hn_points_cap,
        min_points=settings.hn_default_min_points,
    ))


def _register_google_trends(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = GoogleTrendsClient(
        language=settings.gt_language,
        timezone_offset=settings.gt_timezone_offset,
        timeout=settings.gt_request_timeout,
    )
    registry.register(GoogleTrendsService(
        client=client,
        country=settings.gt_default_country,
    ))


def _register_reddit(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = RedditClient(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
        timeout=settings.reddit_request_timeout,
    )
    defaults = RedditFetchDefaults(
        subreddits=settings.reddit_default_subreddits,
        sort="hot",
        time_filter="day",
    )
    registry.register(RedditService(
        client=client,
        score_cap=settings.reddit_score_cap,
        defaults=defaults,
    ))


def _register_newsapi(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = NewsAPIClient(
        api_key=settings.newsapi_api_key,
        base_url=settings.newsapi_base_url,
        timeout=settings.newsapi_request_timeout,
    )
    registry.register(NewsAPIService(
        client=client,
        category=settings.newsapi_default_category,
        country=settings.newsapi_default_country,
    ))


def _register_arxiv(registry: TrendSourceRegistry, settings: Settings) -> None:
    client = ArxivClient(
        base_url=settings.arxiv_api_base_url,
        timeout=settings.arxiv_request_timeout,
    )
    registry.register(ArxivService(
        client=client,
        categories=settings.arxiv_default_categories,
    ))


def init_registry(settings: Settings) -> TrendSourceRegistry:
    """Construct all trend sources from settings."""
    registry = TrendSourceRegistry()
    _register_hackernews(registry, settings)
    _register_google_trends(registry, settings)
    _register_reddit(registry, settings)
    _register_newsapi(registry, settings)
    _register_arxiv(registry, settings)
    return registry
```

**App startup integration** (`src/api/main.py`):

```python
from src.services.trends import init_registry

def create_app(settings: Settings | None = None) -> FastAPI:
    ...
    app.state.trend_registry = init_registry(settings)
    ...
```

### 4.5 Service Adaptations

Each of the 5 services changes its `fetch_and_normalize` signature. Internal logic stays identical. Example using HackerNews:

**Before:**

```python
class HackerNewsService:
    def __init__(self, client: HackerNewsClient, points_cap: float) -> None:
        ...

    async def fetch_and_normalize(
        self, domain_keywords: list[str], max_results: int, min_points: int
    ) -> HNFetchResponse:
        ...
        return HNFetchResponse(
            topics=topics,
            total_fetched=total_fetched,
            total_after_filter=len(topics),
        )
```

**After:**

```python
class HackerNewsService:
    def __init__(
        self, client: HackerNewsClient, points_cap: float, min_points: int
    ) -> None:
        ...
        self._min_points = min_points

    @property
    def source_name(self) -> str:
        return "hackernews"

    async def fetch_and_normalize(
        self, config: TrendFetchConfig
    ) -> list[RawTopic]:
        ...  # uses config.domain_keywords, config.max_results, self._min_points
        return topics
```

**Config model for Reddit** (in `src/services/trends/reddit.py`):

Reddit's constructor would grow to 5 params (`client`, `score_cap`, `subreddits`, `sort`, `time_filter`), violating the max 3 params rule. Group the fetch defaults:

```python
class RedditFetchDefaults(BaseModel, frozen=True):
    """Reddit-specific fetch defaults set at init time."""
    subreddits: list[str]
    sort: str = "hot"
    time_filter: str = "day"
```

Constructor becomes: `RedditService(client, score_cap, defaults)` — 3 params.

**Changes per service:**

| Service | Params moving to constructor | Constructor params | Current return | New return |
|---------|------------------------------|--------------------|----------------|------------|
| `HackerNewsService` | `min_points` | `client`, `points_cap`, `min_points` (3) | `HNFetchResponse` | `list[RawTopic]` |
| `GoogleTrendsService` | `country` | `client`, `country` (2) | `GTFetchResponse` | `list[RawTopic]` |
| `RedditService` | `subreddits`, `sort`, `time_filter` | `client`, `score_cap`, `defaults` (3) | `RedditFetchResponse` | `list[RawTopic]` |
| `NewsAPIService` | `category`, `country` | `client`, `category`, `country` (3) | `NewsAPIFetchResponse` | `list[RawTopic]` |
| `ArxivService` | `categories` | `client`, `categories` (2) | `ArxivFetchResponse` | `list[RawTopic]` |

**Error class changes:** Each source's error class (`HackerNewsAPIError`, `RedditAPIError`, etc.) changes its base class from `Exception` to `TrendSourceError`. Constructor remains the same; only inheritance changes.

### 4.6 Router Refactoring

**File: `src/api/routers/trends.py`** (replaces current 277-line file, ~80 lines)

The handler is split into small functions to stay under the 20-line limit:

```python
import asyncio
import time

import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.errors import CognifyValidationError, ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.trends import (
    SourceResult,
    TrendFetchRequest,
    TrendFetchResponse,
)
from src.services.trends.protocol import TrendFetchConfig, TrendSourceError
from src.services.trends.registry import TrendSourceRegistry

logger = structlog.get_logger()

trends_router = APIRouter()


def _resolve_sources(
    registry: TrendSourceRegistry, requested: list[str] | None
) -> list[str]:
    """Resolve and validate requested source names."""
    sources = requested or registry.available_sources()
    unknown = set(sources) - set(registry.available_sources())
    if unknown:
        raise CognifyValidationError(
            message=f"Unknown sources: {sorted(unknown)}",
        )
    return sources


async def _run_source(
    source_name: str, registry: TrendSourceRegistry, config: TrendFetchConfig
) -> SourceResult:
    """Run a single source, capturing timing and errors."""
    source = registry.get(source_name)
    start = time.monotonic()
    try:
        topics = await source.fetch_and_normalize(config)
        elapsed = int((time.monotonic() - start) * 1000)
        return SourceResult(
            source_name=source_name,
            topics=topics,
            topic_count=len(topics),
            duration_ms=elapsed,
        )
    except TrendSourceError as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.error("trend_source_error", source=source_name, error=str(exc))
        return SourceResult(
            source_name=source_name,
            topics=[],
            topic_count=0,
            duration_ms=elapsed,
            error=str(exc),
        )


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/fetch",
    response_model=TrendFetchResponse,
    summary="Fetch trending topics from one or more sources",
)
async def fetch_trends(
    request: Request,
    body: TrendFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> TrendFetchResponse:
    registry = request.app.state.trend_registry
    source_names = _resolve_sources(registry, body.sources)
    config = TrendFetchConfig(
        domain_keywords=body.domain_keywords,
        max_results=body.max_results,
    )

    results = await asyncio.gather(
        *[_run_source(n, registry, config) for n in source_names]
    )
    source_results = {r.source_name: r for r in results}
    all_topics = [t for r in results for t in r.topics]

    if all(r.error is not None for r in results):
        raise ServiceUnavailableError(
            code="all_sources_unavailable",
            message="All trend sources are unavailable",
        )

    return TrendFetchResponse(
        topics=all_topics,
        sources_queried=list(source_names),
        source_results=source_results,
    )
```

**Key behaviors:**
- Individual source failures produce `SourceResult` with `error` field, not a 503
- Only if ALL sources fail does the endpoint return 503
- Unknown source names in the request return 422 validation error
- `sources: null` (or omitted) queries all registered sources

### 4.7 `SourceResult` Metrics

`topic_count` is set to `len(topics)` at the router level — a single clear field rather than two identical ones. The per-source internal metrics (e.g., `total_trending`, `subreddits_scanned`) are no longer exposed in the API response. This information is still available via structured logs inside each service.

If future needs require per-source internal metrics, the protocol can add an optional `metadata: dict[str, int]` return alongside the topic list. But for now, YAGNI.

### 4.8 API Breaking Change

This refactoring replaces 5 endpoints with 1:

| Old Endpoint | Replacement |
|-------------|-------------|
| `POST /api/v1/trends/hackernews/fetch` | `POST /api/v1/trends/fetch` with `sources: ["hackernews"]` |
| `POST /api/v1/trends/google/fetch` | `POST /api/v1/trends/fetch` with `sources: ["google_trends"]` |
| `POST /api/v1/trends/reddit/fetch` | `POST /api/v1/trends/fetch` with `sources: ["reddit"]` |
| `POST /api/v1/trends/newsapi/fetch` | `POST /api/v1/trends/fetch` with `sources: ["newsapi"]` |
| `POST /api/v1/trends/arxiv/fetch` | `POST /api/v1/trends/fetch` with `sources: ["arxiv"]` |

This is safe because no consumers (frontend or external) depend on these endpoints yet — DASH-002 (Topic Discovery Screen) is still in Backlog and will consume the new unified endpoint.

### 4.9 File Organization

```
src/services/trends/
  __init__.py              # init_registry(), public re-exports
  protocol.py              # TrendSource, TrendFetchConfig, TrendSourceError
  registry.py              # TrendSourceRegistry
  hackernews.py            # HackerNewsService (moved from src/services/)
  hackernews_client.py     # HackerNewsClient (moved as-is)
  google_trends.py         # GoogleTrendsService (moved)
  google_trends_client.py  # GoogleTrendsClient (moved as-is)
  reddit.py                # RedditService (moved, dedup extracted)
  reddit_client.py         # RedditClient (moved as-is)
  _dedup.py                # Reddit dedup helpers (extracted from reddit.py)
  newsapi.py               # NewsAPIService (moved)
  newsapi_client.py        # NewsAPIClient (moved as-is)
  arxiv.py                 # ArxivService (moved)
  arxiv_client.py          # ArxivClient (moved as-is)
```

**Stays in place:** `src/services/topic_ranking.py` — downstream consumer, not a source. Its imports of `RawTopic` from `src/api/schemas/topics` are unaffected.

**Client files move as-is** — no interface changes to transport layer. Only the error base class changes from `Exception` to `TrendSourceError`.

**Pre-existing file size violation:** `reddit.py` is 262 lines (limit: 200). During the move, extract the dedup helpers (`_is_crosspost_duplicate`, `_is_title_duplicate`, `_deduplicate_posts`) into a `_dedup.py` private module within `src/services/trends/`. This brings `reddit.py` well under 200 lines. The dedup logic is self-contained and used only by Reddit.

---

## 5. Import Changes

### 5.1 Source Code Imports

| File | Old Import | New Import |
|------|-----------|------------|
| `src/api/routers/trends.py` | 5 service + 5 client imports | `from src.services.trends.protocol import ...` |
| `src/api/main.py` | (no trend imports) | `from src.services.trends import init_registry` |
| `src/api/schemas/trends.py` | (self-contained) | Rewritten with new schemas |
| `src/services/topic_ranking.py` | No trend source imports | No changes |

### 5.2 Test Imports

All test files under `tests/unit/services/test_{source}.py` and `tests/unit/services/test_{source}_client.py` update their imports from `src.services.{source}` to `src.services.trends.{source}`.

Router endpoint tests in `tests/unit/api/test_trend_endpoints.py` and per-source endpoint tests are rewritten to test the single unified endpoint.

---

## 6. Testing Strategy

### 6.1 New Tests

**`tests/unit/services/trends/test_protocol.py`** (~20 lines):
- `TrendFetchConfig` validation (min_length, ge/le constraints)
- `TrendSourceError` formatting

**`tests/unit/services/trends/test_registry.py`** (~40 lines):
- Register and retrieve a source
- `get()` with unknown name raises `KeyError`
- `available_sources()` returns sorted names
- Duplicate registration overwrites

**`tests/unit/services/trends/test_init.py`** (~20 lines):
- `init_registry(settings)` returns registry with 5 sources
- Each source name is present

**`tests/unit/api/test_trend_endpoints.py`** (rewritten, ~80 lines):
- `POST /trends/fetch` with all sources (mocked registry)
- Subset selection: `sources: ["hackernews"]`
- Partial failure: one source errors, others succeed — 200 with error in `SourceResult`
- All sources fail — 503
- Unknown source name — 422

### 6.2 Migrated Tests

Existing service unit tests (`test_hackernews.py`, `test_reddit.py`, etc.) move to `tests/unit/services/trends/` and adapt:
- Import paths change
- `fetch_and_normalize` calls pass `TrendFetchConfig` instead of individual params
- Assertions check `list[RawTopic]` instead of source-specific response schemas
- All existing test cases preserved — same mocked data, same expected outputs

Existing client unit tests (`test_hackernews_client.py`, etc.) move to `tests/unit/services/trends/` with import path changes only — no logic changes.

Existing per-source endpoint tests (`test_arxiv_endpoints.py`, `test_google_trends_endpoints.py`, `test_newsapi_endpoints.py`) are deleted — their coverage is replaced by the unified endpoint tests.

Existing per-source schema tests (`test_trend_schemas.py`, `test_google_trends_schemas.py`, `test_newsapi_schemas.py`) are deleted — they test the old `HNFetchRequest`, `GTFetchResponse`, etc. schemas that are being removed. Replacement coverage for the new `TrendFetchRequest`, `SourceResult`, and `TrendFetchResponse` schemas goes in `tests/unit/services/trends/test_protocol.py` (for `TrendFetchConfig`) and `tests/unit/api/test_trend_schemas.py` (rewritten for the new API schemas).

### 6.3 Unchanged Tests

- `test_topic_ranking.py` — consumes `RawTopic`, no trend source imports
- `test_topic_schemas.py` — `RawTopic` schema is unchanged
- All non-trend tests — zero impact

---

## 7. App Startup Change

In `src/api/main.py`, `create_app()` adds one line:

```python
app.state.trend_registry = init_registry(settings)
```

Test injection changes from setting `app.state.hn_client` etc. to setting `app.state.trend_registry` with a pre-built registry containing mock sources.

---

## 8. Migration Summary

| What | Action | Risk |
|------|--------|------|
| 10 source files (5 clients + 5 services) | Move to `src/services/trends/` | Low — file moves + import updates |
| `reddit.py` (262 lines) | Extract dedup helpers into `_dedup.py` | Low — pure extraction |
| 5 service signatures | Adapt `fetch_and_normalize` to `TrendFetchConfig` | Low — mechanical change |
| 5 error classes | Change base from `Exception` to `TrendSourceError` | Low — additive |
| 10 API schemas | Delete, replace with 3 unified schemas | Low — old schemas unused after router rewrite |
| Router (277 lines) | Rewrite to single endpoint (~80 lines) | Medium — new endpoint, new test coverage |
| 5 API endpoints | Replace with 1 unified endpoint (breaking, no consumers) | Low — no current consumers |
| ~15 test files | Move + adapt imports/assertions | Low — mechanical |
| 6 per-source test files | Delete (3 endpoint + 3 schema), replaced by unified tests | Low — coverage replaced |

**Net effect**: ~210 lines of router boilerplate eliminated. ~50 lines of new protocol/registry code added. All 683 existing tests pass after migration (with adapted imports and signatures).

---

## 9. Acceptance Criteria Mapping

| Acceptance Criterion | Design Section |
|---------------------|----------------|
| `TrendSource` protocol with `source_name` and `fetch_and_normalize` | 4.1 |
| `TrendFetchConfig` Pydantic model for unified fetch parameters | 4.1 |
| Source registry that discovers and manages active trend sources | 4.3, 4.4 |
| Single registry-driven router endpoint replaces 5 copy-paste handlers | 4.6 |
| All 5 existing sources implement the protocol | 4.5 |
| Existing tests continue to pass (no behavioral changes) | 6.2, 6.3 |
