# ARCH-002: TrendSource Protocol & Registry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formalize a `TrendSource` protocol, create a source registry, and collapse 5 copy-paste router handlers into one registry-driven endpoint.

**Architecture:** Define `TrendSource` protocol + `TrendFetchConfig` in a new `src/services/trends/` package. Move all 10 existing source files there, adapt service signatures, then rewrite the router to use a single registry-driven endpoint. TDD throughout.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-20-arch-002-trendsource-protocol-registry-design.md`

---

## File Impact Summary

### New Files
| File | Purpose |
|------|---------|
| `src/services/trends/__init__.py` | `init_registry()` + per-source factory functions |
| `src/services/trends/protocol.py` | `TrendSource` protocol, `TrendFetchConfig`, `TrendSourceError` |
| `src/services/trends/registry.py` | `TrendSourceRegistry` class |
| `src/services/trends/_dedup.py` | Reddit dedup helpers (extracted from `reddit.py`) |
| `tests/unit/services/trends/__init__.py` | Package init |
| `tests/unit/services/trends/conftest.py` | Mock clients (moved from `tests/unit/services/conftest.py`) |
| `tests/unit/services/trends/test_protocol.py` | Tests for protocol, config, error |
| `tests/unit/services/trends/test_registry.py` | Tests for registry |
| `tests/unit/services/trends/test_init.py` | Tests for `init_registry()` |

### Moved Files (src/services/ → src/services/trends/)
| Old Path | New Path | Changes |
|----------|----------|---------|
| `src/services/hackernews.py` | `src/services/trends/hackernews.py` | Adapt signature + imports |
| `src/services/hackernews_client.py` | `src/services/trends/hackernews_client.py` | Error base class change |
| `src/services/google_trends.py` | `src/services/trends/google_trends.py` | Adapt signature + imports |
| `src/services/google_trends_client.py` | `src/services/trends/google_trends_client.py` | Error base class change |
| `src/services/reddit.py` | `src/services/trends/reddit.py` | Adapt signature + extract dedup |
| `src/services/reddit_client.py` | `src/services/trends/reddit_client.py` | Error base class change |
| `src/services/newsapi.py` | `src/services/trends/newsapi.py` | Adapt signature + imports |
| `src/services/newsapi_client.py` | `src/services/trends/newsapi_client.py` | Error base class change |
| `src/services/arxiv.py` | `src/services/trends/arxiv.py` | Adapt signature + imports |
| `src/services/arxiv_client.py` | `src/services/trends/arxiv_client.py` | Error base class change |

### Moved Test Files (tests/unit/services/ → tests/unit/services/trends/)
| Old Path | New Path | Changes |
|----------|----------|---------|
| `tests/unit/services/test_hackernews.py` | `tests/unit/services/trends/test_hackernews.py` | Adapt imports + assertions |
| `tests/unit/services/test_hackernews_client.py` | `tests/unit/services/trends/test_hackernews_client.py` | Adapt imports |
| `tests/unit/services/test_google_trends.py` | `tests/unit/services/trends/test_google_trends.py` | Adapt imports + assertions |
| `tests/unit/services/test_google_trends_client.py` | `tests/unit/services/trends/test_google_trends_client.py` | Adapt imports |
| `tests/unit/services/test_reddit.py` | `tests/unit/services/trends/test_reddit.py` | Adapt imports + assertions |
| `tests/unit/services/test_reddit_client.py` | `tests/unit/services/trends/test_reddit_client.py` | Adapt imports |
| `tests/unit/services/test_newsapi.py` | `tests/unit/services/trends/test_newsapi.py` | Adapt imports + assertions |
| `tests/unit/services/test_newsapi_client.py` | `tests/unit/services/trends/test_newsapi_client.py` | Adapt imports |
| `tests/unit/services/test_arxiv.py` | `tests/unit/services/trends/test_arxiv.py` | Adapt imports + assertions |
| `tests/unit/services/test_arxiv_client.py` | `tests/unit/services/trends/test_arxiv_client.py` | Adapt imports |

### Modified Files
| File | Changes |
|------|---------|
| `src/api/schemas/trends.py` | Replace 10 schemas with 3 unified ones |
| `src/api/routers/trends.py` | Replace 277-line boilerplate with ~80-line registry-driven handler |
| `src/api/main.py` | Add `init_registry()` call at startup |
| `tests/unit/services/conftest.py` | Remove mock clients (moved to trends subpackage) |
| `tests/unit/api/conftest.py` | Update app fixture to use registry |

### Deleted Test Files
| File | Reason |
|------|--------|
| `tests/unit/api/test_arxiv_endpoints.py` | Replaced by unified endpoint tests |
| `tests/unit/api/test_google_trends_endpoints.py` | Replaced by unified endpoint tests |
| `tests/unit/api/test_newsapi_endpoints.py` | Replaced by unified endpoint tests |
| `tests/unit/api/test_trend_schemas.py` | Old schemas deleted |
| `tests/unit/api/test_google_trends_schemas.py` | Old schemas deleted |
| `tests/unit/api/test_newsapi_schemas.py` | Old schemas deleted |
| `tests/unit/api/test_trend_endpoints.py` | Rewritten (counts as delete + create) |

---

## Task 1: Protocol & Core Models (TDD)

**Files:**
- Create: `src/services/trends/__init__.py` (empty for now)
- Create: `src/services/trends/protocol.py`
- Create: `tests/unit/services/trends/__init__.py`
- Create: `tests/unit/services/trends/test_protocol.py`

- [ ] **Step 1: Create package structure**

Create the `src/services/trends/` and `tests/unit/services/trends/` packages with empty `__init__.py` files.

- [ ] **Step 2: Write failing tests for TrendFetchConfig**

```python
# tests/unit/services/trends/test_protocol.py
import pytest
from pydantic import ValidationError

