# TREND-002: Reddit Trend Source Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Reddit as a trend source — monitor subreddits via asyncpraw, deduplicate crossposts, score by comment velocity, and expose via `POST /api/v1/trends/reddit/fetch`.

**Architecture:** Client/Service/Router separation matching TREND-003 (HN). `RedditClient` wraps asyncpraw for per-subreddit fetching. `RedditService` orchestrates iteration, crosspost dedup, domain filtering, scoring, and `RawTopic` mapping. Endpoint added to existing `trends_router`.

**Tech Stack:** asyncpraw (async Reddit API), difflib.SequenceMatcher (crosspost fuzzy dedup), pydantic SecretStr, structlog

**Spec:** [`docs/superpowers/specs/2026-03-14-trend-002-reddit-trend-source-design.md`](../specs/2026-03-14-trend-002-reddit-trend-source-design.md)

**Existing patterns to follow:**
- Client: `src/services/hackernews_client.py` (62 lines)
- Service: `src/services/hackernews.py` (142 lines)
- Router: `src/api/routers/trends.py` (118 lines)
- Schemas: `src/api/schemas/trends.py` (29 lines)
- Settings: `src/config/settings.py` (39 lines)
- Mock: `tests/unit/services/conftest.py` (84 lines)
- Client tests: `tests/unit/services/test_hackernews_client.py` (116 lines)
- Service tests: `tests/unit/services/test_hackernews.py` (246 lines)
- Schema tests: `tests/unit/api/test_trend_schemas.py` (50 lines)
- Endpoint tests: `tests/unit/api/test_trend_endpoints.py` (194 lines)

---

## Chunk 1: Foundation (dependencies, settings, schemas, mock)

### Task 1: Add asyncpraw dependency and mypy override

**Files:**
- Modify: `pyproject.toml`

- [x] **Step 1: Add asyncpraw to dependencies**

In `pyproject.toml`, add `"asyncpraw>=7.7.0"` to `dependencies` list after `"pytrends>=4.9.0"`:

```python
    "pytrends>=4.9.0",
    "asyncpraw>=7.7.0",
]
```

- [x] **Step 2: Add mypy override for asyncpraw**

In `pyproject.toml`, add a new `[[tool.mypy.overrides]]` section after the existing pytrends override:

```toml
[[tool.mypy.overrides]]
module = "asyncpraw.*"
ignore_missing_imports = true
```

- [x] **Step 3: Install the dependency**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pip install asyncpraw>=7.7.0`
Expected: Successful install

- [x] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add asyncpraw dependency and mypy override for TREND-002"
```

---

### Task 2: Add Reddit settings to configuration

**Files:**
- Modify: `src/config/settings.py`

- [x] **Step 1: Add Reddit settings fields**

Add after the Google Trends settings block (line 38) in `src/config/settings.py`:

```python
    # Reddit integration
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "cognify:v1.0 (by /u/cognify-bot)"
    reddit_default_subreddits: list[str] = [
        "cybersecurity",
        "programming",
        "netsec",
        "technology",
    ]
    reddit_score_cap: float = 1000.0
    reddit_request_timeout: float = 15.0
```

Note: Using plain `str` for `reddit_client_secret` to stay consistent with existing `jwt_private_key`/`jwt_public_key` pattern. The spec called for `SecretStr` but the codebase doesn't use it yet — we'll follow the existing convention and migrate all secrets to `SecretStr` in a follow-up tech-debt ticket.

- [x] **Step 2: Verify settings load**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify python -c "from src.config.settings import Settings; s = Settings(); print(s.reddit_default_subreddits)"`
Expected: `['cybersecurity', 'programming', 'netsec', 'technology']`

- [x] **Step 3: Commit**

```bash
git add src/config/settings.py
git commit -m "feat(trend-002): add Reddit integration settings"
```

---

### Task 3: Add Reddit request/response schemas

**Files:**
- Modify: `src/api/schemas/trends.py`
- Test: `tests/unit/api/test_trend_schemas.py`

- [x] **Step 1: Write failing schema tests**

Append to `tests/unit/api/test_trend_schemas.py`:

```python
from src.api.schemas.trends import RedditFetchRequest, RedditFetchResponse


class TestRedditFetchRequest:
    def test_valid_request_defaults(self) -> None:
        req = RedditFetchRequest(domain_keywords=["cyber"])
        assert req.domain_keywords == ["cyber"]
        assert req.subreddits is None
        assert req.max_results == 20
        assert req.sort == "hot"
        assert req.time_filter == "day"

    def test_custom_values(self) -> None:
        req = RedditFetchRequest(
            domain_keywords=["ai", "ml"],
            subreddits=["machinelearning", "artificial"],
            max_results=50,
            sort="top",
            time_filter="week",
        )
        assert req.subreddits == ["machinelearning", "artificial"]
        assert req.max_results == 50
        assert req.sort == "top"
        assert req.time_filter == "week"

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RedditFetchRequest(domain_keywords=[])

    def test_max_results_too_high(self) -> None:
        with pytest.raises(ValidationError):
            RedditFetchRequest(domain_keywords=["x"], max_results=101)

    def test_max_results_too_low(self) -> None:
        with pytest.raises(ValidationError):
            RedditFetchRequest(domain_keywords=["x"], max_results=0)

    def test_invalid_sort_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RedditFetchRequest(domain_keywords=["x"], sort="banana")

    def test_invalid_time_filter_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RedditFetchRequest(domain_keywords=["x"], time_filter="year")

    def test_too_many_subreddits_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RedditFetchRequest(
                domain_keywords=["x"],
                subreddits=["sub"] * 21,
            )


