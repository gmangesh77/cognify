# TREND-003: Hacker News Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch trending HN stories via Algolia API, filter by domain, normalize scores, and expose via a FastAPI endpoint that produces `RawTopic` objects for the existing ranking pipeline.

**Architecture:** Client/Service/Router separation. `HackerNewsClient` handles HTTP to Algolia, `HackerNewsService` handles filtering/scoring/normalization, `trends_router` handles auth/rate-limiting/error-mapping. All output as `RawTopic` from the existing TREND-006 schema.

**Tech Stack:** Python 3.12, FastAPI, httpx (async HTTP), Pydantic v2, structlog, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-13-trend-003-hackernews-integration-design.md`

**Conda:** All commands use `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify`

---

## Chunk 1: Dependencies, Settings, Schemas

### Task 1: Promote httpx to production dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Move httpx from dev to prod dependencies**

In `pyproject.toml`, add `"httpx>=0.27.0"` to the `dependencies` list and remove it from `[project.optional-dependencies] dev`.

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
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "freezegun>=1.4.0",
]
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -q`
Expected: All existing tests pass.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: promote httpx to production dependency"
```

---

### Task 2: Add HN settings fields

**Files:**
- Modify: `src/config/settings.py`
- Test: `tests/unit/config/test_settings.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/config/test_settings.py`:

```python
class TestHackerNewsSettings:
    def test_hn_defaults(self) -> None:
        s = Settings()
        assert s.hn_api_base_url == "https://hn.algolia.com/api/v1"
        assert s.hn_default_max_results == 30
        assert s.hn_default_min_points == 10
        assert s.hn_points_cap == 300.0
        assert s.hn_request_timeout == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/config/test_settings.py::TestHackerNewsSettings -v`
Expected: FAIL — `Settings` has no field `hn_api_base_url`.

- [ ] **Step 3: Add HN settings fields**

Add to `src/config/settings.py` after the `dedup_similarity_threshold` line:

```python
    # Hacker News integration
    hn_api_base_url: str = "https://hn.algolia.com/api/v1"
    hn_default_max_results: int = 30
    hn_default_min_points: int = 10
    hn_points_cap: float = 300.0
    hn_request_timeout: float = 10.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/config/test_settings.py::TestHackerNewsSettings -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/config/settings.py tests/unit/config/test_settings.py
git commit -m "feat: add Hacker News integration settings"
```

---

### Task 3: Create trend schemas (HNFetchRequest, HNFetchResponse)

**Files:**
- Create: `src/api/schemas/trends.py`
- Test: `tests/unit/api/test_trend_schemas.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/test_trend_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from src.api.schemas.trends import HNFetchRequest, HNFetchResponse


class TestHNFetchRequest:
    def test_valid_request(self) -> None:
        req = HNFetchRequest(domain_keywords=["cyber"])
        assert req.domain_keywords == ["cyber"]
        assert req.max_results == 30
        assert req.min_points == 10

    def test_custom_values(self) -> None:
        req = HNFetchRequest(
            domain_keywords=["ai", "ml"],
            max_results=50,
            min_points=20,
        )
        assert req.max_results == 50
        assert req.min_points == 20

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HNFetchRequest(domain_keywords=[])

    def test_max_results_too_high(self) -> None:
        with pytest.raises(ValidationError):
            HNFetchRequest(domain_keywords=["x"], max_results=101)

    def test_max_results_too_low(self) -> None:
        with pytest.raises(ValidationError):
            HNFetchRequest(domain_keywords=["x"], max_results=0)

    def test_negative_min_points(self) -> None:
        with pytest.raises(ValidationError):
            HNFetchRequest(domain_keywords=["x"], min_points=-1)


class TestHNFetchResponse:
    def test_response_shape(self) -> None:
        resp = HNFetchResponse(
            topics=[],
            total_fetched=10,
            total_after_filter=3,
        )
        assert resp.total_fetched == 10
        assert resp.total_after_filter == 3
        assert resp.topics == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_trend_schemas.py -v`
Expected: FAIL — cannot import `HNFetchRequest`.

- [ ] **Step 3: Create the schemas**

Verify that `src/api/schemas/__init__.py` exists (it does — created in TREND-006). No changes needed to `__init__.py` since the new schemas are imported directly by the router.

Create `src/api/schemas/trends.py`:

```python
from pydantic import BaseModel, Field

from src.api.schemas.topics import RawTopic


class HNFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    max_results: int = Field(default=30, ge=1, le=100)
    min_points: int = Field(default=10, ge=0)


class HNFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_filter: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_trend_schemas.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/schemas/trends.py tests/unit/api/test_trend_schemas.py
git commit -m "feat: add HNFetchRequest and HNFetchResponse schemas"
```

---

## Chunk 2: HackerNewsClient

### Task 4: Create HackerNewsClient with HNStoryResponse type

**Files:**
- Create: `src/services/hackernews_client.py`
- Create: `tests/unit/services/test_hackernews_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/services/test_hackernews_client.py`:

```python
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.hackernews_client import (
    HackerNewsAPIError,
    HackerNewsClient,
)

SAMPLE_HIT = {
    "objectID": "123",
    "title": "Cybersecurity Trends 2026",
    "url": "https://example.com/cyber",
    "points": 150,
    "num_comments": 42,
    "story_text": "A deep dive into security.",
    "created_at_i": 1710000000,
}


class TestFetchStories:
    async def test_successful_fetch(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"hits": [SAMPLE_HIT]},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            stories = await client.fetch_stories("cyber", 10, 30)

        assert len(stories) == 1
        assert stories[0]["title"] == "Cybersecurity Trends 2026"
        assert stories[0]["points"] == 150

    async def test_empty_results(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"hits": []},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            stories = await client.fetch_stories("niche", 10, 30)

        assert stories == []

    async def test_http_error_raises(self) -> None:
        mock_response = httpx.Response(
            500,
            json={"message": "server error"},
            request=httpx.Request("GET", "http://test"),
        )
        mock_response.is_success = False
        with patch("src.services.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(HackerNewsAPIError, match="500"):
                await client.fetch_stories("cyber", 10, 30)

    async def test_timeout_raises(self) -> None:
        with patch("src.services.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(HackerNewsAPIError, match="timed out"):
                await client.fetch_stories("cyber", 10, 30)

    async def test_connection_error_raises(self) -> None:
        with patch("src.services.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(HackerNewsAPIError, match="refused"):
                await client.fetch_stories("cyber", 10, 30)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews_client.py -v`
Expected: FAIL — cannot import `HackerNewsClient`.

- [ ] **Step 3: Implement HackerNewsClient**

Create `src/services/hackernews_client.py`:

```python
from typing import TypedDict

import httpx


class HNStoryResponse(TypedDict):
    objectID: str
    title: str
    url: str | None
    points: int | None
    num_comments: int | None
    story_text: str | None
    created_at_i: int


class HackerNewsAPIError(Exception):
    """Raised when the Algolia HN API is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class HackerNewsClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url
        self._timeout = timeout

    async def fetch_stories(
        self,
        query: str,
        min_points: int,
        num_results: int,
    ) -> list[HNStoryResponse]:
        params = {
            "query": query,
            "tags": "story",
            "numericFilters": f"points>{min_points}",
            "hitsPerPage": num_results,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
            ) as client:
                resp = await client.get(
                    f"{self._base_url}/search",
                    params=params,
                )
        except httpx.TimeoutException as exc:
            raise HackerNewsAPIError(
                f"HN API timed out: {exc}",
            ) from exc
        except httpx.ConnectError as exc:
            raise HackerNewsAPIError(
                f"HN API connection failed: {exc}",
            ) from exc
        if not resp.is_success:
            raise HackerNewsAPIError(
                f"HN API returned {resp.status_code}",
            )
        hits: list[HNStoryResponse] = resp.json()["hits"]
        return hits
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews_client.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/hackernews_client.py tests/unit/services/test_hackernews_client.py
git commit -m "feat: add HackerNewsClient with Algolia HN API integration"
```

---

## Chunk 3: HackerNewsService

### Task 5: Implement score normalization

**Files:**
- Create: `src/services/hackernews.py`
- Create: `tests/unit/services/test_hackernews.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/services/test_hackernews.py`:

```python
from src.services.hackernews import HackerNewsService


class TestScoreNormalization:
    def test_standard_score(self) -> None:
        """50 points, 20 comments, cap 300: (35+6)/300*100 ≈ 13.67"""
        score = HackerNewsService.calculate_score(50, 20, 300.0)
        assert round(score, 2) == 13.67

    def test_high_score_capped_at_100(self) -> None:
        """500 points, 200 comments, cap 300 → exceeds cap → 100"""
        score = HackerNewsService.calculate_score(500, 200, 300.0)
        assert score == 100.0

    def test_zero_points_zero_comments(self) -> None:
        score = HackerNewsService.calculate_score(0, 0, 300.0)
        assert score == 0.0

    def test_exact_cap(self) -> None:
        """300 points, 0 comments, cap 300: (210+0)/300*100 = 70"""
        score = HackerNewsService.calculate_score(300, 0, 300.0)
        assert score == 70.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py::TestScoreNormalization -v`
Expected: FAIL — cannot import `HackerNewsService`.

- [ ] **Step 3: Implement calculate_score**

Create `src/services/hackernews.py`:

```python
import structlog

logger = structlog.get_logger()


class HackerNewsService:
    @staticmethod
    def calculate_score(
        points: int,
        num_comments: int,
        points_cap: float,
    ) -> float:
        raw = (points * 0.7) + (num_comments * 0.3)
        return min(100.0, (raw / points_cap) * 100)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py::TestScoreNormalization -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/hackernews.py tests/unit/services/test_hackernews.py
git commit -m "feat: add HackerNewsService with score normalization"
```

---

### Task 6: Implement velocity calculation

**Files:**
- Modify: `src/services/hackernews.py`
- Modify: `tests/unit/services/test_hackernews.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/services/test_hackernews.py`:

```python
class TestVelocityCalculation:
    def test_recent_high_points(self) -> None:
        """100 points, 2 hours ago → velocity 50"""
        vel = HackerNewsService.calculate_velocity(100, 2.0)
        assert vel == 50.0

    def test_old_story(self) -> None:
        """100 points, 20 hours ago → velocity 5"""
        vel = HackerNewsService.calculate_velocity(100, 20.0)
        assert vel == 5.0

    def test_very_recent_clamped_to_1h(self) -> None:
        """100 points, 0.1 hours → clamped to 1h → velocity 100"""
        vel = HackerNewsService.calculate_velocity(100, 0.1)
        assert vel == 100.0

    def test_zero_points(self) -> None:
        vel = HackerNewsService.calculate_velocity(0, 5.0)
        assert vel == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py::TestVelocityCalculation -v`
Expected: FAIL — `HackerNewsService` has no `calculate_velocity`.

- [ ] **Step 3: Implement calculate_velocity**

Add to `src/services/hackernews.py` in the `HackerNewsService` class:

```python
    @staticmethod
    def calculate_velocity(points: int, hours_ago: float) -> float:
        hours = max(1.0, hours_ago)
        return points / hours
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py::TestVelocityCalculation -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/hackernews.py tests/unit/services/test_hackernews.py
git commit -m "feat: add velocity calculation (points per hour)"
```

---

### Task 7: Implement domain filtering

**Files:**
- Modify: `src/services/hackernews.py`
- Modify: `tests/unit/services/test_hackernews.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/services/test_hackernews.py`:

```python
from src.services.hackernews_client import HNStoryResponse


def _story(**overrides: object) -> HNStoryResponse:
    base: HNStoryResponse = {
        "objectID": "1",
        "title": "Test Story",
        "url": "https://example.com",
        "points": 100,
        "num_comments": 20,
        "story_text": None,
        "created_at_i": 1710000000,
    }
    result: dict[str, object] = {**base, **overrides}
    return result  # type: ignore[return-value]


class TestDomainFiltering:
    def test_matches_title(self) -> None:
        story = _story(title="Cybersecurity breach report")
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_matches_url(self) -> None:
        story = _story(
            title="A normal title",
            url="https://cybernews.com/article",
        )
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 1

    def test_case_insensitive(self) -> None:
        story = _story(title="CYBERSECURITY NEWS")
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        story = _story(title="Cooking recipes")
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 0

    def test_multiple_keywords_any_match(self) -> None:
        story = _story(title="New AI model released")
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber", "AI"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]

    def test_none_url_handled(self) -> None:
        story = _story(title="Cyber topic", url=None)
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py::TestDomainFiltering -v`
Expected: FAIL — `HackerNewsService` has no `filter_by_domain`.

- [ ] **Step 3: Implement filter_by_domain**

`filter_by_domain` returns a list of `(story, matched_keywords)` tuples for stories that match at least one keyword. Add to `src/services/hackernews.py`:

```python
from src.services.hackernews_client import HNStoryResponse


class HackerNewsService:
    # ... existing methods ...

    @staticmethod
    def filter_by_domain(
        stories: list[HNStoryResponse],
        domain_keywords: list[str],
    ) -> list[tuple[HNStoryResponse, list[str]]]:
        results: list[tuple[HNStoryResponse, list[str]]] = []
        for story in stories:
            title = story["title"].lower()
            url = (story.get("url") or "").lower()
            matched = [
                kw
                for kw in domain_keywords
                if kw.lower() in title or kw.lower() in url
            ]
            if matched:
                results.append((story, matched))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py::TestDomainFiltering -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/hackernews.py tests/unit/services/test_hackernews.py
git commit -m "feat: add domain keyword filtering for HN stories"
```

---

### Task 8: Implement story-to-RawTopic mapping

**Files:**
- Modify: `src/services/hackernews.py`
- Modify: `tests/unit/services/test_hackernews.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/services/test_hackernews.py`:

```python
from datetime import UTC, datetime


class TestStoryMapping:
    def test_full_mapping(self) -> None:
        story = _story(
            objectID="42",
            title="Cyber Attack Analysis",
            url="https://example.com/cyber",
            points=150,
            num_comments=40,
            story_text="Detailed analysis of attack.",
            created_at_i=1710000000,
        )
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["cyber"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.title == "Cyber Attack Analysis"
        assert topic.source == "hackernews"
        assert topic.external_url == "https://example.com/cyber"
        assert topic.domain_keywords == ["cyber"]
        assert topic.description == "Detailed analysis of attack."
        assert 0 <= topic.trend_score <= 100
        assert topic.velocity > 0

    def test_missing_url_uses_hn_link(self) -> None:
        story = _story(objectID="99", url=None)
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["test"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert "news.ycombinator.com/item?id=99" in topic.external_url

    def test_missing_story_text_empty_description(self) -> None:
        story = _story(story_text=None)
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["test"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.description == ""

    def test_long_story_text_truncated(self) -> None:
        story = _story(story_text="x" * 500)
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["test"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert len(topic.description) == 200

    def test_none_points_treated_as_zero(self) -> None:
        story = _story(points=None, num_comments=None)
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["test"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.trend_score == 0.0
        assert topic.velocity == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py::TestStoryMapping -v`
Expected: FAIL — `HackerNewsService` has no `map_to_raw_topic`.

- [ ] **Step 3: Implement map_to_raw_topic**

Add to `src/services/hackernews.py`:

```python
from datetime import UTC, datetime

from src.api.schemas.topics import RawTopic


class HackerNewsService:
    # ... existing methods ...

    @staticmethod
    def map_to_raw_topic(
        story: HNStoryResponse,
        matched_keywords: list[str],
        points_cap: float,
        now: datetime | None = None,
    ) -> RawTopic:
        if now is None:
            now = datetime.now(UTC)
        points = story.get("points") or 0
        comments = story.get("num_comments") or 0
        created = datetime.fromtimestamp(
            story["created_at_i"], tz=UTC,
        )
        hours_ago = (now - created).total_seconds() / 3600
        url = story.get("url") or (
            f"https://news.ycombinator.com/item?id={story['objectID']}"
        )
        text = story.get("story_text") or ""
        return RawTopic(
            title=story["title"],
            description=text[:200],
            source="hackernews",
            external_url=url,
            trend_score=HackerNewsService.calculate_score(
                points, comments, points_cap,
            ),
            discovered_at=created,
            velocity=HackerNewsService.calculate_velocity(
                points, hours_ago,
            ),
            domain_keywords=matched_keywords,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py::TestStoryMapping -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/hackernews.py tests/unit/services/test_hackernews.py
git commit -m "feat: add story-to-RawTopic field mapping"
```

---

### Task 9: Implement fetch_and_normalize orchestrator

**Files:**
- Modify: `src/services/hackernews.py`
- Modify: `tests/unit/services/test_hackernews.py`
- Modify: `tests/unit/services/conftest.py`

- [ ] **Step 1: Create MockHackerNewsClient**

Add to `tests/unit/services/conftest.py`:

```python
from src.services.hackernews_client import HackerNewsClient, HNStoryResponse


class MockHackerNewsClient(HackerNewsClient):
    """Returns canned stories for deterministic testing."""

    def __init__(
        self,
        stories: list[HNStoryResponse] | None = None,
    ) -> None:
        super().__init__(base_url="http://mock", timeout=1.0)
        self._stories = stories or []

    async def fetch_stories(
        self,
        query: str,
        min_points: int,
        num_results: int,
    ) -> list[HNStoryResponse]:
        return self._stories[:num_results]
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/unit/services/test_hackernews.py`:

```python
from tests.unit.services.conftest import MockHackerNewsClient


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        stories: list[HNStoryResponse] = [
            _story(
                objectID="1",
                title="Cybersecurity breach",
                points=200,
                num_comments=50,
            ),
            _story(
                objectID="2",
                title="Cooking recipes",
                points=300,
                num_comments=100,
            ),
        ]
        mock_client = MockHackerNewsClient(stories=stories)
        service = HackerNewsService(
            client=mock_client,
            points_cap=300.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            max_results=30,
            min_points=10,
        )
        assert result.total_fetched == 2
        assert result.total_after_filter == 1
        assert len(result.topics) == 1
        assert result.topics[0].title == "Cybersecurity breach"

    async def test_empty_stories(self) -> None:
        mock_client = MockHackerNewsClient(stories=[])
        service = HackerNewsService(
            client=mock_client,
            points_cap=300.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            max_results=30,
            min_points=10,
        )
        assert result.total_fetched == 0
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_no_matches_after_filter(self) -> None:
        stories = [_story(title="Cooking blog")]
        mock_client = MockHackerNewsClient(stories=stories)
        service = HackerNewsService(
            client=mock_client,
            points_cap=300.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            max_results=30,
            min_points=10,
        )
        assert result.total_fetched == 1
        assert result.total_after_filter == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py::TestFetchAndNormalize -v`
Expected: FAIL — `HackerNewsService.__init__` doesn't accept `client`.

- [ ] **Step 4: Refactor HackerNewsService to accept client and implement fetch_and_normalize**

Update `src/services/hackernews.py` — add `__init__` and `fetch_and_normalize`. **IMPORTANT: All existing `@staticmethod` decorators on `calculate_score`, `calculate_velocity`, `filter_by_domain`, and `map_to_raw_topic` MUST be preserved.**

```python
import time

import structlog

from datetime import UTC, datetime

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import HNFetchResponse
from src.services.hackernews_client import HackerNewsClient, HNStoryResponse

logger = structlog.get_logger()


class HackerNewsService:
    def __init__(
        self,
        client: HackerNewsClient,
        points_cap: float,
    ) -> None:
        self._client = client
        self._points_cap = points_cap

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        max_results: int,
        min_points: int,
    ) -> HNFetchResponse:
        start = time.monotonic()
        logger.info(
            "hackernews_fetch_started",
            domain_keywords=domain_keywords,
            max_results=max_results,
            min_points=min_points,
        )
        query = " ".join(domain_keywords)
        stories = await self._client.fetch_stories(
            query, min_points, max_results,
        )
        total_fetched = len(stories)
        filtered = self.filter_by_domain(
            stories, domain_keywords,
        )
        logger.debug(
            "hackernews_stories_filtered",
            before_count=total_fetched,
            after_count=len(filtered),
            domain_keywords=domain_keywords,
        )
        topics = [
            self.map_to_raw_topic(
                story, kws, self._points_cap,
            )
            for story, kws in filtered
        ]
        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "hackernews_fetch_completed",
            total_fetched=total_fetched,
            total_after_filter=len(topics),
            duration_ms=duration_ms,
        )
        return HNFetchResponse(
            topics=topics,
            total_fetched=total_fetched,
            total_after_filter=len(topics),
        )

    # ... keep ALL existing @staticmethod methods unchanged ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_hackernews.py -v`
Expected: All tests PASS. Static method tests continue to work since `@staticmethod` decorators are preserved.

- [ ] **Step 6: Commit**

```bash
git add src/services/hackernews.py tests/unit/services/test_hackernews.py tests/unit/services/conftest.py
git commit -m "feat: add fetch_and_normalize orchestrator with MockHackerNewsClient"
```

---

## Chunk 4: API Endpoint

### Task 10: Create trends router and endpoint

**Files:**
- Create: `src/api/routers/trends.py`
- Modify: `src/api/main.py`
- Create: `tests/unit/api/test_trend_endpoints.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/test_trend_endpoints.py`:

```python
from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.services.hackernews_client import HNStoryResponse
from tests.unit.services.conftest import MockHackerNewsClient

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header


def _hn_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "domain_keywords": ["cyber"],
        "max_results": 30,
        "min_points": 10,
    }
    base.update(overrides)
    return base


SAMPLE_STORIES: list[HNStoryResponse] = [
    {
        "objectID": "1",
        "title": "Cybersecurity Trends 2026",
        "url": "https://example.com/cyber",
        "points": 150,
        "num_comments": 42,
        "story_text": "Analysis of trends.",
        "created_at_i": 1710000000,
    },
]


@pytest.fixture
def trend_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def trend_app(trend_settings: Settings) -> FastAPI:
    app = create_app(trend_settings)
    app.state.hn_client = MockHackerNewsClient(
        stories=SAMPLE_STORIES,
    )
    return app


@pytest.fixture
async def trend_client(
    trend_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=trend_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestTrendEndpointAuth:
    async def test_no_token_returns_401(
        self,
        trend_client: httpx.AsyncClient,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
            headers=make_auth_header("viewer", trend_settings),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
            headers=make_auth_header("admin", trend_settings),
        )
        assert resp.status_code == 200


class TestTrendEndpointValidation:
    async def test_empty_keywords_returns_422(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(domain_keywords=[]),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 422


class TestTrendEndpointSuccess:
    async def test_response_shape(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "total_fetched" in data
        assert "total_after_filter" in data
        assert data["total_fetched"] == 1

    async def test_no_matches_returns_empty(
        self,
        trend_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await trend_client.post(
            "/api/v1/trends/hackernews/fetch",
            json=_hn_request(domain_keywords=["cooking"]),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_after_filter"] == 0


class TestTrendEndpoint503:
    async def test_api_error_returns_503(
        self,
        trend_settings: Settings,
    ) -> None:
        from src.services.hackernews_client import HackerNewsAPIError

        class FailingClient(MockHackerNewsClient):
            async def fetch_stories(
                self,
                query: str,
                min_points: int,
                num_results: int,
            ) -> list[HNStoryResponse]:
                raise HackerNewsAPIError("API down")

        app = create_app(trend_settings)
        app.state.hn_client = FailingClient()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/trends/hackernews/fetch",
                json=_hn_request(),
                headers=make_auth_header(
                    "editor", trend_settings,
                ),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "hackernews_unavailable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_trend_endpoints.py -v`
Expected: FAIL — cannot import from `src.api.routers.trends`.

- [ ] **Step 3: Create trends router**

Create `src/api/routers/trends.py`:

```python
import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.trends import HNFetchRequest, HNFetchResponse
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
```

- [ ] **Step 4: Register trends_router in main.py**

Add to `src/api/main.py` — import at top:

```python
from src.api.routers.trends import trends_router
```

Add in `_register_routers` function after the topics_router block:

```python
    app.include_router(
        trends_router,
        prefix=settings.api_v1_prefix,
        tags=["trends"],
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_trend_endpoints.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 6: Run full test suite**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -q`
Expected: All tests pass (existing + new).

- [ ] **Step 7: Commit**

```bash
git add src/api/routers/trends.py src/api/main.py tests/unit/api/test_trend_endpoints.py
git commit -m "feat: add POST /api/v1/trends/hackernews/fetch endpoint"
```

---

## Chunk 5: Linting, Verification, Progress Tracking

### Task 11: Run linting and type checking

**Files:** All new/modified files

- [ ] **Step 1: Run ruff check**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/ tests/`
Expected: No errors. If errors, fix and re-run.

- [ ] **Step 2: Run ruff format**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/ tests/`
Expected: No reformatting needed. If needed, run `ruff format src/ tests/` and commit fixes.

- [ ] **Step 3: Run mypy**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/ --strict`
Expected: No errors. Fix any type issues.

- [ ] **Step 4: Run full test suite with coverage**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest --cov=src --cov-report=term-missing -q`
Expected: All tests pass, coverage ≥ 80% on new files, overall ≥ 98%.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve lint formatting and mypy type issues"
```

(Skip if no fixes needed.)

---

### Task 12: Update progress tracking

**Files:**
- Modify: `project-management/PROGRESS.md`
- Modify: `project-management/BACKLOG.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update PROGRESS.md**

Change TREND-003 row:
- Status: `Done`
- Branch: `` `feature/TREND-003-hackernews-integration` ``
- Plan: `[plan](../docs/superpowers/plans/2026-03-13-trend-003-hackernews-integration.md)`
- Spec: `[spec](../docs/superpowers/specs/2026-03-13-trend-003-hackernews-integration-design.md)`

- [ ] **Step 2: Update BACKLOG.md**

Add `— DONE` to TREND-003 heading. Add status and plan/spec fields.

- [ ] **Step 3: Update CLAUDE.md Current Status**

Update "Last completed" and "Next up" lines.

- [ ] **Step 4: Commit**

```bash
git add project-management/PROGRESS.md project-management/BACKLOG.md CLAUDE.md
git commit -m "docs: mark TREND-003 as Done in progress tracking"
```