from src.services.trends.protocol import TrendFetchConfig, TrendSourceError


class TestTrendFetchConfig:
    def test_valid_config(self) -> None:
        config = TrendFetchConfig(domain_keywords=["ai", "ml"])
        assert config.domain_keywords == ["ai", "ml"]
        assert config.max_results == 30

    def test_custom_max_results(self) -> None:
        config = TrendFetchConfig(domain_keywords=["ai"], max_results=10)
        assert config.max_results == 10

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrendFetchConfig(domain_keywords=[])

    def test_max_results_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            TrendFetchConfig(domain_keywords=["ai"], max_results=0)

    def test_max_results_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            TrendFetchConfig(domain_keywords=["ai"], max_results=101)


class TestTrendSourceError:
    def test_format(self) -> None:
        err = TrendSourceError("hackernews", "API timeout")
        assert str(err) == "[hackernews] API timeout"
        assert err.source_name == "hackernews"

    def test_is_exception(self) -> None:
        err = TrendSourceError("reddit", "Rate limited")
        assert isinstance(err, Exception)
```

- [ ] **Step 3: Run tests — expect FAIL (import error)**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_protocol.py -v`
Expected: `ModuleNotFoundError: No module named 'src.services.trends.protocol'`

- [ ] **Step 4: Implement protocol.py**

```python
# src/services/trends/protocol.py
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
        self, config: TrendFetchConfig,
    ) -> list[RawTopic]: ...
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_protocol.py -v`
Expected: All 7 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/services/trends/__init__.py src/services/trends/protocol.py tests/unit/services/trends/__init__.py tests/unit/services/trends/test_protocol.py
git commit -m "feat(arch-002): add TrendSource protocol, TrendFetchConfig, TrendSourceError"
```

---

## Task 2: Registry (TDD)

**Files:**
- Create: `src/services/trends/registry.py`
- Create: `tests/unit/services/trends/test_registry.py`

- [ ] **Step 1: Write failing tests for TrendSourceRegistry**

```python
# tests/unit/services/trends/test_registry.py
import pytest

from src.api.schemas.topics import RawTopic
from src.services.trends.protocol import TrendFetchConfig
from src.services.trends.registry import TrendSourceRegistry