class TestRedditFetchResponse:
    def test_response_shape(self) -> None:
        resp = RedditFetchResponse(
            topics=[],
            total_fetched=50,
            total_after_dedup=40,
            total_after_filter=10,
            subreddits_scanned=4,
        )
        assert resp.total_fetched == 50
        assert resp.total_after_dedup == 40
        assert resp.total_after_filter == 10
        assert resp.subreddits_scanned == 4
        assert resp.topics == []
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_trend_schemas.py::TestRedditFetchRequest -v`
Expected: FAIL — `ImportError: cannot import name 'RedditFetchRequest'`

- [x] **Step 3: Implement schemas**

Add to `src/api/schemas/trends.py` after the existing GT schemas:

```python
from typing import Literal


class RedditFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    subreddits: list[str] | None = Field(
        default=None,
        max_length=20,
    )
    max_results: int = Field(default=20, ge=1, le=100)
    sort: Literal["hot", "top", "new", "rising"] = "hot"
    time_filter: Literal["hour", "day", "week"] = "day"


class RedditFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_dedup: int
    total_after_filter: int
    subreddits_scanned: int
```

Note: Add the `Literal` import at the top of the file alongside the existing `pydantic` imports.

- [x] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_trend_schemas.py -v`
Expected: All tests PASS (existing HN/GT schema tests + new Reddit schema tests)

- [x] **Step 5: Commit**

```bash
git add src/api/schemas/trends.py tests/unit/api/test_trend_schemas.py
git commit -m "feat(trend-002): add Reddit request/response schemas with validation"
```

---

## Chunk 2: Reddit Client + Mock

### Task 4: Implement RedditClient with asyncpraw

**Files:**
- Create: `src/services/reddit_client.py`
- Test: `tests/unit/services/test_reddit_client.py`

- [x] **Step 1: Write failing client tests**

Create `tests/unit/services/test_reddit_client.py`:

```python
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.reddit_client import (
    RedditAPIError,
    RedditClient,
)


async def _async_iter(items: list[Any]) -> AsyncIterator[Any]:
    """Helper: wrap a list into an async iterator for mocking asyncpraw listings."""
    for item in items:
        yield item


def _mock_submission(**overrides: object) -> MagicMock:
    """Create a mock asyncpraw Submission object."""
    defaults = {
        "id": "abc123",
        "title": "Test Post",
        "selftext": "Some text content",
        "score": 100,
        "num_comments": 50,
        "created_utc": 1710000000.0,
        "url": "https://example.com/article",
        "permalink": "/r/test/comments/abc123/test_post/",
        "subreddit": MagicMock(display_name="test"),
        "upvote_ratio": 0.95,
        "crosspost_parent_list": [],
    }
    defaults.update(overrides)
    sub = MagicMock()
    for key, val in defaults.items():
        setattr(sub, key, val)
    return sub


class TestFetchSubredditPosts:
    async def test_successful_fetch(self) -> None:
        mock_sub = _mock_submission()
        mock_subreddit = MagicMock()
        mock_subreddit.hot = MagicMock(
            return_value=_async_iter([mock_sub]),
        )

        mock_reddit = AsyncMock()
        mock_reddit.subreddit = AsyncMock(return_value=mock_subreddit)

        with patch(
            "src.services.reddit_client.asyncpraw.Reddit",
            return_value=mock_reddit,
        ):
            client = RedditClient(
                client_id="test",
                client_secret="test",
                user_agent="test",
                timeout=5.0,
            )
            posts = await client.fetch_subreddit_posts(
                "test", "hot", "day", 10,
            )

        assert len(posts) == 1
        assert posts[0]["title"] == "Test Post"
        assert posts[0]["score"] == 100
        assert posts[0]["subreddit"] == "test"

    async def test_empty_subreddit(self) -> None:
        mock_subreddit = MagicMock()
        mock_subreddit.hot = MagicMock(
            return_value=_async_iter([]),
        )

        mock_reddit = AsyncMock()
        mock_reddit.subreddit = AsyncMock(return_value=mock_subreddit)

        with patch(
            "src.services.reddit_client.asyncpraw.Reddit",
            return_value=mock_reddit,
        ):
            client = RedditClient(
                client_id="test",
                client_secret="test",
                user_agent="test",
                timeout=5.0,
            )
            posts = await client.fetch_subreddit_posts(
                "empty", "hot", "day", 10,
            )

        assert posts == []

    async def test_api_error_raises(self) -> None:
        mock_reddit = AsyncMock()
        mock_reddit.subreddit = AsyncMock(
            side_effect=Exception("API failure"),
        )

        with patch(
            "src.services.reddit_client.asyncpraw.Reddit",
            return_value=mock_reddit,
        ):
            client = RedditClient(
                client_id="test",
                client_secret="test",
                user_agent="test",
                timeout=5.0,
            )
            with pytest.raises(RedditAPIError, match="API failure"):
                await client.fetch_subreddit_posts(
                    "test", "hot", "day", 10,
                )
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.reddit_client'`

- [x] **Step 3: Implement RedditClient**

Create `src/services/reddit_client.py`:

