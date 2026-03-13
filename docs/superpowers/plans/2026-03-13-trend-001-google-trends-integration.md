# TREND-001: Google Trends Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch trending searches and related queries from Google Trends via pytrends, filter by domain relevance, normalize scores, and expose as `RawTopic` objects via a REST endpoint.

**Architecture:** Client/Service/Router pattern matching TREND-003. `GoogleTrendsClient` wraps pytrends with `asyncio.to_thread()` for async compatibility. `GoogleTrendsService` handles scoring, filtering, dedup. Router adds endpoint alongside existing HN route.

**Tech Stack:** pytrends, FastAPI, Pydantic, structlog, pytest

**Spec:** [`docs/superpowers/specs/2026-03-13-trend-001-google-trends-integration-design.md`](../specs/2026-03-13-trend-001-google-trends-integration-design.md)

**Conda:** All commands use `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/services/google_trends_client.py` | Wraps pytrends — `fetch_trending_searches()` and `fetch_related_queries()`. TypedDicts for responses. `GoogleTrendsAPIError` exception. |
| `src/services/google_trends.py` | Business logic: scoring, velocity, domain filtering, dedup, field mapping to `RawTopic` |
| `tests/unit/services/test_google_trends_client.py` | Client unit tests (~5 tests) |
| `tests/unit/services/test_google_trends.py` | Service unit tests (~15 tests) |
| `tests/unit/api/test_google_trends_schemas.py` | Schema validation tests (~6 tests) |
| `tests/unit/api/test_google_trends_endpoints.py` | Endpoint integration tests (~8 tests) |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml:10-22` | Add `pytrends>=4.10.0` to `dependencies` |
| `src/config/settings.py:32-33` | Add 5 `gt_*` settings fields |
| `src/api/schemas/trends.py:1-16` | Add `GTFetchRequest`, `GTFetchResponse` models |
| `src/api/routers/trends.py:1-64` | Add `_get_gt_service()` helper and `POST /trends/google/fetch` route |
| `tests/unit/services/conftest.py:1-51` | Add `MockGoogleTrendsClient` class |

---

## Chunk 1: Foundation (Tasks 1–4)

### Task 1: Add pytrends dependency

**Files:**
- Modify: `pyproject.toml:10-22`

- [ ] **Step 1: Add pytrends to dependencies**

In `pyproject.toml`, add `"pytrends>=4.10.0"` to the `dependencies` list:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic-settings>=2.6.0",
    "structlog>=24.4.0",
    "slowapi>=0.1.9",
    "PyJWT[crypto]>=2.9.0",
    "bcrypt>=4.2.0",
    "email-validator>=2.2.0",
    "sentence-transformers>=3.0.0",
    "numpy>=1.26.0",
    "httpx>=0.27.0",
    "pytrends>=4.10.0",
]
```

- [ ] **Step 2: Install**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pip install -e ".[dev]"`
Expected: pytrends installed successfully

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat(trend-001): add pytrends dependency"
```

---

### Task 2: Add Google Trends settings

**Files:**
- Modify: `src/config/settings.py:32-33`

- [ ] **Step 1: Add gt_* settings fields**

Append after line 32 (after `hn_request_timeout`) in `src/config/settings.py`:

```python
    # Google Trends integration
    gt_language: str = "en-US"
    gt_timezone_offset: int = 360
    gt_default_country: str = "united_states"
    gt_default_max_results: int = 30
    gt_request_timeout: float = 15.0
```

- [ ] **Step 2: Verify settings load**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify python -c "from src.config.settings import Settings; s = Settings(); print(s.gt_language, s.gt_timezone_offset, s.gt_request_timeout)"`
Expected: `en-US 360 15.0`

- [ ] **Step 3: Commit**

```bash
git add src/config/settings.py
git commit -m "feat(trend-001): add gt_* settings for Google Trends"
```

---

### Task 3: Create GoogleTrendsClient

**Files:**
- Create: `src/services/google_trends_client.py`
- Create: `tests/unit/services/test_google_trends_client.py`

- [ ] **Step 1: Write the client test file**

Create `tests/unit/services/test_google_trends_client.py`:

```python
import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.services.google_trends_client import (
    GoogleTrendsAPIError,
    GoogleTrendsClient,
)