class _FakeSource:
    """Minimal TrendSource implementation for testing."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def source_name(self) -> str:
        return self._name

    async def fetch_and_normalize(
        self, config: TrendFetchConfig,
    ) -> list[RawTopic]:
        return []


class TestTrendSourceRegistry:
    def test_register_and_get(self) -> None:
        registry = TrendSourceRegistry()
        source = _FakeSource("test")
        registry.register(source)
        assert registry.get("test") is source

    def test_get_unknown_raises(self) -> None:
        registry = TrendSourceRegistry()
        with pytest.raises(KeyError):
            registry.get("unknown")

    def test_available_sources_sorted(self) -> None:
        registry = TrendSourceRegistry()
        registry.register(_FakeSource("reddit"))
        registry.register(_FakeSource("arxiv"))
        registry.register(_FakeSource("hackernews"))
        assert registry.available_sources() == [
            "arxiv", "hackernews", "reddit",
        ]

    def test_get_all_returns_copy(self) -> None:
        registry = TrendSourceRegistry()
        source = _FakeSource("test")
        registry.register(source)
        all_sources = registry.get_all()
        assert all_sources == {"test": source}
        all_sources["injected"] = _FakeSource("injected")
        assert "injected" not in registry.get_all()

    def test_duplicate_overwrites(self) -> None:
        registry = TrendSourceRegistry()
        first = _FakeSource("test")
        second = _FakeSource("test")
        registry.register(first)
        registry.register(second)
        assert registry.get("test") is second

    def test_empty_registry(self) -> None:
        registry = TrendSourceRegistry()
        assert registry.available_sources() == []
        assert registry.get_all() == {}
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_registry.py -v`
Expected: `ModuleNotFoundError: No module named 'src.services.trends.registry'`

- [ ] **Step 3: Implement registry.py**

```python
# src/services/trends/registry.py
from src.services.trends.protocol import TrendSource


class TrendSourceRegistry:
    """Manages registered trend source instances."""

    def __init__(self) -> None:
        self._sources: dict[str, TrendSource] = {}

    def register(self, source: TrendSource) -> None:
        """Register a source. Overwrites if name exists."""
        self._sources[source.source_name] = source

    def get(self, name: str) -> TrendSource:
        """Get source by name. Raises KeyError if not found."""
        return self._sources[name]

    def get_all(self) -> dict[str, TrendSource]:
        """Return copy of all registered sources."""
        return dict(self._sources)

    def available_sources(self) -> list[str]:
        """Return sorted list of registered source names."""
        return sorted(self._sources.keys())
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_registry.py -v`
Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/services/trends/registry.py tests/unit/services/trends/test_registry.py
git commit -m "feat(arch-002): add TrendSourceRegistry"
```

---

## Task 3: Move Client Files & Update Error Base Classes

This task moves all 5 client files to `src/services/trends/` and changes their error base class from `Exception` to `TrendSourceError`. Client tests move with import updates only.

**Files:**
- Move: `src/services/hackernews_client.py` → `src/services/trends/hackernews_client.py`
- Move: `src/services/google_trends_client.py` → `src/services/trends/google_trends_client.py`
- Move: `src/services/reddit_client.py` → `src/services/trends/reddit_client.py`
- Move: `src/services/newsapi_client.py` → `src/services/trends/newsapi_client.py`
- Move: `src/services/arxiv_client.py` → `src/services/trends/arxiv_client.py`
- Move: `tests/unit/services/test_hackernews_client.py` → `tests/unit/services/trends/test_hackernews_client.py`
- Move: `tests/unit/services/test_google_trends_client.py` → `tests/unit/services/trends/test_google_trends_client.py`
- Move: `tests/unit/services/test_reddit_client.py` → `tests/unit/services/trends/test_reddit_client.py`
- Move: `tests/unit/services/test_newsapi_client.py` → `tests/unit/services/trends/test_newsapi_client.py`
- Move: `tests/unit/services/test_arxiv_client.py` → `tests/unit/services/trends/test_arxiv_client.py`

- [ ] **Step 1: Move all 5 client files with `git mv`**

```bash
cd D:/Workbench/github/cognify-arch-002
git mv src/services/hackernews_client.py src/services/trends/hackernews_client.py
git mv src/services/google_trends_client.py src/services/trends/google_trends_client.py
git mv src/services/reddit_client.py src/services/trends/reddit_client.py
git mv src/services/newsapi_client.py src/services/trends/newsapi_client.py
git mv src/services/arxiv_client.py src/services/trends/arxiv_client.py
```

- [ ] **Step 2: Update error base classes in each client**

In each `*_client.py`, change the error class to inherit from `TrendSourceError` instead of `Exception`. The constructor needs to pass `source_name` to the parent. Pattern for each:

**hackernews_client.py** — Change:
```python
class HackerNewsAPIError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
```
To:
```python
from src.services.trends.protocol import TrendSourceError

class HackerNewsAPIError(TrendSourceError):
    def __init__(self, message: str) -> None:
        super().__init__("hackernews", message)
```

Apply the same pattern to all 5 clients:
- `GoogleTrendsAPIError` → `super().__init__("google_trends", message)`
- `RedditAPIError` → `super().__init__("reddit", message)`
- `NewsAPIError` → `super().__init__("newsapi", message)`
- `ArxivAPIError` → `super().__init__("arxiv", message)`

- [ ] **Step 3: Move all 5 client test files with `git mv`**

```bash
git mv tests/unit/services/test_hackernews_client.py tests/unit/services/trends/test_hackernews_client.py
git mv tests/unit/services/test_google_trends_client.py tests/unit/services/trends/test_google_trends_client.py
git mv tests/unit/services/test_reddit_client.py tests/unit/services/trends/test_reddit_client.py
git mv tests/unit/services/test_newsapi_client.py tests/unit/services/trends/test_newsapi_client.py
git mv tests/unit/services/test_arxiv_client.py tests/unit/services/trends/test_arxiv_client.py
```

- [ ] **Step 4: Update imports in moved client test files**

In each test file, update the import from `src.services.X_client` to `src.services.trends.X_client`. For example in `test_hackernews_client.py`:
```python
# Old: from src.services.hackernews_client import ...
# New:
from src.services.trends.hackernews_client import ...
```

- [ ] **Step 5: Update mock client imports in `tests/unit/services/conftest.py`**

The mock clients in `tests/unit/services/conftest.py` import from the old paths (`from src.services.hackernews_client import ...`). These will break now that the client files have moved. Update all 5 client imports to the new paths:

```python
# Old: from src.services.hackernews_client import HackerNewsClient, HNStoryResponse
# New:
from src.services.trends.hackernews_client import HackerNewsClient, HNStoryResponse
# ... same pattern for all 5 clients
```

This keeps the mock clients importable from the original conftest location, which is needed by service tests not yet moved (Reddit, NewsAPI in Tasks 5-6).

- [ ] **Step 6: Run client tests to verify moves**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_*_client.py -v`
Expected: All client tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(arch-002): move client files to trends package, update error base classes"
```

---

## Task 4: Move & Adapt Service Files (HackerNews, Google Trends, arXiv)

These 3 services have simple constructor adaptations (max 3 params already).

**Files:**
- Move + adapt: `src/services/hackernews.py` → `src/services/trends/hackernews.py`
- Move + adapt: `src/services/google_trends.py` → `src/services/trends/google_trends.py`
- Move + adapt: `src/services/arxiv.py` → `src/services/trends/arxiv.py`
- Move + adapt: `tests/unit/services/test_hackernews.py` → `tests/unit/services/trends/test_hackernews.py`
- Move + adapt: `tests/unit/services/test_google_trends.py` → `tests/unit/services/trends/test_google_trends.py`
- Move + adapt: `tests/unit/services/test_arxiv.py` → `tests/unit/services/trends/test_arxiv.py`

- [ ] **Step 1: Move 3 service files with `git mv`**

```bash
cd D:/Workbench/github/cognify-arch-002
git mv src/services/hackernews.py src/services/trends/hackernews.py
git mv src/services/google_trends.py src/services/trends/google_trends.py
git mv src/services/arxiv.py src/services/trends/arxiv.py
```

- [ ] **Step 2: Adapt HackerNewsService**

In `src/services/trends/hackernews.py`:

1. Update imports: `from src.services.hackernews_client` → `from src.services.trends.hackernews_client`
2. Remove `from src.api.schemas.trends import HNFetchResponse`
3. Add `from src.services.trends.protocol import TrendFetchConfig`
4. Add `min_points` to constructor (3rd param), store as `self._min_points`
5. Add `source_name` property returning `"hackernews"`
6. Change `fetch_and_normalize` signature: accept `config: TrendFetchConfig`, return `list[RawTopic]`
7. Inside: use `config.domain_keywords`, `config.max_results`, `self._min_points`
8. Return `topics` list instead of `HNFetchResponse(...)`

- [ ] **Step 3: Adapt GoogleTrendsService**

In `src/services/trends/google_trends.py`:

1. Update imports similarly
2. Add `country` to constructor (2nd param), store as `self._country`
3. Add `source_name` property returning `"google_trends"`
4. Change `fetch_and_normalize` signature: accept `config: TrendFetchConfig`, return `list[RawTopic]`
5. Inside: use `config.domain_keywords`, `config.max_results`, `self._country`
6. Return `topics` list instead of `GTFetchResponse(...)`

- [ ] **Step 4: Adapt ArxivService**

In `src/services/trends/arxiv.py`:

1. Update imports similarly
2. Add `categories` to constructor (2nd param), store as `self._categories`
3. Add `source_name` property returning `"arxiv"`
4. Change `fetch_and_normalize` signature: accept `config: TrendFetchConfig`, return `list[RawTopic]`
5. Inside: use `config.domain_keywords`, `config.max_results`, `self._categories`
6. Return `topics` list instead of `ArxivFetchResponse(...)`

- [ ] **Step 5: Move 3 test files with `git mv`**

```bash
git mv tests/unit/services/test_hackernews.py tests/unit/services/trends/test_hackernews.py
git mv tests/unit/services/test_google_trends.py tests/unit/services/trends/test_google_trends.py
git mv tests/unit/services/test_arxiv.py tests/unit/services/trends/test_arxiv.py
```

- [ ] **Step 6: Adapt test files**

In each test file:
1. Update imports from `src.services.X` → `src.services.trends.X`
2. Update imports from `tests.unit.services.conftest` → `tests.unit.services.trends.conftest`
3. Update `HackerNewsService(client=..., points_cap=...)` → add `min_points=10`
4. Update `fetch_and_normalize(domain_keywords=..., max_results=..., min_points=...)` → `fetch_and_normalize(TrendFetchConfig(domain_keywords=..., max_results=...))`
5. Change assertions from `result.topics` / `result.total_fetched` → `result` is `list[RawTopic]`, check `len(result)` directly
6. Apply same pattern for Google Trends and arXiv tests

- [ ] **Step 7: Create `tests/unit/services/trends/conftest.py`**

**Copy** (not move) the 5 `Mock*Client` classes from `tests/unit/services/conftest.py` into `tests/unit/services/trends/conftest.py`. The imports in the new file should use the new paths (`from src.services.trends.X_client import ...`).

Keep the originals in `tests/unit/services/conftest.py` for now — Reddit and NewsAPI tests still import from there. They'll be cleaned up in Task 7 after all services are moved.

- [ ] **Step 8: Run moved tests**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_hackernews.py tests/unit/services/trends/test_google_trends.py tests/unit/services/trends/test_arxiv.py -v`
Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(arch-002): move and adapt HN, GT, arXiv services to trends package"
```

---

## Task 5: Move & Adapt Reddit Service (with dedup extraction)

Reddit is the most complex service (262 lines) and needs dedup helper extraction.

**Files:**
- Move + adapt: `src/services/reddit.py` → `src/services/trends/reddit.py`
- Create: `src/services/trends/_dedup.py`
- Move + adapt: `tests/unit/services/test_reddit.py` → `tests/unit/services/trends/test_reddit.py`

- [ ] **Step 1: Move reddit files with `git mv`**

```bash
cd D:/Workbench/github/cognify-arch-002
git mv src/services/reddit.py src/services/trends/reddit.py
git mv tests/unit/services/test_reddit.py tests/unit/services/trends/test_reddit.py
```

- [ ] **Step 2: Extract dedup helpers into `_dedup.py`**

Create `src/services/trends/_dedup.py` by extracting `RedditService.deduplicate_crossposts` (lines 55-116 of `src/services/trends/reddit.py`, which was just moved). Copy the method body into a module-level function — remove `@staticmethod` decorator but keep everything else identical (it already has no `self` references). Move the `SequenceMatcher` import there too.

```python
# src/services/trends/_dedup.py
from difflib import SequenceMatcher

from src.services.trends.reddit_client import RedditPostResponse


def deduplicate_crossposts(
    posts: list[RedditPostResponse],
) -> tuple[list[RedditPostResponse], int]:
    """Two-pass dedup: crosspost_parent IDs then fuzzy title match.
    Returns (deduped_posts, removed_count)."""
    # Copy lines 60-116 from RedditService.deduplicate_crossposts
    # (the full method body — no changes needed)
```

After extraction, verify `wc -l src/services/trends/reddit.py` is under 200 lines.

- [ ] **Step 3: Adapt RedditService**

In `src/services/trends/reddit.py`:

1. Update imports: `from src.services.reddit_client` → `from src.services.trends.reddit_client`
2. Remove `from src.api.schemas.trends import RedditFetchResponse`
3. Add `from src.services.trends.protocol import TrendFetchConfig`
4. Add `RedditFetchDefaults` frozen Pydantic model (3 fields: `subreddits`, `sort`, `time_filter`)
5. Change constructor to `__init__(self, client, score_cap, defaults)` (3 params)
6. Add `source_name` property returning `"reddit"`
7. Remove `deduplicate_crossposts` method, import from `_dedup` instead
8. Remove `SequenceMatcher` import (moved to `_dedup.py`)
9. Change `fetch_and_normalize` signature: accept `config: TrendFetchConfig`, return `list[RawTopic]`
10. Inside: use `config.domain_keywords`, `config.max_results`, `self._defaults.subreddits`, etc.
11. Return `topics` list instead of `RedditFetchResponse(...)`

Verify `reddit.py` is now well under 200 lines.

- [ ] **Step 4: Adapt test file**

In `tests/unit/services/trends/test_reddit.py`:
1. Update imports
2. Update `RedditService(client=..., score_cap=...)` → `RedditService(client=..., score_cap=..., defaults=RedditFetchDefaults(subreddits=...))`
3. Update `fetch_and_normalize` calls to use `TrendFetchConfig`
4. Change assertions from `result.topics`/`result.total_*` → `result` is `list[RawTopic]`
5. Update `deduplicate_crossposts` test calls from `RedditService.deduplicate_crossposts(...)` → `from src.services.trends._dedup import deduplicate_crossposts`

- [ ] **Step 5: Run tests**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_reddit.py -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(arch-002): move Reddit service, extract dedup helpers"
```

---

## Task 6: Move & Adapt NewsAPI Service

**Files:**
- Move + adapt: `src/services/newsapi.py` → `src/services/trends/newsapi.py`
- Move + adapt: `tests/unit/services/test_newsapi.py` → `tests/unit/services/trends/test_newsapi.py`

- [ ] **Step 1: Move files**

```bash
cd D:/Workbench/github/cognify-arch-002
git mv src/services/newsapi.py src/services/trends/newsapi.py
git mv tests/unit/services/test_newsapi.py tests/unit/services/trends/test_newsapi.py
```

- [ ] **Step 2: Adapt NewsAPIService**

In `src/services/trends/newsapi.py`:

1. Update imports similarly
2. Add `category` and `country` to constructor (3 params total: `client`, `category`, `country`)
3. Add `source_name` property returning `"newsapi"`
4. Change `fetch_and_normalize` signature: accept `config: TrendFetchConfig`, return `list[RawTopic]`
5. Inside: use `config.domain_keywords`, `config.max_results`, `self._category`, `self._country`
6. Return `topics` list instead of `NewsAPIFetchResponse(...)`

- [ ] **Step 3: Adapt test file**

Update imports, constructor calls, `fetch_and_normalize` calls (use `TrendFetchConfig`), and assertions.

- [ ] **Step 4: Run tests**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_newsapi.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(arch-002): move and adapt NewsAPI service to trends package"
```

---

## Task 7: Update conftest & Run Full Service Test Suite

Clean up the original `tests/unit/services/conftest.py` and verify all moved tests pass together.

**Files:**
- Modify: `tests/unit/services/conftest.py` (remove moved mock clients)

- [ ] **Step 1: Update original conftest.py**

Remove `MockHackerNewsClient`, `MockRedditClient`, `MockGoogleTrendsClient`, `MockNewsAPIClient`, `MockArxivClient` from `tests/unit/services/conftest.py`. Keep only `MockEmbeddingService` (and its imports). Remove the now-unused imports of client types.

- [ ] **Step 2: Run ALL service tests (old location + new location)**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/ -v`
Expected: All tests pass. No import errors from leftover references.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/services/conftest.py
git commit -m "refactor(arch-002): clean up original conftest after mock client migration"
```

---

## Task 8: Unified API Schemas (TDD)

**Files:**
- Rewrite: `src/api/schemas/trends.py`
- Rewrite: `tests/unit/api/test_trend_schemas.py`
- Delete: `tests/unit/api/test_google_trends_schemas.py`
- Delete: `tests/unit/api/test_newsapi_schemas.py`

- [ ] **Step 1: Write tests for new schemas**

```python
# tests/unit/api/test_trend_schemas.py (rewritten)
import pytest
from pydantic import ValidationError

from src.api.schemas.trends import (
    SourceResult,
    TrendFetchRequest,
    TrendFetchResponse,
)


class TestTrendFetchRequest:
    def test_defaults(self) -> None:
        req = TrendFetchRequest(domain_keywords=["ai"])
        assert req.max_results == 30
        assert req.sources is None

    def test_with_sources(self) -> None:
        req = TrendFetchRequest(
            domain_keywords=["ai"],
            sources=["hackernews", "reddit"],
        )
        assert req.sources == ["hackernews", "reddit"]

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrendFetchRequest(domain_keywords=[])


class TestSourceResult:
    def test_success_result(self) -> None:
        result = SourceResult(
            source_name="hackernews",
            topics=[],
            topic_count=0,
            duration_ms=42,
        )
        assert result.error is None

    def test_error_result(self) -> None:
        result = SourceResult(
            source_name="reddit",
            topics=[],
            topic_count=0,
            duration_ms=100,
            error="API timeout",
        )
        assert result.error == "API timeout"


class TestTrendFetchResponse:
    def test_combined_response(self) -> None:
        resp = TrendFetchResponse(
            topics=[],
            sources_queried=["hackernews"],
            source_results={},
        )
        assert resp.sources_queried == ["hackernews"]
```

- [ ] **Step 2: Run tests — expect FAIL (old schemas still in file)**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/api/test_trend_schemas.py -v`
Expected: FAIL — `ImportError` because old file has different exports.

- [ ] **Step 3: Rewrite `src/api/schemas/trends.py`**

Replace the entire file with the 3 unified schemas from the spec (Section 4.2): `TrendFetchRequest`, `SourceResult`, `TrendFetchResponse`.

- [ ] **Step 4: Delete old per-source schema test files**

```bash
cd D:/Workbench/github/cognify-arch-002
git rm tests/unit/api/test_google_trends_schemas.py
git rm tests/unit/api/test_newsapi_schemas.py
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/api/test_trend_schemas.py -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/api/schemas/trends.py tests/unit/api/test_trend_schemas.py
git add -A  # catches deleted files
git commit -m "refactor(arch-002): replace 10 per-source API schemas with 3 unified schemas"
```

---

## Task 9: Registry Initialization & App Startup (TDD)

**Files:**
- Modify: `src/services/trends/__init__.py`
- Create: `tests/unit/services/trends/test_init.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: Write failing tests for `init_registry`**

```python
# tests/unit/services/trends/test_init.py
from src.config.settings import Settings
from src.services.trends import init_registry


class TestInitRegistry:
    def test_registers_all_five_sources(self) -> None:
        settings = Settings()
        registry = init_registry(settings)
        names = registry.available_sources()
        assert len(names) == 5
        assert "arxiv" in names
        assert "google_trends" in names
        assert "hackernews" in names
        assert "newsapi" in names
        assert "reddit" in names

    def test_each_source_is_retrievable(self) -> None:
        settings = Settings()
        registry = init_registry(settings)
        for name in registry.available_sources():
            source = registry.get(name)
            assert source.source_name == name
```

**Note:** These tests call `Settings()` with defaults and construct real HTTP client objects via `init_registry`. This is safe — all client constructors are inert at construction time (no network calls until `fetch_*` methods are invoked). Default Settings values (empty API keys, placeholder URLs) work fine for construction.

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_init.py -v`
Expected: FAIL — `init_registry` not yet defined.

- [ ] **Step 3: Implement `init_registry` in `__init__.py`**

Write the per-source factory functions (`_register_hackernews`, `_register_google_trends`, `_register_reddit`, `_register_newsapi`, `_register_arxiv`) and the top-level `init_registry(settings)` function as specified in Section 4.4 of the spec. Each factory is under 20 lines.

Also add public re-exports:
```python
from src.services.trends.protocol import (
    TrendFetchConfig,
    TrendSource,
    TrendSourceError,
)
from src.services.trends.registry import TrendSourceRegistry

__all__ = [
    "TrendFetchConfig",
    "TrendSource",
    "TrendSourceError",
    "TrendSourceRegistry",
    "init_registry",
]
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/services/trends/test_init.py -v`
Expected: All 2 tests pass.

- [ ] **Step 5: Add `init_registry()` call to `src/api/main.py`**

Add `from src.services.trends import init_registry` at the top. In `create_app()`, after `app.state.user_repo = ...`, add:

```python
app.state.trend_registry = init_registry(settings)
```

- [ ] **Step 6: Run full test suite to verify startup**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest --tb=short -q`
Expected: Tests pass (some old endpoint tests may fail due to schema changes — that's expected, fixed in Task 10).

- [ ] **Step 7: Commit**

```bash
git add src/services/trends/__init__.py tests/unit/services/trends/test_init.py src/api/main.py
git commit -m "feat(arch-002): add init_registry and integrate with app startup"
```

---

## Task 10: Router Refactoring & Unified Endpoint (TDD)

**Files:**
- Rewrite: `src/api/routers/trends.py`
- Rewrite: `tests/unit/api/test_trend_endpoints.py`
- Delete: `tests/unit/api/test_arxiv_endpoints.py`
- Delete: `tests/unit/api/test_google_trends_endpoints.py`
- Delete: `tests/unit/api/test_newsapi_endpoints.py`
- Modify: `tests/unit/api/conftest.py` (update app fixture)

- [ ] **Step 1: Write tests for the unified endpoint**

Read `tests/unit/api/conftest.py` to understand the existing test app fixture pattern (how `app.state` is set up, how mock clients are injected). Then write `tests/unit/api/test_trend_endpoints.py` with tests for:

1. **All sources success** — `POST /api/v1/trends/fetch` with `domain_keywords`, no `sources` field → 200, response has all source results
2. **Single source selection** — `sources: ["hackernews"]` → 200, only hackernews in results
3. **Partial failure** — one source raises `TrendSourceError`, others succeed → 200, failed source has `error` in `SourceResult`
4. **All fail** — all sources raise → 503
5. **Unknown source** — `sources: ["nonexistent"]` → 422
6. **No token** — request without auth header → 401
7. **Viewer role forbidden** — viewer token → 403
8. **Editor role allowed** — editor token → 200
9. **Admin role allowed** — admin token → 200

Use a mock registry with `_FakeSource` implementations (similar to Task 2 tests). Inject via `app.state.trend_registry`. Use the existing auth test patterns from the current `test_trend_endpoints.py` for tests 6-9.

- [ ] **Step 2: Update `tests/unit/api/conftest.py`**

Update the test app fixture to set `app.state.trend_registry` with a mock registry instead of setting individual `app.state.hn_client`, `app.state.gt_client`, etc.

- [ ] **Step 3: Run tests — expect FAIL (old router)**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/api/test_trend_endpoints.py -v`
Expected: FAIL — old router doesn't have `/trends/fetch` endpoint.

- [ ] **Step 4: Rewrite `src/api/routers/trends.py`**

Replace the entire 277-line file with the ~80-line implementation from spec Section 4.6. Three module-level functions: `_resolve_sources`, `_run_source`, `fetch_trends`.

- [ ] **Step 5: Delete old per-source endpoint test files**

```bash
cd D:/Workbench/github/cognify-arch-002
git rm tests/unit/api/test_arxiv_endpoints.py
git rm tests/unit/api/test_google_trends_endpoints.py
git rm tests/unit/api/test_newsapi_endpoints.py
```

- [ ] **Step 6: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest tests/unit/api/test_trend_endpoints.py -v`
Expected: All 5+ tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(arch-002): replace 5 router handlers with single registry-driven endpoint"
```

---

## Task 11: Full Test Suite Verification & Lint

- [ ] **Step 1: Run full test suite**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest --tb=short -q`
Expected: All tests pass (count should be close to 683, adjusted for deleted/added tests).

- [ ] **Step 2: Run linters**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
Expected: Clean. Fix any issues.

- [ ] **Step 3: Run mypy**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run mypy src/`
Expected: Clean (no `Any` types, all protocols satisfied).

- [ ] **Step 4: Verify file sizes**

Check that no file exceeds 200 lines:
```bash
wc -l src/services/trends/*.py src/api/routers/trends.py src/api/schemas/trends.py
```
Expected: All under 200.

- [ ] **Step 5: Fix any issues found, re-run all checks**

- [ ] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "chore(arch-002): fix lint and type issues"
```

---

## Task 12: Cleanup & Final Verification

- [ ] **Step 1: Verify no stale imports reference old paths**

```bash
cd D:/Workbench/github/cognify-arch-002
grep -r "from src.services.hackernews" src/ tests/ --include="*.py" | grep -v "src.services.trends"
grep -r "from src.services.reddit" src/ tests/ --include="*.py" | grep -v "src.services.trends"
grep -r "from src.services.google_trends" src/ tests/ --include="*.py" | grep -v "src.services.trends"
grep -r "from src.services.newsapi" src/ tests/ --include="*.py" | grep -v "src.services.trends"
grep -r "from src.services.arxiv" src/ tests/ --include="*.py" | grep -v "src.services.trends"
```
Expected: No results (all imports updated). Note: `src/services/serpapi_client.py` is NOT part of this migration — it's for research agents, not trends.

- [ ] **Step 2: Verify old source files are deleted**

```bash
ls src/services/hackernews*.py src/services/google_trends*.py src/services/reddit*.py src/services/newsapi*.py src/services/arxiv*.py 2>/dev/null
```
Expected: "No such file or directory" for all.

- [ ] **Step 3: Run full test suite one final time with coverage**

Run: `cd D:/Workbench/github/cognify-arch-002 && uv run pytest --cov=src --cov-report=term-missing --tb=short -q`
Expected: All tests pass, coverage ≥ 97%.

- [ ] **Step 4: Final commit if any cleanup was needed**

```bash
git add -A
git commit -m "chore(arch-002): final cleanup and verification"
```