```python
from typing import TypedDict

import asyncpraw  # type: ignore[import-untyped]


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


class RedditAPIError(Exception):
    """Raised when the Reddit API is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class RedditClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        timeout: float,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._timeout = timeout

    async def fetch_subreddit_posts(
        self,
        subreddit: str,
        sort: str,
        time_filter: str,
        limit: int,
    ) -> list[RedditPostResponse]:
        try:
            reddit = asyncpraw.Reddit(
                client_id=self._client_id,
                client_secret=self._client_secret,
                user_agent=self._user_agent,
                requestor_kwargs={"timeout": self._timeout},
            )
            try:
                sub = await reddit.subreddit(subreddit)
                fetch_fn = getattr(sub, sort)
                kwargs: dict[str, object] = {"limit": limit}
                if sort == "top":
                    kwargs["time_filter"] = time_filter
                posts: list[RedditPostResponse] = []
                async for submission in fetch_fn(**kwargs):
                    crosspost_parent: str | None = None
                    if hasattr(submission, "crosspost_parent_list"):
                        parents = submission.crosspost_parent_list
                        if parents:
                            crosspost_parent = parents[0].get("id")
                    posts.append(
                        RedditPostResponse(
                            id=submission.id,
                            title=submission.title,
                            selftext=submission.selftext or "",
                            score=submission.score,
                            num_comments=submission.num_comments,
                            created_utc=submission.created_utc,
                            url=submission.url,
                            permalink=submission.permalink,
                            subreddit=submission.subreddit.display_name,
                            upvote_ratio=submission.upvote_ratio,
                            crosspost_parent=crosspost_parent,
                        ),
                    )
                return posts
            finally:
                await reddit.close()
        except RedditAPIError:
            raise
        except Exception as exc:
            raise RedditAPIError(
                f"Reddit API error: {exc}",
            ) from exc
```

- [x] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit_client.py -v`
Expected: All PASS

- [x] **Step 5: Add MockRedditClient to test conftest**

Add the import at the top of `tests/unit/services/conftest.py`:

```python
from src.services.reddit_client import RedditClient, RedditPostResponse
```

Then add the mock class after `MockGoogleTrendsClient`:

```python
class MockRedditClient(RedditClient):
    """Returns canned posts per subreddit for deterministic testing."""

    def __init__(
        self,
        posts: dict[str, list[RedditPostResponse]] | None = None,
    ) -> None:
        super().__init__(
            client_id="mock",
            client_secret="mock",
            user_agent="mock",
            timeout=1.0,
        )
        self._posts = posts or {}

    async def fetch_subreddit_posts(
        self,
        subreddit: str,
        sort: str,
        time_filter: str,
        limit: int,
    ) -> list[RedditPostResponse]:
        return self._posts.get(subreddit, [])[:limit]
```

- [x] **Step 6: Commit**

```bash
git add src/services/reddit_client.py tests/unit/services/test_reddit_client.py tests/unit/services/conftest.py
git commit -m "feat(trend-002): implement RedditClient with asyncpraw wrapper"
```

---

## Chunk 3: Reddit Service (scoring, dedup, filtering, mapping)

### Task 5: Implement scoring and velocity calculations

**Files:**
- Create: `src/services/reddit.py`
- Test: `tests/unit/services/test_reddit.py`

- [x] **Step 1: Write failing score/velocity tests**

Create `tests/unit/services/test_reddit.py`:

```python
from datetime import UTC, datetime

import pytest

from src.services.reddit import RedditService
from src.services.reddit_client import RedditAPIError, RedditPostResponse
from tests.unit.services.conftest import MockRedditClient


def _post(**overrides: object) -> RedditPostResponse:
    base: RedditPostResponse = {
        "id": "abc123",
        "title": "Test Post",
        "selftext": "Some content",
        "score": 100,
        "num_comments": 50,
        "created_utc": 1710000000.0,
        "url": "https://example.com",
        "permalink": "/r/test/comments/abc123/test_post/",
        "subreddit": "test",
        "upvote_ratio": 0.95,
        "crosspost_parent": None,
    }
    result: dict[str, object] = {**base, **overrides}
    return result  # type: ignore[return-value]


class TestScoreNormalization:
    def test_standard_score(self) -> None:
        """score=200, 100 comments, 2h ago, cap=1000.
        cv=50, rb=100*exp(-ln2/12*2)≈89.1, raw=(60+25+17.8)=102.8
        trend=(102.8/1000)*100=10.28"""
        score = RedditService.calculate_score(
            score=200,
            num_comments=100,
            hours_ago=2.0,
            score_cap=1000.0,
        )
        assert round(score, 1) == 10.3

    def test_zero_comments_zero_score(self) -> None:
        """score=0, 0 comments, 1h ago.
        cv=0, rb≈94.4, raw=(0+0+18.9)=18.9
        trend=(18.9/1000)*100=1.89"""
        score = RedditService.calculate_score(
            score=0,
            num_comments=0,
            hours_ago=1.0,
            score_cap=1000.0,
        )
        assert round(score, 1) == 1.9

    def test_high_score_capped_at_100(self) -> None:
        """Huge values should cap at 100."""
        score = RedditService.calculate_score(
            score=50000,
            num_comments=10000,
            hours_ago=0.5,
            score_cap=1000.0,
        )
        assert score == 100.0

    def test_very_recent_clamps_comment_velocity(self) -> None:
        """hours_ago < 1 → clamped to 1 for comment_velocity denominator.
        recency_bonus still differs (uses raw hours_ago), so scores differ slightly."""
        score_recent = RedditService.calculate_score(
            score=100,
            num_comments=200,
            hours_ago=0.1,
            score_cap=1000.0,
        )
        score_1h = RedditService.calculate_score(
            score=100,
            num_comments=200,
            hours_ago=1.0,
            score_cap=1000.0,
        )
        # Both use comment_velocity = 200/1.0 = 200 (clamped),
        # but recency_bonus differs slightly. Scores close but not equal.
        assert abs(score_recent - score_1h) < 1.0
        assert score_recent > score_1h  # more recent → higher recency_bonus