class TestFetchTrendingSearches:
    async def test_successful_fetch(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.return_value = pd.DataFrame(
            {0: ["AI security", "quantum computing"]},
        )

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            results = await client.fetch_trending_searches("united_states")

        assert len(results) == 2
        assert results[0]["title"] == "AI security"
        assert results[1]["title"] == "quantum computing"

    async def test_empty_results(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.return_value = pd.DataFrame(
            {0: []},
        )

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            results = await client.fetch_trending_searches("united_states")

        assert results == []

    async def test_pytrends_error_raises(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.side_effect = Exception(
            "API error",
        )

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            with pytest.raises(GoogleTrendsAPIError, match="API error"):
                await client.fetch_trending_searches("united_states")

    async def test_timeout_raises(self) -> None:
        from requests.exceptions import Timeout

        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.side_effect = Timeout(
            "Connection timed out",
        )

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            with pytest.raises(
                GoogleTrendsAPIError,
                match="timed out",
            ):
                await client.fetch_trending_searches("united_states")


class TestFetchRelatedQueries:
    async def test_successful_fetch(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.related_queries.return_value = {
            "cybersecurity": {
                "rising": pd.DataFrame(
                    {"query": ["cyber attack 2026"], "value": [500]},
                ),
                "top": pd.DataFrame(
                    {"query": ["network security"], "value": [80]},
                ),
            },
        }

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            results = await client.fetch_related_queries(
                ["cybersecurity"],
            )

        assert len(results) == 2
        rising = [r for r in results if r["query_type"] == "rising"]
        top = [r for r in results if r["query_type"] == "top"]
        assert len(rising) == 1
        assert rising[0]["title"] == "cyber attack 2026"
        assert rising[0]["value"] == 500
        assert len(top) == 1
        assert top[0]["title"] == "network security"

    async def test_breakout_value_converted(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.related_queries.return_value = {
            "ai": {
                "rising": pd.DataFrame(
                    {"query": ["ai breakout"], "value": ["Breakout"]},
                ),
                "top": None,
            },
        }

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            results = await client.fetch_related_queries(["ai"])

        assert len(results) == 1
        assert results[0]["value"] == 5000
        assert isinstance(results[0]["value"], int)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_google_trends_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.google_trends_client'`

- [ ] **Step 3: Write the client implementation**

Create `src/services/google_trends_client.py`:

```python
import asyncio
from typing import TypedDict

from pytrends.request import TrendReq


class GTTrendingSearch(TypedDict):
    title: str


class GTRelatedQuery(TypedDict):
    title: str
    value: int
    query_type: str
    seed_keyword: str


class GoogleTrendsAPIError(Exception):
    """Raised when Google Trends API is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class GoogleTrendsClient:
    def __init__(
        self,
        language: str,
        timezone_offset: int,
        timeout: float,
    ) -> None:
        self._pytrends = TrendReq(
            hl=language,
            tz=timezone_offset,
            requests_args={"timeout": timeout},
        )

    def _fetch_trending_sync(
        self,
        country: str,
    ) -> list[GTTrendingSearch]:
        df = self._pytrends.trending_searches(pn=country)
        results: list[GTTrendingSearch] = []
        for title in df[0].tolist():
            results.append(GTTrendingSearch(title=str(title)))
        return results

    def _fetch_related_sync(
        self,
        keywords: list[str],
    ) -> list[GTRelatedQuery]:
        self._pytrends.build_payload(kw_list=keywords[:5])
        raw = self._pytrends.related_queries()
        results: list[GTRelatedQuery] = []
        for keyword, data in raw.items():
            for query_type in ("rising", "top"):
                df = data.get(query_type)
                if df is None or df.empty:
                    continue
                for _, row in df.iterrows():
                    value = row["value"]
                    if value == "Breakout":
                        value = 5000
                    results.append(
                        GTRelatedQuery(
                            title=str(row["query"]),
                            value=int(value),
                            query_type=query_type,
                            seed_keyword=str(keyword),
                        ),
                    )
        return results

    async def fetch_trending_searches(
        self,
        country: str,
    ) -> list[GTTrendingSearch]:
        try:
            return await asyncio.to_thread(
                self._fetch_trending_sync,
                country,
            )
        except GoogleTrendsAPIError:
            raise
        except Exception as exc:
            raise GoogleTrendsAPIError(str(exc)) from exc

    async def fetch_related_queries(
        self,
        keywords: list[str],
    ) -> list[GTRelatedQuery]:
        try:
            return await asyncio.to_thread(
                self._fetch_related_sync,
                keywords,
            )
        except GoogleTrendsAPIError:
            raise
        except Exception as exc:
            raise GoogleTrendsAPIError(str(exc)) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_google_trends_client.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/services/google_trends_client.py tests/unit/services/test_google_trends_client.py
git commit -m "feat(trend-001): add GoogleTrendsClient with pytrends wrapper"
```

---

### Task 4: Add GTFetchRequest/GTFetchResponse schemas + tests

**Files:**
- Modify: `src/api/schemas/trends.py:1-16`
- Create: `tests/unit/api/test_google_trends_schemas.py`

- [ ] **Step 1: Write schema tests**

Create `tests/unit/api/test_google_trends_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from src.api.schemas.trends import GTFetchRequest, GTFetchResponse


class TestGTFetchRequest:
    def test_valid_request(self) -> None:
        req = GTFetchRequest(domain_keywords=["cyber"])
        assert req.domain_keywords == ["cyber"]
        assert req.country == "united_states"
        assert req.max_results == 30

    def test_custom_values(self) -> None:
        req = GTFetchRequest(
            domain_keywords=["ai", "ml"],
            country="united_kingdom",
            max_results=50,
        )
        assert req.country == "united_kingdom"
        assert req.max_results == 50

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GTFetchRequest(domain_keywords=[])

    def test_max_results_too_high(self) -> None:
        with pytest.raises(ValidationError):
            GTFetchRequest(domain_keywords=["x"], max_results=101)

    def test_max_results_too_low(self) -> None:
        with pytest.raises(ValidationError):
            GTFetchRequest(domain_keywords=["x"], max_results=0)


class TestGTFetchResponse:
    def test_response_shape(self) -> None:
        resp = GTFetchResponse(
            topics=[],
            total_trending=10,
            total_related=20,
            total_after_filter=5,
        )
        assert resp.total_trending == 10
        assert resp.total_related == 20
        assert resp.total_after_filter == 5
        assert resp.topics == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_google_trends_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'GTFetchRequest'`

- [ ] **Step 3: Add schemas to trends.py**

Append to `src/api/schemas/trends.py` (after the existing `HNFetchResponse` class):

```python


class GTFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    country: str = Field(default="united_states")
    max_results: int = Field(default=30, ge=1, le=100)


class GTFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_trending: int
    total_related: int
    total_after_filter: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_google_trends_schemas.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/api/schemas/trends.py tests/unit/api/test_google_trends_schemas.py
git commit -m "feat(trend-001): add GTFetchRequest/GTFetchResponse schemas"
```

---

## Chunk 2: Service Logic (Tasks 5–6)

### Task 5: Create GoogleTrendsService — scoring, filtering, mapping

**Files:**
- Create: `src/services/google_trends.py`
- Create: `tests/unit/services/test_google_trends.py`

- [ ] **Step 1: Write scoring and velocity tests**

Create `tests/unit/services/test_google_trends.py`:

```python
from datetime import UTC, datetime

from src.services.google_trends import GoogleTrendsService
from src.services.google_trends_client import (
    GTRelatedQuery,
    GTTrendingSearch,
)


class TestScoreCalculation:
    def test_trending_score_fixed_70(self) -> None:
        score = GoogleTrendsService.calculate_score("trending", 0)
        assert score == 70.0

    def test_rising_100_percent(self) -> None:
        """100% rise → 50 + (100/100)*10 = 60"""
        score = GoogleTrendsService.calculate_score("rising", 100)
        assert score == 60.0

    def test_rising_500_percent(self) -> None:
        """500% rise → 50 + (500/100)*10 = 100"""
        score = GoogleTrendsService.calculate_score("rising", 500)
        assert score == 100.0

    def test_rising_breakout_capped(self) -> None:
        """5000 (Breakout) → min(100, 50 + 500) = 100"""
        score = GoogleTrendsService.calculate_score("rising", 5000)
        assert score == 100.0

    def test_top_direct_mapping(self) -> None:
        score = GoogleTrendsService.calculate_score("top", 80)
        assert score == 80.0

    def test_top_zero(self) -> None:
        score = GoogleTrendsService.calculate_score("top", 0)
        assert score == 0.0


class TestVelocityCalculation:
    def test_trending_velocity(self) -> None:
        vel = GoogleTrendsService.calculate_velocity("trending", 0)
        assert vel == 50.0

    def test_rising_velocity(self) -> None:
        """200% → min(100, 200/10) = 20"""
        vel = GoogleTrendsService.calculate_velocity("rising", 200)
        assert vel == 20.0

    def test_rising_breakout_velocity_capped(self) -> None:
        """5000 → min(100, 500) = 100"""
        vel = GoogleTrendsService.calculate_velocity("rising", 5000)
        assert vel == 100.0

    def test_top_velocity(self) -> None:
        vel = GoogleTrendsService.calculate_velocity("top", 80)
        assert vel == 5.0


class TestDomainFiltering:
    def test_matches_title(self) -> None:
        items: list[GTTrendingSearch | GTRelatedQuery] = [
            GTTrendingSearch(title="cybersecurity trends"),
        ]
        matched = GoogleTrendsService.filter_by_domain(
            items,
            ["cyber"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_case_insensitive(self) -> None:
        items: list[GTTrendingSearch | GTRelatedQuery] = [
            GTTrendingSearch(title="AI SECURITY NEWS"),
        ]
        matched = GoogleTrendsService.filter_by_domain(items, ["ai"])
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        items: list[GTTrendingSearch | GTRelatedQuery] = [
            GTTrendingSearch(title="cooking recipes"),
        ]
        matched = GoogleTrendsService.filter_by_domain(
            items,
            ["cyber"],
        )
        assert len(matched) == 0

    def test_multiple_keywords_any_match(self) -> None:
        items: list[GTTrendingSearch | GTRelatedQuery] = [
            GTTrendingSearch(title="New AI model released"),
        ]
        matched = GoogleTrendsService.filter_by_domain(
            items,
            ["cyber", "AI"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]


class TestMapToRawTopic:
    def test_trending_mapping(self) -> None:
        topic = GoogleTrendsService.map_to_raw_topic(
            title="AI security trends",
            query_type="trending",
            value=0,
            matched_keywords=["AI", "security"],
        )
        assert topic.title == "AI security trends"
        assert topic.source == "google_trends"
        assert topic.description == ""
        assert topic.trend_score == 70.0
        assert topic.velocity == 50.0
        assert topic.domain_keywords == ["AI", "security"]
        assert "trends.google.com" in topic.external_url
        assert "AI+security+trends" in topic.external_url

    def test_rising_mapping(self) -> None:
        topic = GoogleTrendsService.map_to_raw_topic(
            title="cyber attack",
            query_type="rising",
            value=300,
            matched_keywords=["cyber"],
        )
        assert topic.trend_score == 80.0
        assert topic.velocity == 30.0

    def test_top_mapping(self) -> None:
        topic = GoogleTrendsService.map_to_raw_topic(
            title="network security",
            query_type="top",
            value=90,
            matched_keywords=["security"],
        )
        assert topic.trend_score == 90.0
        assert topic.velocity == 5.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_google_trends.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.google_trends'`

- [ ] **Step 3: Write the service implementation**

Create `src/services/google_trends.py`:

```python
import time
from datetime import UTC, datetime
from urllib.parse import quote_plus

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import GTFetchResponse
from src.services.google_trends_client import (
    GTRelatedQuery,
    GTTrendingSearch,
    GoogleTrendsClient,
)

logger = structlog.get_logger()


class GoogleTrendsService:
    def __init__(self, client: GoogleTrendsClient) -> None:
        self._client = client

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        country: str,
        max_results: int,
    ) -> GTFetchResponse:
        start = time.monotonic()
        logger.info(
            "google_trends_fetch_started",
            domain_keywords=domain_keywords,
            country=country,
            max_results=max_results,
        )
        trending = await self._client.fetch_trending_searches(
            country,
        )
        related = await self._client.fetch_related_queries(
            domain_keywords,
        )
        total_trending = len(trending)
        total_related = len(related)

        all_items: list[GTTrendingSearch | GTRelatedQuery] = [
            *trending,
            *related,
        ]
        filtered = self.filter_by_domain(
            all_items,
            domain_keywords,
        )
        logger.debug(
            "google_trends_results_filtered",
            before_count=len(all_items),
            after_count=len(filtered),
            domain_keywords=domain_keywords,
        )

        topics: list[RawTopic] = []
        for item, kws in filtered:
            query_type, value = self._extract_type_value(item)
            topic = self.map_to_raw_topic(
                title=item["title"],
                query_type=query_type,
                value=value,
                matched_keywords=kws,
            )
            topics.append(topic)

        topics = self._deduplicate(topics)
        total_after_filter = len(topics)
        topics = topics[:max_results]

        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "google_trends_fetch_completed",
            total_trending=total_trending,
            total_related=total_related,
            total_after_filter=total_after_filter,
            duration_ms=duration_ms,
        )
        return GTFetchResponse(
            topics=topics,
            total_trending=total_trending,
            total_related=total_related,
            total_after_filter=total_after_filter,
        )

    @staticmethod
    def _extract_type_value(
        item: GTTrendingSearch | GTRelatedQuery,
    ) -> tuple[str, int]:
        if "query_type" in item:
            rq: GTRelatedQuery = item  # type: ignore[assignment]
            return rq["query_type"], rq["value"]
        return "trending", 0

    @staticmethod
    def calculate_score(query_type: str, value: int) -> float:
        if query_type == "trending":
            return 70.0
        if query_type == "rising":
            return min(100.0, 50.0 + (value / 100.0) * 10.0)
        return float(value)

    @staticmethod
    def calculate_velocity(query_type: str, value: int) -> float:
        if query_type == "trending":
            return 50.0
        if query_type == "rising":
            return min(100.0, value / 10.0)
        return 5.0

    @staticmethod
    def filter_by_domain(
        items: list[GTTrendingSearch | GTRelatedQuery],
        domain_keywords: list[str],
    ) -> list[
        tuple[GTTrendingSearch | GTRelatedQuery, list[str]]
    ]:
        results: list[
            tuple[GTTrendingSearch | GTRelatedQuery, list[str]]
        ] = []
        for item in items:
            title_lower = item["title"].lower()
            matched = [
                kw
                for kw in domain_keywords
                if kw.lower() in title_lower
            ]
            if matched:
                results.append((item, matched))
        return results

    @staticmethod
    def map_to_raw_topic(
        title: str,
        query_type: str,
        value: int,
        matched_keywords: list[str],
    ) -> RawTopic:
        encoded = quote_plus(title)
        url = (
            "https://trends.google.com/trends/"
            f"explore?q={encoded}"
        )
        return RawTopic(
            title=title,
            description="",
            source="google_trends",
            external_url=url,
            trend_score=GoogleTrendsService.calculate_score(
                query_type,
                value,
            ),
            discovered_at=datetime.now(UTC),
            velocity=GoogleTrendsService.calculate_velocity(
                query_type,
                value,
            ),
            domain_keywords=matched_keywords,
        )

    @staticmethod
    def _deduplicate(topics: list[RawTopic]) -> list[RawTopic]:
        seen: dict[str, RawTopic] = {}
        for topic in topics:
            key = topic.title.lower()
            if key not in seen:
                seen[key] = topic
            elif topic.trend_score > seen[key].trend_score:
                seen[key] = topic
        return list(seen.values())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_google_trends.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/services/google_trends.py tests/unit/services/test_google_trends.py
git commit -m "feat(trend-001): add GoogleTrendsService with scoring, filtering, mapping"
```

---

### Task 6: Add dedup and fetch_and_normalize tests

**Files:**
- Modify: `tests/unit/services/test_google_trends.py` (append)
- Modify: `tests/unit/services/conftest.py`

- [ ] **Step 1: Add MockGoogleTrendsClient to conftest**

Append to `tests/unit/services/conftest.py`:

```python
from src.services.google_trends_client import (
    GoogleTrendsClient,
    GTRelatedQuery,
    GTTrendingSearch,
)


class MockGoogleTrendsClient(GoogleTrendsClient):
    """Returns canned trending/related data for deterministic testing."""

    def __init__(
        self,
        trending: list[GTTrendingSearch] | None = None,
        related: list[GTRelatedQuery] | None = None,
    ) -> None:
        # Skip parent __init__ — TrendReq() in super().__init__
        # attempts real HTTP initialization. Unlike MockHackerNewsClient
        # which can call super() with dummy URL/timeout, pytrends
        # TrendReq has no equivalent safe constructor args.
        self._trending = trending or []
        self._related = related or []

    async def fetch_trending_searches(
        self,
        country: str,
    ) -> list[GTTrendingSearch]:
        return self._trending

    async def fetch_related_queries(
        self,
        keywords: list[str],
    ) -> list[GTRelatedQuery]:
        return self._related
```

- [ ] **Step 2: Add dedup and pipeline tests**

Append to `tests/unit/services/test_google_trends.py`:

```python
from tests.unit.services.conftest import MockGoogleTrendsClient


class TestDeduplication:
    async def test_higher_score_wins(self) -> None:
        trending: list[GTTrendingSearch] = [
            GTTrendingSearch(title="AI Security"),
        ]
        related: list[GTRelatedQuery] = [
            GTRelatedQuery(
                title="ai security",
                value=500,
                query_type="rising",
                seed_keyword="ai",
            ),
        ]
        mock = MockGoogleTrendsClient(
            trending=trending,
            related=related,
        )
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["ai", "security"],
            country="united_states",
            max_results=30,
        )
        assert len(result.topics) == 1
        # Rising score (100) > trending score (70)
        assert result.topics[0].trend_score == 100.0

    async def test_first_wins_on_equal_score(self) -> None:
        related: list[GTRelatedQuery] = [
            GTRelatedQuery(
                title="AI Security",
                value=80,
                query_type="top",
                seed_keyword="ai",
            ),
            GTRelatedQuery(
                title="ai security",
                value=80,
                query_type="top",
                seed_keyword="security",
            ),
        ]
        mock = MockGoogleTrendsClient(related=related)
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["ai", "security"],
            country="united_states",
            max_results=30,
        )
        assert len(result.topics) == 1


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        trending: list[GTTrendingSearch] = [
            GTTrendingSearch(title="cybersecurity breach"),
            GTTrendingSearch(title="cooking show"),
        ]
        related: list[GTRelatedQuery] = [
            GTRelatedQuery(
                title="cyber attack 2026",
                value=300,
                query_type="rising",
                seed_keyword="cyber",
            ),
        ]
        mock = MockGoogleTrendsClient(
            trending=trending,
            related=related,
        )
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            country="united_states",
            max_results=30,
        )
        assert result.total_trending == 2
        assert result.total_related == 1
        # "cooking show" filtered out
        assert result.total_after_filter == 2
        assert len(result.topics) == 2

    async def test_empty_results(self) -> None:
        mock = MockGoogleTrendsClient()
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            country="united_states",
            max_results=30,
        )
        assert result.total_trending == 0
        assert result.total_related == 0
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_max_results_caps_output(self) -> None:
        trending: list[GTTrendingSearch] = [
            GTTrendingSearch(title=f"cyber topic {i}")
            for i in range(10)
        ]
        mock = MockGoogleTrendsClient(trending=trending)
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            country="united_states",
            max_results=3,
        )
        assert len(result.topics) == 3
        assert result.total_after_filter == 10
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_google_trends.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/unit/services/conftest.py tests/unit/services/test_google_trends.py
git commit -m "feat(trend-001): add dedup and pipeline tests with MockGoogleTrendsClient"
```

---

## Chunk 3: Router & Endpoint Tests (Tasks 7–8)

### Task 7: Add Google Trends endpoint to router

**Files:**
- Modify: `src/api/routers/trends.py:1-64`
- Create: `tests/unit/api/test_google_trends_endpoints.py`

- [ ] **Step 1: Write endpoint tests**

Create `tests/unit/api/test_google_trends_endpoints.py`:

```python
from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.services.google_trends_client import (
    GTRelatedQuery,
    GTTrendingSearch,
)
from tests.unit.services.conftest import MockGoogleTrendsClient

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header


SAMPLE_TRENDING: list[GTTrendingSearch] = [
    GTTrendingSearch(title="Cybersecurity Trends 2026"),
]

SAMPLE_RELATED: list[GTRelatedQuery] = [
    GTRelatedQuery(
        title="cyber attack prevention",
        value=200,
        query_type="rising",
        seed_keyword="cyber",
    ),
]


def _gt_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "domain_keywords": ["cyber"],
        "country": "united_states",
        "max_results": 30,
    }
    base.update(overrides)
    return base


@pytest.fixture
def gt_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def gt_app(gt_settings: Settings) -> FastAPI:
    app = create_app(gt_settings)
    app.state.gt_client = MockGoogleTrendsClient(
        trending=SAMPLE_TRENDING,
        related=SAMPLE_RELATED,
    )
    return app


@pytest.fixture
async def gt_client(
    gt_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gt_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestGTEndpointAuth:
    async def test_no_token_returns_401(
        self,
        gt_client: httpx.AsyncClient,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
            headers=make_auth_header("viewer", gt_settings),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
            headers=make_auth_header("editor", gt_settings),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
            headers=make_auth_header("admin", gt_settings),
        )
        assert resp.status_code == 200


class TestGTEndpointValidation:
    async def test_empty_keywords_returns_422(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(domain_keywords=[]),
            headers=make_auth_header("editor", gt_settings),
        )
        assert resp.status_code == 422


class TestGTEndpointSuccess:
    async def test_response_shape(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(),
            headers=make_auth_header("editor", gt_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "total_trending" in data
        assert "total_related" in data
        assert "total_after_filter" in data

    async def test_no_matches_returns_empty(
        self,
        gt_client: httpx.AsyncClient,
        gt_settings: Settings,
    ) -> None:
        resp = await gt_client.post(
            "/api/v1/trends/google/fetch",
            json=_gt_request(domain_keywords=["cooking"]),
            headers=make_auth_header("editor", gt_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_after_filter"] == 0


class TestGTEndpoint503:
    async def test_api_error_returns_503(
        self,
        gt_settings: Settings,
    ) -> None:
        from src.services.google_trends_client import (
            GoogleTrendsAPIError,
        )

        class FailingClient(MockGoogleTrendsClient):
            async def fetch_trending_searches(
                self,
                country: str,
            ) -> list[GTTrendingSearch]:
                raise GoogleTrendsAPIError("API down")

        app = create_app(gt_settings)
        app.state.gt_client = FailingClient()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/trends/google/fetch",
                json=_gt_request(),
                headers=make_auth_header(
                    "editor",
                    gt_settings,
                ),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert (
                data["error"]["code"]
                == "google_trends_unavailable"
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_google_trends_endpoints.py -v`
Expected: FAIL — no route `/trends/google/fetch`

- [ ] **Step 3: Add Google Trends route to router**

Modify `src/api/routers/trends.py` — add imports and the new endpoint. The full file becomes:

```python
import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.trends import (
    GTFetchRequest,
    GTFetchResponse,
    HNFetchRequest,
    HNFetchResponse,
)
from src.services.google_trends import GoogleTrendsService
from src.services.google_trends_client import (
    GoogleTrendsAPIError,
    GoogleTrendsClient,
)
from src.services.hackernews import HackerNewsService
from src.services.hackernews_client import (
    HackerNewsAPIError,
    HackerNewsClient,
)

logger = structlog.get_logger()

trends_router = APIRouter()


def _get_hn_service(request: Request) -> HackerNewsService:
    settings = request.app.state.settings
    # Test injection: tests set app.state.hn_client to a mock.
    # In production, a fresh short-lived client is created per request.
    if hasattr(request.app.state, "hn_client"):
        client = request.app.state.hn_client
    else:
        client = HackerNewsClient(
            base_url=settings.hn_api_base_url,
            timeout=settings.hn_request_timeout,
        )
    return HackerNewsService(
        client=client,
        points_cap=settings.hn_points_cap,
    )


def _get_gt_service(request: Request) -> GoogleTrendsService:
    settings = request.app.state.settings
    # Test injection: tests set app.state.gt_client to a mock.
    # In production, a fresh short-lived client is created per request.
    if hasattr(request.app.state, "gt_client"):
        client = request.app.state.gt_client
    else:
        client = GoogleTrendsClient(
            language=settings.gt_language,
            timezone_offset=settings.gt_timezone_offset,
            timeout=settings.gt_request_timeout,
        )
    return GoogleTrendsService(client=client)


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/hackernews/fetch",
    response_model=HNFetchResponse,
    summary="Fetch trending HN stories",
)
async def fetch_hackernews(
    request: Request,
    body: HNFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> HNFetchResponse:
    service = _get_hn_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            max_results=body.max_results,
            min_points=body.min_points,
        )
    except HackerNewsAPIError as exc:
        logger.error(
            "hackernews_api_error",
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="hackernews_unavailable",
            message="Hacker News API is not available",
        ) from exc


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/google/fetch",
    response_model=GTFetchResponse,
    summary="Fetch Google Trends topics",
)
async def fetch_google_trends(
    request: Request,
    body: GTFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> GTFetchResponse:
    service = _get_gt_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            country=body.country,
            max_results=body.max_results,
        )
    except GoogleTrendsAPIError as exc:
        logger.error(
            "google_trends_api_error",
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="google_trends_unavailable",
            message="Google Trends API is not available",
        ) from exc
```

- [ ] **Step 4: Run endpoint tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_google_trends_endpoints.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/api/routers/trends.py tests/unit/api/test_google_trends_endpoints.py
git commit -m "feat(trend-001): add POST /trends/google/fetch endpoint"
```

---

### Task 8: Run full test suite, lint, and type checks

**Files:** None (verification only)

- [ ] **Step 1: Run ruff format**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format src/ tests/`
Expected: Files formatted (or already formatted)

- [ ] **Step 2: Run ruff check**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/ tests/`
Expected: All checks passed!

- [ ] **Step 3: Run mypy**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/`
Expected: Success — no errors found

- [ ] **Step 4: Run full test suite with coverage**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest --cov=src --cov-report=term-missing -v`
Expected: All tests pass, coverage ≥80% on new files

- [ ] **Step 5: Fix any issues**

If any lint/type/test issues: fix them and re-run the failing check.

- [ ] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "chore(trend-001): fix lint and type issues"
```

(Skip if no fixes were needed.)

---

## Summary

| Task | Description | Tests |
|------|------------|-------|
| 1 | Add pytrends dependency | — |
| 2 | Add gt_* settings | — |
| 3 | GoogleTrendsClient + tests | ~6 |
| 4 | GT schemas + tests | ~6 |
| 5 | GoogleTrendsService (scoring, filtering, mapping) + tests | ~13 |
| 6 | Dedup + pipeline tests + MockGoogleTrendsClient | ~6 |
| 7 | Router endpoint + endpoint tests | ~8 |
| 8 | Full lint/type/test verification | — |
| **Total** | | **~39** |