class TestVelocityCalculation:
    def test_standard_velocity(self) -> None:
        """100 score, 2 hours → 50"""
        vel = RedditService.calculate_velocity(100, 2.0)
        assert vel == 50.0

    def test_very_recent_clamped_to_1h(self) -> None:
        """100 score, 0.1 hours → clamped to 1 → 100"""
        vel = RedditService.calculate_velocity(100, 0.1)
        assert vel == 100.0

    def test_old_post(self) -> None:
        """100 score, 20 hours → 5"""
        vel = RedditService.calculate_velocity(100, 20.0)
        assert vel == 5.0

    def test_zero_score(self) -> None:
        vel = RedditService.calculate_velocity(0, 5.0)
        assert vel == 0.0
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit.py::TestScoreNormalization -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.reddit'`

- [x] **Step 3: Implement score/velocity methods**

Create `src/services/reddit.py` with initial scoring methods:

```python
import math
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import RedditFetchResponse
from src.services.reddit_client import (
    RedditAPIError,
    RedditClient,
    RedditPostResponse,
)

logger = structlog.get_logger()

# 12-hour half-life for recency decay
_RECENCY_LAMBDA = math.log(2) / 12


class RedditService:
    def __init__(
        self,
        client: RedditClient,
        score_cap: float,
    ) -> None:
        self._client = client
        self._score_cap = score_cap

    @staticmethod
    def calculate_score(
        score: int,
        num_comments: int,
        hours_ago: float,
        score_cap: float,
    ) -> float:
        hours = max(1.0, hours_ago)
        comment_velocity = num_comments / hours
        recency_bonus = 100.0 * math.exp(
            -_RECENCY_LAMBDA * hours_ago,
        )
        raw = (
            (score * 0.3)
            + (comment_velocity * 0.5)
            + (recency_bonus * 0.2)
        )
        return min(100.0, (raw / score_cap) * 100)

    @staticmethod
    def calculate_velocity(
        score: int,
        hours_ago: float,
    ) -> float:
        hours = max(1.0, hours_ago)
        return score / hours
```

- [x] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit.py::TestScoreNormalization tests/unit/services/test_reddit.py::TestVelocityCalculation -v`
Expected: All PASS

- [x] **Step 5: Commit**

```bash
git add src/services/reddit.py tests/unit/services/test_reddit.py
git commit -m "feat(trend-002): add Reddit scoring and velocity calculations"
```

---

### Task 6: Implement crosspost deduplication

**Files:**
- Modify: `src/services/reddit.py`
- Modify: `tests/unit/services/test_reddit.py`

- [x] **Step 1: Write failing dedup tests**

Append to `tests/unit/services/test_reddit.py`:

```python
class TestCrosspostDedup:
    def test_crosspost_parent_groups(self) -> None:
        """Posts with same crosspost_parent merged, highest score kept."""
        posts = [
            _post(id="1", title="Post A", score=50, crosspost_parent="parent_1", subreddit="sub1"),
            _post(id="2", title="Post A copy", score=200, crosspost_parent="parent_1", subreddit="sub2"),
            _post(id="3", title="Unique post", score=100, crosspost_parent=None, subreddit="sub1"),
        ]
        deduped, count = RedditService.deduplicate_crossposts(posts)
        assert len(deduped) == 2
        # The parent_1 group kept highest score (200)
        parent_group = [p for p in deduped if p["crosspost_parent"] == "parent_1"]
        assert len(parent_group) == 1
        assert parent_group[0]["score"] == 200

    def test_fuzzy_title_groups(self) -> None:
        """Posts with very similar titles (>0.85 ratio) merged."""
        posts = [
            _post(id="1", title="Breaking: Major cybersecurity breach at Company X", score=300, subreddit="sub1"),
            _post(id="2", title="Breaking: Major cybersecurity breach at Company X!", score=100, subreddit="sub2"),
            _post(id="3", title="Completely different topic", score=50, subreddit="sub1"),
        ]
        deduped, count = RedditService.deduplicate_crossposts(posts)
        assert len(deduped) == 2
        # Similar titles merged, highest score kept
        breach_post = [p for p in deduped if "breach" in p["title"]]
        assert len(breach_post) == 1
        assert breach_post[0]["score"] == 300

    def test_unique_posts_preserved(self) -> None:
        """All unique posts pass through unchanged."""
        posts = [
            _post(id="1", title="Topic A", score=100),
            _post(id="2", title="Topic B", score=200),
            _post(id="3", title="Topic C", score=300),
        ]
        deduped, count = RedditService.deduplicate_crossposts(posts)
        assert len(deduped) == 3
        assert count == 0

    def test_empty_input(self) -> None:
        deduped, count = RedditService.deduplicate_crossposts([])
        assert deduped == []
        assert count == 0

    def test_subreddit_count_tracked(self) -> None:
        """Merged groups report correct subreddit count."""
        posts = [
            _post(id="1", title="Same Post", score=50, crosspost_parent="parent_1", subreddit="sub1"),
            _post(id="2", title="Same Post", score=100, crosspost_parent="parent_1", subreddit="sub2"),
            _post(id="3", title="Same Post", score=75, crosspost_parent="parent_1", subreddit="sub3"),
        ]
        deduped, count = RedditService.deduplicate_crossposts(posts)
        assert len(deduped) == 1
        assert count == 2  # 3 posts → 1 = 2 removed
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit.py::TestCrosspostDedup -v`
Expected: FAIL — `AttributeError: type object 'RedditService' has no attribute 'deduplicate_crossposts'`

- [x] **Step 3: Implement dedup method**

Add to `RedditService` class in `src/services/reddit.py`:

```python
    @staticmethod
    def deduplicate_crossposts(
        posts: list[RedditPostResponse],
    ) -> tuple[list[RedditPostResponse], int]:
        """Two-pass dedup: crosspost_parent IDs then fuzzy title match.
        Returns (deduped_posts, removed_count)."""
        if not posts:
            return [], 0

        # Pass 1: group by crosspost_parent
        parent_groups: dict[str, list[RedditPostResponse]] = {}
        no_parent: list[RedditPostResponse] = []
        for post in posts:
            parent = post["crosspost_parent"]
            if parent:
                parent_groups.setdefault(parent, []).append(post)
            else:
                no_parent.append(post)

        # Keep highest score per parent group
        survivors: list[RedditPostResponse] = []
        for group in parent_groups.values():
            best = max(group, key=lambda p: p["score"])
            survivors.append(best)

        # Pass 2: fuzzy title match on remaining posts
        merged_into: dict[int, int] = {}  # index → group leader index
        for i, post_a in enumerate(no_parent):
            if i in merged_into:
                continue
            for j in range(i + 1, len(no_parent)):
                if j in merged_into:
                    continue
                ratio = SequenceMatcher(
                    None,
                    post_a["title"].lower(),
                    no_parent[j]["title"].lower(),
                ).ratio()
                if ratio > 0.85:
                    merged_into[j] = i

        # Build fuzzy groups
        fuzzy_groups: dict[int, list[int]] = {}
        for j, leader in merged_into.items():
            fuzzy_groups.setdefault(leader, [leader]).append(j)

        # Keep highest score per fuzzy group
        seen_leaders: set[int] = set()
        for i, post in enumerate(no_parent):
            if i in merged_into:
                continue
            if i in fuzzy_groups:
                seen_leaders.add(i)
                group_indices = fuzzy_groups[i]
                group_posts = [no_parent[idx] for idx in group_indices]
                best = max(group_posts, key=lambda p: p["score"])
                survivors.append(best)
            else:
                survivors.append(post)

        original_count = len(posts)
        removed = original_count - len(survivors)
        return survivors, removed
```

- [x] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit.py::TestCrosspostDedup -v`
Expected: All PASS

- [x] **Step 5: Commit**

```bash
git add src/services/reddit.py tests/unit/services/test_reddit.py
git commit -m "feat(trend-002): implement crosspost deduplication with fuzzy title matching"
```

---

### Task 7: Implement domain filtering and field mapping

**Files:**
- Modify: `src/services/reddit.py`
- Modify: `tests/unit/services/test_reddit.py`

- [x] **Step 1: Write failing filter and mapping tests**

Append to `tests/unit/services/test_reddit.py`:

```python
class TestDomainFiltering:
    def test_matches_title(self) -> None:
        post = _post(title="Cybersecurity breach report")
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_matches_selftext(self) -> None:
        post = _post(
            title="A normal title",
            selftext="Deep dive into cybersecurity trends",
        )
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 1

    def test_matches_subreddit_name(self) -> None:
        post = _post(
            title="A normal title",
            selftext="Normal text",
            subreddit="cybersecurity",
        )
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 1

    def test_case_insensitive(self) -> None:
        post = _post(title="CYBERSECURITY NEWS")
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        post = _post(title="Cooking recipes", selftext="Delicious food", subreddit="cooking")
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 0

    def test_multiple_keywords_any_match(self) -> None:
        post = _post(title="New AI model released")
        matched = RedditService.filter_by_domain(
            [post], ["cyber", "AI"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]


class TestMapToRawTopic:
    def test_full_mapping(self) -> None:
        post = _post(
            id="abc123",
            title="Cyber Attack Analysis",
            selftext="Detailed analysis of the attack.",
            score=150,
            num_comments=40,
            created_utc=1710000000.0,
            permalink="/r/cybersecurity/comments/abc123/cyber_attack/",
            subreddit="cybersecurity",
        )
        topic = RedditService.map_to_raw_topic(
            post,
            matched_keywords=["cyber"],
            score_cap=1000.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.title == "Cyber Attack Analysis"
        assert topic.source == "reddit"
        assert topic.external_url == "https://www.reddit.com/r/cybersecurity/comments/abc123/cyber_attack/"
        assert topic.domain_keywords == ["cyber"]
        assert topic.description == "Detailed analysis of the attack."
        assert 0 <= topic.trend_score <= 100
        assert topic.velocity > 0

    def test_empty_selftext(self) -> None:
        post = _post(selftext="")
        topic = RedditService.map_to_raw_topic(
            post,
            matched_keywords=["test"],
            score_cap=1000.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.description == ""

    def test_long_selftext_truncated(self) -> None:
        post = _post(selftext="x" * 500)
        topic = RedditService.map_to_raw_topic(
            post,
            matched_keywords=["test"],
            score_cap=1000.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert len(topic.description) == 200

    def test_zero_score_and_comments(self) -> None:
        post = _post(score=0, num_comments=0)
        topic = RedditService.map_to_raw_topic(
            post,
            matched_keywords=["test"],
            score_cap=1000.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.velocity == 0.0
        assert topic.trend_score >= 0  # recency_bonus still contributes
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit.py::TestDomainFiltering tests/unit/services/test_reddit.py::TestMapToRawTopic -v`
Expected: FAIL — `AttributeError: type object 'RedditService' has no attribute 'filter_by_domain'`

- [x] **Step 3: Implement filter_by_domain and map_to_raw_topic**

Add to `RedditService` class in `src/services/reddit.py`:

```python
    @staticmethod
    def filter_by_domain(
        posts: list[RedditPostResponse],
        domain_keywords: list[str],
    ) -> list[tuple[RedditPostResponse, list[str]]]:
        results: list[tuple[RedditPostResponse, list[str]]] = []
        for post in posts:
            title = post["title"].lower()
            selftext = post["selftext"].lower()
            subreddit = post["subreddit"].lower()
            matched = [
                kw
                for kw in domain_keywords
                if kw.lower() in title
                or kw.lower() in selftext
                or kw.lower() in subreddit
            ]
            if matched:
                results.append((post, matched))
        return results

    @staticmethod
    def map_to_raw_topic(
        post: RedditPostResponse,
        matched_keywords: list[str],
        score_cap: float,
        now: datetime | None = None,
    ) -> RawTopic:
        if now is None:
            now = datetime.now(UTC)
        created = datetime.fromtimestamp(
            post["created_utc"],
            tz=UTC,
        )
        hours_ago = (now - created).total_seconds() / 3600
        return RawTopic(
            title=post["title"],
            description=post["selftext"][:200],
            source="reddit",
            external_url=f"https://www.reddit.com{post['permalink']}",
            trend_score=RedditService.calculate_score(
                post["score"],
                post["num_comments"],
                hours_ago,
                score_cap,
            ),
            discovered_at=created,
            velocity=RedditService.calculate_velocity(
                post["score"],
                hours_ago,
            ),
            domain_keywords=matched_keywords,
        )
```

- [x] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit.py::TestDomainFiltering tests/unit/services/test_reddit.py::TestMapToRawTopic -v`
Expected: All PASS

- [x] **Step 5: Commit**

```bash
git add src/services/reddit.py tests/unit/services/test_reddit.py
git commit -m "feat(trend-002): implement domain filtering and RawTopic field mapping"
```

---

### Task 8: Implement fetch_and_normalize pipeline

**Files:**
- Modify: `src/services/reddit.py`
- Modify: `tests/unit/services/test_reddit.py`

- [x] **Step 1: Write failing pipeline tests**

Append to `tests/unit/services/test_reddit.py`:

```python
# Note: Pipeline tests use default created_utc timestamps. Since fetch_and_normalize
# calls datetime.now(UTC) internally (no now= override), scores will be based on
# actual wall-clock time. This is consistent with the HN test pattern. Tests assert
# on structure and counts rather than exact score values.


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        posts: dict[str, list[RedditPostResponse]] = {
            "cybersecurity": [
                _post(id="1", title="Cybersecurity breach", score=200, num_comments=50, subreddit="cybersecurity"),
                _post(id="2", title="Cooking recipes", score=300, num_comments=100, subreddit="cybersecurity"),
            ],
            "netsec": [
                _post(id="3", title="Network security tips", score=150, num_comments=30, subreddit="netsec"),
            ],
        }
        mock_client = MockRedditClient(posts=posts)
        service = RedditService(
            client=mock_client,
            score_cap=1000.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber", "security"],
            subreddits=["cybersecurity", "netsec"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.total_fetched == 3
        assert result.subreddits_scanned == 2
        assert result.total_after_filter >= 1  # at least cyber/security posts match
        assert all(t.source == "reddit" for t in result.topics)

    async def test_empty_results(self) -> None:
        mock_client = MockRedditClient(posts={})
        service = RedditService(
            client=mock_client,
            score_cap=1000.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            subreddits=["empty"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.total_fetched == 0
        assert result.topics == []

    async def test_no_matches_after_filter(self) -> None:
        posts: dict[str, list[RedditPostResponse]] = {
            "cooking": [
                _post(id="1", title="Best recipes", subreddit="cooking"),
            ],
        }
        mock_client = MockRedditClient(posts=posts)
        service = RedditService(
            client=mock_client,
            score_cap=1000.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            subreddits=["cooking"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.total_fetched == 1
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_crosspost_dedup_in_pipeline(self) -> None:
        """Same crosspost_parent across subreddits → deduped."""
        posts: dict[str, list[RedditPostResponse]] = {
            "cybersecurity": [
                _post(id="1", title="Cyber breach", score=100, crosspost_parent="parent_1", subreddit="cybersecurity"),
            ],
            "netsec": [
                _post(id="2", title="Cyber breach copy", score=200, crosspost_parent="parent_1", subreddit="netsec"),
            ],
        }
        mock_client = MockRedditClient(posts=posts)
        service = RedditService(
            client=mock_client,
            score_cap=1000.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            subreddits=["cybersecurity", "netsec"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.total_fetched == 2
        assert result.total_after_dedup == 1

    async def test_partial_subreddit_failure(self) -> None:
        """One subreddit fails, others still processed."""

        class PartialFailClient(MockRedditClient):
            async def fetch_subreddit_posts(
                self,
                subreddit: str,
                sort: str,
                time_filter: str,
                limit: int,
            ) -> list[RedditPostResponse]:
                if subreddit == "private_sub":
                    raise RedditAPIError("Subreddit is private")
                return await super().fetch_subreddit_posts(
                    subreddit, sort, time_filter, limit,
                )

        posts: dict[str, list[RedditPostResponse]] = {
            "cybersecurity": [
                _post(id="1", title="Cyber news", score=100, subreddit="cybersecurity"),
            ],
        }
        client = PartialFailClient(posts=posts)
        service = RedditService(client=client, score_cap=1000.0)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            subreddits=["cybersecurity", "private_sub"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.subreddits_scanned == 1
        assert result.total_fetched == 1

    async def test_all_subreddits_fail_raises(self) -> None:
        """All subreddits fail → RedditAPIError raised."""

        class AllFailClient(MockRedditClient):
            async def fetch_subreddit_posts(
                self,
                subreddit: str,
                sort: str,
                time_filter: str,
                limit: int,
            ) -> list[RedditPostResponse]:
                raise RedditAPIError("API down")

        client = AllFailClient(posts={})
        service = RedditService(client=client, score_cap=1000.0)
        with pytest.raises(RedditAPIError, match="All subreddits failed"):
            await service.fetch_and_normalize(
                domain_keywords=["cyber"],
                subreddits=["sub1", "sub2"],
                max_results=20,
                sort="hot",
                time_filter="day",
            )
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit.py::TestFetchAndNormalize -v`
Expected: FAIL — `AttributeError: ... has no attribute 'fetch_and_normalize'`

- [x] **Step 3: Implement fetch_and_normalize**

Add to `RedditService` class in `src/services/reddit.py`:

```python
    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        subreddits: list[str],
        max_results: int,
        sort: str,
        time_filter: str,
    ) -> RedditFetchResponse:
        start = time.monotonic()
        logger.info(
            "reddit_fetch_started",
            domain_keywords=domain_keywords,
            subreddits=subreddits,
            max_results=max_results,
            sort=sort,
        )

        all_posts: list[RedditPostResponse] = []
        scanned = 0
        for subreddit in subreddits:
            try:
                posts = await self._client.fetch_subreddit_posts(
                    subreddit,
                    sort,
                    time_filter,
                    max_results,
                )
                all_posts.extend(posts)
                scanned += 1
            except RedditAPIError:
                logger.warning(
                    "reddit_subreddit_failed",
                    subreddit=subreddit,
                )
                continue

        if scanned == 0:
            raise RedditAPIError(
                "All subreddits failed",
            )

        total_fetched = len(all_posts)

        deduped, removed = self.deduplicate_crossposts(all_posts)
        logger.debug(
            "reddit_crossposts_deduped",
            before_count=total_fetched,
            after_count=len(deduped),
            groups_merged=removed,
        )

        filtered = self.filter_by_domain(deduped, domain_keywords)
        logger.debug(
            "reddit_posts_filtered",
            before_count=len(deduped),
            after_count=len(filtered),
            domain_keywords=domain_keywords,
        )

        topics = sorted(
            [
                self.map_to_raw_topic(
                    post,
                    kws,
                    self._score_cap,
                )
                for post, kws in filtered
            ],
            key=lambda t: t.trend_score,
            reverse=True,
        )

        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "reddit_fetch_completed",
            total_fetched=total_fetched,
            total_after_dedup=len(deduped),
            total_after_filter=len(topics),
            subreddits_scanned=scanned,
            duration_ms=duration_ms,
        )

        return RedditFetchResponse(
            topics=topics,
            total_fetched=total_fetched,
            total_after_dedup=len(deduped),
            total_after_filter=len(topics),
            subreddits_scanned=scanned,
        )
```

- [x] **Step 4: Run all service tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_reddit.py -v`
Expected: All PASS

- [x] **Step 5: Commit**

```bash
git add src/services/reddit.py tests/unit/services/test_reddit.py
git commit -m "feat(trend-002): implement fetch_and_normalize pipeline with partial failure handling"
```

---

## Chunk 4: API Endpoint and Integration

### Task 9: Add Reddit endpoint to trends router

**Files:**
- Modify: `src/api/routers/trends.py`
- Modify: `tests/unit/api/test_trend_endpoints.py`

- [x] **Step 1: Write failing endpoint tests**

Append to `tests/unit/api/test_trend_endpoints.py`:

```python
from src.services.reddit_client import RedditPostResponse
from tests.unit.services.conftest import MockRedditClient


def _reddit_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "domain_keywords": ["cyber"],
        "subreddits": ["cybersecurity"],
        "max_results": 20,
        "sort": "hot",
        "time_filter": "day",
    }
    base.update(overrides)
    return base


SAMPLE_REDDIT_POSTS: dict[str, list[RedditPostResponse]] = {
    "cybersecurity": [
        {
            "id": "abc123",
            "title": "Cybersecurity Trends 2026",
            "selftext": "Analysis of trends.",
            "score": 150,
            "num_comments": 42,
            "created_utc": 1710000000.0,
            "url": "https://example.com/cyber",
            "permalink": "/r/cybersecurity/comments/abc123/cyber_trends/",
            "subreddit": "cybersecurity",
            "upvote_ratio": 0.95,
            "crosspost_parent": None,
        },
    ],
}


@pytest.fixture
def reddit_app(trend_settings: Settings) -> FastAPI:
    app = create_app(trend_settings)
    app.state.reddit_client = MockRedditClient(
        posts=SAMPLE_REDDIT_POSTS,
    )
    return app


@pytest.fixture
async def reddit_client(
    reddit_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=reddit_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestRedditEndpointAuth:
    async def test_no_token_returns_401(
        self,
        reddit_client: httpx.AsyncClient,
    ) -> None:
        resp = await reddit_client.post(
            "/api/v1/trends/reddit/fetch",
            json=_reddit_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        reddit_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await reddit_client.post(
            "/api/v1/trends/reddit/fetch",
            json=_reddit_request(),
            headers=make_auth_header("viewer", trend_settings),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        reddit_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await reddit_client.post(
            "/api/v1/trends/reddit/fetch",
            json=_reddit_request(),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        reddit_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await reddit_client.post(
            "/api/v1/trends/reddit/fetch",
            json=_reddit_request(),
            headers=make_auth_header("admin", trend_settings),
        )
        assert resp.status_code == 200


class TestRedditEndpointValidation:
    async def test_empty_keywords_returns_422(
        self,
        reddit_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await reddit_client.post(
            "/api/v1/trends/reddit/fetch",
            json=_reddit_request(domain_keywords=[]),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 422

    async def test_invalid_sort_returns_422(
        self,
        reddit_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await reddit_client.post(
            "/api/v1/trends/reddit/fetch",
            json=_reddit_request(sort="banana"),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 422


class TestRedditEndpointSuccess:
    async def test_response_shape(
        self,
        reddit_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await reddit_client.post(
            "/api/v1/trends/reddit/fetch",
            json=_reddit_request(),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "total_fetched" in data
        assert "total_after_dedup" in data
        assert "total_after_filter" in data
        assert "subreddits_scanned" in data

    async def test_no_matches_returns_empty(
        self,
        reddit_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        resp = await reddit_client.post(
            "/api/v1/trends/reddit/fetch",
            json=_reddit_request(domain_keywords=["cooking"]),
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_after_filter"] == 0

    async def test_uses_default_subreddits_when_none(
        self,
        reddit_client: httpx.AsyncClient,
        trend_settings: Settings,
    ) -> None:
        """When subreddits is null/omitted, uses settings defaults."""
        body = _reddit_request()
        del body["subreddits"]  # type: ignore[arg-type]
        resp = await reddit_client.post(
            "/api/v1/trends/reddit/fetch",
            json=body,
            headers=make_auth_header("editor", trend_settings),
        )
        assert resp.status_code == 200


class TestRedditEndpoint503:
    async def test_api_error_returns_503(
        self,
        trend_settings: Settings,
    ) -> None:
        from src.services.reddit_client import RedditAPIError

        class AllFailClient(MockRedditClient):
            async def fetch_subreddit_posts(
                self,
                subreddit: str,
                sort: str,
                time_filter: str,
                limit: int,
            ) -> list[RedditPostResponse]:
                raise RedditAPIError("API down")

        app = create_app(trend_settings)
        app.state.reddit_client = AllFailClient()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/trends/reddit/fetch",
                json=_reddit_request(),
                headers=make_auth_header(
                    "editor",
                    trend_settings,
                ),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "reddit_unavailable"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_trend_endpoints.py::TestRedditEndpointAuth -v`
Expected: FAIL — 404 (endpoint doesn't exist yet)

- [x] **Step 3: Implement the Reddit endpoint**

Add to `src/api/routers/trends.py`:

At the top, add imports:

```python
from src.api.schemas.trends import (
    GTFetchRequest,
    GTFetchResponse,
    HNFetchRequest,
    HNFetchResponse,
    RedditFetchRequest,
    RedditFetchResponse,
)
from src.services.reddit import RedditService
from src.services.reddit_client import (
    RedditAPIError,
    RedditClient,
)
```

Add the DI function:

```python
def _get_reddit_service(request: Request) -> RedditService:
    settings = request.app.state.settings
    # Test injection: tests set app.state.reddit_client to a mock.
    # In production, a fresh short-lived client is created per request.
    if hasattr(request.app.state, "reddit_client"):
        client = request.app.state.reddit_client
    else:
        client = RedditClient(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            timeout=settings.reddit_request_timeout,
        )
    return RedditService(
        client=client,
        score_cap=settings.reddit_score_cap,
    )
```

Add the endpoint:

```python
@limiter.limit("5/minute")
@trends_router.post(
    "/trends/reddit/fetch",
    response_model=RedditFetchResponse,
    summary="Fetch trending Reddit posts",
)
async def fetch_reddit(
    request: Request,
    body: RedditFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> RedditFetchResponse:
    settings = request.app.state.settings
    subreddits = body.subreddits or settings.reddit_default_subreddits
    service = _get_reddit_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            subreddits=subreddits,
            max_results=body.max_results,
            sort=body.sort,
            time_filter=body.time_filter,
        )
    except RedditAPIError as exc:
        logger.error(
            "reddit_api_error",
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="reddit_unavailable",
            message="Reddit API is not available",
        ) from exc
```

- [x] **Step 4: Run all endpoint tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_trend_endpoints.py -v`
Expected: All PASS (existing HN tests + new Reddit tests)

- [x] **Step 5: Commit**

```bash
git add src/api/routers/trends.py tests/unit/api/test_trend_endpoints.py
git commit -m "feat(trend-002): add POST /api/v1/trends/reddit/fetch endpoint"
```

---

### Task 10: Run full test suite and lint

**Files:** None (verification only)

- [x] **Step 1: Run full test suite**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest --cov=src --cov-report=term-missing -v`
Expected: All tests PASS, coverage ≥80% on new files

- [x] **Step 2: Run linter**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/ tests/ && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/ tests/`
Expected: No errors

- [x] **Step 3: Run mypy**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/`
Expected: No errors (asyncpraw module ignored via override)

- [x] **Step 4: Fix any issues found, commit**

If lint/type errors found, fix and commit:

```bash
git add -A
git commit -m "fix(trend-002): resolve lint and type check issues"
```

---

### Task 11: Update tracking files

**Files:**
- Modify: `project-management/PROGRESS.md`
- Modify: `project-management/BACKLOG.md`

- [x] **Step 1: Update PROGRESS.md**

Update the TREND-002 row in `project-management/PROGRESS.md`:

```markdown
| TREND-002 | Reddit Trend Source       | In Progress | `feature/TREND-002-reddit-trend-source` | [plan](../docs/superpowers/plans/2026-03-14-trend-002-reddit-trend-source.md) | [spec](../docs/superpowers/specs/2026-03-14-trend-002-reddit-trend-source-design.md) |
```

- [x] **Step 2: Update BACKLOG.md**

Update the TREND-002 entry in `project-management/BACKLOG.md` to add status and links:

```markdown
### TREND-002: Reddit Trend Source [Must]
- **Status**: In Progress (branch `feature/TREND-002-reddit-trend-source`)
- **Plan**: [`docs/superpowers/plans/2026-03-14-trend-002-reddit-trend-source.md`](../docs/superpowers/plans/2026-03-14-trend-002-reddit-trend-source.md)
- **Spec**: [`docs/superpowers/specs/2026-03-14-trend-002-reddit-trend-source-design.md`](../docs/superpowers/specs/2026-03-14-trend-002-reddit-trend-source-design.md)
```

- [x] **Step 3: Commit**

```bash
git add project-management/PROGRESS.md project-management/BACKLOG.md
git commit -m "docs: update tracking files — TREND-002 plan ready for execution"
```
