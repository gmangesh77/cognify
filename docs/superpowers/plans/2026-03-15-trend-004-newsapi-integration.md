# TREND-004: NewsAPI Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NewsAPI Top Headlines as a trend source, following the established client/service/router pattern.

**Architecture:** HTTP client (`httpx`) wraps the NewsAPI REST API. A service layer handles domain filtering, hybrid scoring (position + recency + keyword), two-pass deduplication (URL + fuzzy title), and normalization to `RawTopic`. A FastAPI endpoint exposes the fetch pipeline with auth and rate limiting.

**Tech Stack:** Python 3.12+, httpx, FastAPI, Pydantic, structlog, pytest

**Spec:** [`docs/superpowers/specs/2026-03-15-trend-004-newsapi-integration-design.md`](../specs/2026-03-15-trend-004-newsapi-integration-design.md)

**Test command:** `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest {path} -v`

**Lint command:** `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check {path} && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy {path}`

---

## Chunk 1: Client Layer

### Task 1: NewsAPI Client — Types, Error, and Client

**Files:**
- Create: `src/services/newsapi_client.py`
- Test: `tests/unit/services/test_newsapi_client.py`

- [ ] **Step 1: Create the client module with types, error, and client class**

Create `src/services/newsapi_client.py`:

```python
from typing import TypedDict

import httpx


class NewsAPISource(TypedDict):
    id: str | None
    name: str


class NewsAPIArticle(TypedDict):
    title: str
    description: str | None
    url: str
    urlToImage: str | None
    publishedAt: str
    source: NewsAPISource
    author: str | None
    content: str | None


class NewsAPIError(Exception):
    """Raised when the NewsAPI is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class NewsAPIClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    async def fetch_top_headlines(
        self,
        category: str,
        country: str,
        page_size: int,
    ) -> list[NewsAPIArticle]:
        params: dict[str, str | int] = {
            "category": category,
            "country": country,
            "pageSize": page_size,
            "apiKey": self._api_key,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
            ) as client:
                resp = await client.get(
                    f"{self._base_url}/top-headlines",
                    params=params,
                )
        except httpx.TimeoutException as exc:
            raise NewsAPIError(
                f"NewsAPI timed out: {exc}",
            ) from exc
        except httpx.ConnectError as exc:
            raise NewsAPIError(
                f"NewsAPI connection failed: {exc}",
            ) from exc
        if not resp.is_success:
            raise NewsAPIError(
                f"NewsAPI returned {resp.status_code}",
            )
        data = resp.json()
        if data.get("status") != "ok":
            code = data.get("code", "unknown")
            raise NewsAPIError(f"NewsAPI error: {code}")
        articles: list[NewsAPIArticle] = data.get("articles", [])
        return [
            a for a in articles if a.get("title") != "[Removed]"
        ]
```

- [ ] **Step 2: Write client tests**

Create `tests/unit/services/test_newsapi_client.py`:

```python
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.newsapi_client import (
    NewsAPIClient,
    NewsAPIError,
)

SAMPLE_ARTICLE = {
    "title": "Cybersecurity Alert",
    "description": "A major breach was reported.",
    "url": "https://example.com/cyber",
    "urlToImage": "https://example.com/img.jpg",
    "publishedAt": "2026-03-15T10:00:00Z",
    "source": {"id": "test-source", "name": "Test Source"},
    "author": "Jane Doe",
    "content": "Full article content here...",
}


class TestFetchTopHeadlines:
    async def test_successful_fetch(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"status": "ok", "articles": [SAMPLE_ARTICLE]},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            articles = await client.fetch_top_headlines(
                "technology", "us", 30,
            )
        assert len(articles) == 1
        assert articles[0]["title"] == "Cybersecurity Alert"

    async def test_empty_results(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"status": "ok", "articles": []},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            articles = await client.fetch_top_headlines(
                "technology", "us", 30,
            )
        assert articles == []

    async def test_api_error_status_raises(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"status": "error", "code": "apiKeyInvalid"},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="bad-key",
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(NewsAPIError, match="apiKeyInvalid"):
                await client.fetch_top_headlines(
                    "technology", "us", 30,
                )

    async def test_http_error_raises(self) -> None:
        mock_response = httpx.Response(
            500,
            json={"message": "server error"},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(NewsAPIError, match="500"):
                await client.fetch_top_headlines(
                    "technology", "us", 30,
                )

    async def test_timeout_raises(self) -> None:
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(NewsAPIError, match="timed out"):
                await client.fetch_top_headlines(
                    "technology", "us", 30,
                )

    async def test_connection_error_raises(self) -> None:
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(NewsAPIError, match="refused"):
                await client.fetch_top_headlines(
                    "technology", "us", 30,
                )

    async def test_removed_articles_filtered(self) -> None:
        articles = [
            SAMPLE_ARTICLE,
            {**SAMPLE_ARTICLE, "title": "[Removed]"},
        ]
        mock_response = httpx.Response(
            200,
            json={"status": "ok", "articles": articles},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            result = await client.fetch_top_headlines(
                "technology", "us", 30,
            )
        assert len(result) == 1
        assert result[0]["title"] == "Cybersecurity Alert"
```

- [ ] **Step 3: Run client tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_newsapi_client.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 4: Run lint on client module**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/services/newsapi_client.py && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/services/newsapi_client.py`
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add src/services/newsapi_client.py tests/unit/services/test_newsapi_client.py
git commit -m "feat(trend-004): add NewsAPI client with error handling and tests"
```

---

## Chunk 2: Service Layer

### Task 2: NewsAPI Service — Scoring, Filtering, Dedup, Pipeline

**Files:**
- Create: `src/services/newsapi.py`
- Modify: `tests/unit/services/conftest.py` (add `MockNewsAPIClient`)
- Test: `tests/unit/services/test_newsapi.py`

- [ ] **Step 1: Add MockNewsAPIClient to conftest**

Add to end of `tests/unit/services/conftest.py`:

```python
from src.services.newsapi_client import NewsAPIClient, NewsAPIArticle


class MockNewsAPIClient(NewsAPIClient):
    """Returns canned articles for deterministic testing."""

    def __init__(
        self,
        articles: list[NewsAPIArticle] | None = None,
    ) -> None:
        super().__init__(
            api_key="mock",
            base_url="http://mock",
            timeout=1.0,
        )
        self._articles = articles or []

    async def fetch_top_headlines(
        self,
        category: str,
        country: str,
        page_size: int,
    ) -> list[NewsAPIArticle]:
        return self._articles[:page_size]
```

- [ ] **Step 2: Create the service module**

Create `src/services/newsapi.py`:

```python
import math
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import NewsAPIFetchResponse
from src.services.newsapi_client import NewsAPIArticle, NewsAPIClient

logger = structlog.get_logger()

# 6-hour half-life for recency decay
_RECENCY_LAMBDA = math.log(2) / 6


class NewsAPIService:
    def __init__(self, client: NewsAPIClient) -> None:
        self._client = client

    @staticmethod
    def calculate_score(
        index: int,
        total: int,
        hours_ago: float,
        num_keywords: int,
    ) -> float:
        if total == 0:
            return 0.0
        position = max(0.0, 100 - (index * (100 / total)))
        recency = math.exp(-_RECENCY_LAMBDA * hours_ago)
        keyword = min(20.0, num_keywords * 5.0)
        return min(100.0, position * 0.5 + recency * 30 + keyword)

    @staticmethod
    def calculate_velocity(hours_ago: float) -> float:
        return 1.0 / max(1.0, hours_ago)

    @staticmethod
    def filter_by_domain(
        articles: list[NewsAPIArticle],
        domain_keywords: list[str],
    ) -> list[tuple[NewsAPIArticle, list[str]]]:
        results: list[tuple[NewsAPIArticle, list[str]]] = []
        for article in articles:
            title = article["title"].lower()
            desc = (article.get("description") or "").lower()
            source_name = article["source"]["name"].lower()
            content = (article.get("content") or "").lower()
            text = f"{title} {desc} {source_name} {content}"
            matched = [
                kw
                for kw in domain_keywords
                if kw.lower() in text
            ]
            if matched:
                results.append((article, matched))
        return results

    @staticmethod
    def map_to_raw_topic(
        article: NewsAPIArticle,
        score: float,
        velocity: float,
        matched_keywords: list[str],
    ) -> RawTopic:
        desc = article.get("description") or ""
        return RawTopic(
            title=article["title"],
            description=desc[:200],
            source="newsapi",
            external_url=article["url"],
            trend_score=score,
            velocity=velocity,
            discovered_at=datetime.now(UTC),
            domain_keywords=matched_keywords,
        )

    @staticmethod
    def _deduplicate(
        topics: list[RawTopic],
    ) -> list[RawTopic]:
        if not topics:
            return []

        # Pass 1: exact URL dedup — keep highest score
        by_url: dict[str, RawTopic] = {}
        for topic in topics:
            url = topic.external_url
            if url in by_url:
                if topic.trend_score > by_url[url].trend_score:
                    by_url[url] = topic
            else:
                by_url[url] = topic
        unique = list(by_url.values())

        # Pass 2: fuzzy title dedup
        merged: set[int] = set()
        result: list[RawTopic] = []
        for i, topic_a in enumerate(unique):
            if i in merged:
                continue
            best = topic_a
            for j in range(i + 1, len(unique)):
                if j in merged:
                    continue
                ratio = SequenceMatcher(
                    None,
                    topic_a.title.lower(),
                    unique[j].title.lower(),
                ).ratio()
                if ratio > 0.85:
                    merged.add(j)
                    if unique[j].trend_score > best.trend_score:
                        best = unique[j]
            result.append(best)
        return result

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        category: str,
        country: str,
        max_results: int,
    ) -> NewsAPIFetchResponse:
        start = time.monotonic()
        logger.info(
            "newsapi_fetch_started",
            domain_keywords=domain_keywords,
            category=category,
            country=country,
            max_results=max_results,
        )
        articles = await self._client.fetch_top_headlines(
            category,
            country,
            max_results,
        )
        total_fetched = len(articles)
        filtered = self.filter_by_domain(
            articles,
            domain_keywords,
        )
        logger.debug(
            "newsapi_items_filtered",
            before_count=total_fetched,
            after_count=len(filtered),
            domain_keywords=domain_keywords,
        )
        now = datetime.now(UTC)
        topics: list[RawTopic] = []
        total = len(filtered)
        for index, (article, kws) in enumerate(filtered):
            published = article.get("publishedAt") or ""
            try:
                pub_dt = datetime.fromisoformat(
                    published.replace("Z", "+00:00"),
                )
                hours_ago = max(
                    0.0,
                    (now - pub_dt).total_seconds() / 3600,
                )
            except (ValueError, TypeError):
                hours_ago = 24.0  # fallback for bad dates
            score = self.calculate_score(
                index, total, hours_ago, len(kws),
            )
            velocity = self.calculate_velocity(hours_ago)
            topics.append(
                self.map_to_raw_topic(article, score, velocity, kws),
            )
        deduped = self._deduplicate(topics)
        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "newsapi_fetch_completed",
            total_fetched=total_fetched,
            total_after_filter=len(topics),
            total_after_dedup=len(deduped),
            duration_ms=duration_ms,
        )
        return NewsAPIFetchResponse(
            topics=deduped,
            total_fetched=total_fetched,
            total_after_filter=len(topics),
        )
```

- [ ] **Step 3: Write service tests**

Create `tests/unit/services/test_newsapi.py`:

```python
import math
from datetime import UTC, datetime

from src.services.newsapi import NewsAPIService
from src.services.newsapi_client import NewsAPIArticle
from tests.unit.services.conftest import MockNewsAPIClient


def _article(**overrides: object) -> NewsAPIArticle:
    base: NewsAPIArticle = {
        "title": "Test Article",
        "description": "A test description.",
        "url": "https://example.com/article",
        "urlToImage": "https://example.com/img.jpg",
        "publishedAt": "2026-03-15T10:00:00Z",
        "source": {"id": "test", "name": "Test Source"},
        "author": "Author",
        "content": "Full content here.",
    }
    result: dict[str, object] = {**base, **overrides}
    return result  # type: ignore[return-value]


class TestScoreCalculation:
    def test_first_position_fresh_article(self) -> None:
        """Position 0/20, 1h old, 2 keywords → ~86.7"""
        score = NewsAPIService.calculate_score(0, 20, 1.0, 2)
        assert round(score, 1) == 86.7

    def test_middle_position_old_article(self) -> None:
        """Position 10/20, 12h old, 1 keyword → 37.5"""
        score = NewsAPIService.calculate_score(10, 20, 12.0, 1)
        assert round(score, 1) == 37.5

    def test_last_position_very_old(self) -> None:
        """Position 19/20, 48h old, 1 keyword → ~7.6"""
        score = NewsAPIService.calculate_score(19, 20, 48.0, 1)
        assert round(score, 1) == 7.6

    def test_score_capped_at_100(self) -> None:
        score = NewsAPIService.calculate_score(0, 1, 0.0, 10)
        assert score == 100.0

    def test_zero_total_returns_zero(self) -> None:
        score = NewsAPIService.calculate_score(0, 0, 1.0, 1)
        assert score == 0.0

    def test_many_keywords_bonus_capped(self) -> None:
        """Keyword bonus capped at 20 (4+ keywords)."""
        score_4 = NewsAPIService.calculate_score(5, 10, 6.0, 4)
        score_8 = NewsAPIService.calculate_score(5, 10, 6.0, 8)
        assert score_4 == score_8  # both capped at 20


class TestVelocityCalculation:
    def test_fresh_article(self) -> None:
        """0.5 hours → clamped to 1h → velocity 1.0"""
        vel = NewsAPIService.calculate_velocity(0.5)
        assert vel == 1.0

    def test_one_hour_old(self) -> None:
        vel = NewsAPIService.calculate_velocity(1.0)
        assert vel == 1.0

    def test_ten_hours_old(self) -> None:
        vel = NewsAPIService.calculate_velocity(10.0)
        assert vel == 0.1

    def test_very_old(self) -> None:
        vel = NewsAPIService.calculate_velocity(100.0)
        assert vel == 0.01


class TestDomainFiltering:
    def test_matches_title(self) -> None:
        article = _article(title="Cybersecurity breach report")
        matched = NewsAPIService.filter_by_domain(
            [article], ["cyber"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_matches_description(self) -> None:
        article = _article(
            title="A normal title",
            description="Cybersecurity trends rising",
        )
        matched = NewsAPIService.filter_by_domain(
            [article], ["cyber"],
        )
        assert len(matched) == 1

    def test_matches_source_name(self) -> None:
        article = _article(
            title="Normal title",
            description="Normal desc",
            source={"id": "cd", "name": "Cybersecurity Dive"},
        )
        matched = NewsAPIService.filter_by_domain(
            [article], ["cyber"],
        )
        assert len(matched) == 1

    def test_matches_content(self) -> None:
        article = _article(
            title="Normal title",
            description="Normal desc",
            content="Deep dive into cybersecurity",
        )
        matched = NewsAPIService.filter_by_domain(
            [article], ["cyber"],
        )
        assert len(matched) == 1

    def test_case_insensitive(self) -> None:
        article = _article(title="CYBERSECURITY NEWS")
        matched = NewsAPIService.filter_by_domain(
            [article], ["cyber"],
        )
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        article = _article(title="Cooking recipes")
        matched = NewsAPIService.filter_by_domain(
            [article], ["cyber"],
        )
        assert len(matched) == 0

    def test_multiple_keywords(self) -> None:
        article = _article(title="New AI model released")
        matched = NewsAPIService.filter_by_domain(
            [article], ["cyber", "AI"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]

    def test_none_description_handled(self) -> None:
        article = _article(
            title="Cyber topic",
            description=None,
        )
        matched = NewsAPIService.filter_by_domain(
            [article], ["cyber"],
        )
        assert len(matched) == 1

    def test_none_content_handled(self) -> None:
        article = _article(
            title="Cyber topic",
            content=None,
        )
        matched = NewsAPIService.filter_by_domain(
            [article], ["cyber"],
        )
        assert len(matched) == 1


class TestTopicMapping:
    def test_full_mapping(self) -> None:
        article = _article(
            title="Cyber Alert",
            description="A major breach.",
            url="https://example.com/cyber",
        )
        topic = NewsAPIService.map_to_raw_topic(
            article,
            score=75.0,
            velocity=0.5,
            matched_keywords=["cyber"],
        )
        assert topic.title == "Cyber Alert"
        assert topic.source == "newsapi"
        assert topic.external_url == "https://example.com/cyber"
        assert topic.trend_score == 75.0
        assert topic.velocity == 0.5
        assert topic.domain_keywords == ["cyber"]
        assert topic.description == "A major breach."

    def test_none_description_empty_string(self) -> None:
        article = _article(description=None)
        topic = NewsAPIService.map_to_raw_topic(
            article, 50.0, 0.5, ["test"],
        )
        assert topic.description == ""

    def test_long_description_truncated(self) -> None:
        article = _article(description="x" * 500)
        topic = NewsAPIService.map_to_raw_topic(
            article, 50.0, 0.5, ["test"],
        )
        assert len(topic.description) == 200


class TestDeduplication:
    def test_duplicate_urls_keep_higher_score(self) -> None:
        from src.api.schemas.topics import RawTopic

        t1 = RawTopic(
            title="Article A",
            source="newsapi",
            external_url="https://example.com/same",
            trend_score=30.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="Article B",
            source="newsapi",
            external_url="https://example.com/same",
            trend_score=70.0,
            discovered_at=datetime.now(UTC),
        )
        result = NewsAPIService._deduplicate([t1, t2])
        assert len(result) == 1
        assert result[0].trend_score == 70.0

    def test_fuzzy_title_dedup(self) -> None:
        from src.api.schemas.topics import RawTopic

        t1 = RawTopic(
            title="Major Cybersecurity Breach Hits US Companies",
            source="newsapi",
            external_url="https://a.com/1",
            trend_score=60.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="Major Cybersecurity Breach Hits US Firms",
            source="newsapi",
            external_url="https://b.com/2",
            trend_score=80.0,
            discovered_at=datetime.now(UTC),
        )
        result = NewsAPIService._deduplicate([t1, t2])
        assert len(result) == 1
        assert result[0].trend_score == 80.0

    def test_different_titles_kept(self) -> None:
        from src.api.schemas.topics import RawTopic

        t1 = RawTopic(
            title="Cybersecurity breach",
            source="newsapi",
            external_url="https://a.com/1",
            trend_score=50.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="New AI model released",
            source="newsapi",
            external_url="https://b.com/2",
            trend_score=60.0,
            discovered_at=datetime.now(UTC),
        )
        result = NewsAPIService._deduplicate([t1, t2])
        assert len(result) == 2

    def test_empty_input(self) -> None:
        result = NewsAPIService._deduplicate([])
        assert result == []


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        articles: list[NewsAPIArticle] = [
            _article(
                title="Cybersecurity breach",
                url="https://a.com/1",
            ),
            _article(
                title="Cooking recipes",
                url="https://b.com/2",
            ),
        ]
        mock_client = MockNewsAPIClient(articles=articles)
        service = NewsAPIService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            category="technology",
            country="us",
            max_results=30,
        )
        assert result.total_fetched == 2
        assert result.total_after_filter == 1
        assert len(result.topics) == 1
        assert result.topics[0].title == "Cybersecurity breach"

    async def test_empty_articles(self) -> None:
        mock_client = MockNewsAPIClient(articles=[])
        service = NewsAPIService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            category="technology",
            country="us",
            max_results=30,
        )
        assert result.total_fetched == 0
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_no_matches(self) -> None:
        articles = [_article(title="Cooking blog")]
        mock_client = MockNewsAPIClient(articles=articles)
        service = NewsAPIService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            category="technology",
            country="us",
            max_results=30,
        )
        assert result.total_fetched == 1
        assert result.total_after_filter == 0

    async def test_max_results_caps_fetch(self) -> None:
        articles = [
            _article(
                title=f"Cyber article {i}",
                url=f"https://example.com/{i}",
            )
            for i in range(10)
        ]
        mock_client = MockNewsAPIClient(articles=articles)
        service = NewsAPIService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            category="technology",
            country="us",
            max_results=3,
        )
        assert result.total_fetched == 3
```

- [ ] **Step 4: Run service tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_newsapi.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run lint on service module**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/services/newsapi.py tests/unit/services/conftest.py && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/services/newsapi.py`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add src/services/newsapi.py tests/unit/services/conftest.py tests/unit/services/test_newsapi.py
git commit -m "feat(trend-004): add NewsAPI service with scoring, filtering, dedup, and tests"
```

---

## Chunk 3: API Layer (Schemas, Settings, Router, Endpoint Tests)

### Task 3: Schemas, Settings, Router Endpoint, and Tests

**Files:**
- Modify: `src/api/schemas/trends.py` (add `NewsAPIFetchRequest`, `NewsAPIFetchResponse`)
- Modify: `src/config/settings.py` (add NewsAPI settings)
- Modify: `src/api/routers/trends.py` (add endpoint + DI helper)
- Create: `tests/unit/api/test_newsapi_schemas.py`
- Create: `tests/unit/api/test_newsapi_endpoints.py`

- [ ] **Step 1: Add schemas to `src/api/schemas/trends.py`**

Add at end of file:

```python
class NewsAPIFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    max_results: int = Field(default=30, ge=1, le=100)
    category: str = Field(default="technology")
    country: str = Field(default="us")


class NewsAPIFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_filter: int
```

- [ ] **Step 2: Add settings to `src/config/settings.py`**

Add after the Reddit settings block (after line 50):

```python
    # NewsAPI integration
    newsapi_api_key: str = ""
    newsapi_base_url: str = "https://newsapi.org/v2"
    newsapi_request_timeout: float = 10.0
    newsapi_default_category: str = "technology"
    newsapi_default_country: str = "us"
```

- [ ] **Step 3: Add endpoint to `src/api/routers/trends.py`**

Add the import at the top (in the imports from `src.api.schemas.trends`):
```python
    NewsAPIFetchRequest,
    NewsAPIFetchResponse,
```

Add the imports for the NewsAPI service:
```python
from src.services.newsapi import NewsAPIService
from src.services.newsapi_client import (
    NewsAPIClient,
    NewsAPIError,
)
```

Add the DI helper and endpoint at the end of the file:

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


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/newsapi/fetch",
    response_model=NewsAPIFetchResponse,
    summary="Fetch trending NewsAPI headlines",
)
async def fetch_newsapi(
    request: Request,
    body: NewsAPIFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> NewsAPIFetchResponse:
    service = _get_newsapi_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            category=body.category,
            country=body.country,
            max_results=body.max_results,
        )
    except NewsAPIError as exc:
        logger.error(
            "newsapi_api_error",
            error=str(exc),
            category=body.category,
            country=body.country,
        )
        raise ServiceUnavailableError(
            code="newsapi_unavailable",
            message="NewsAPI is not available",
        ) from exc
```

- [ ] **Step 4: Write schema tests**

Create `tests/unit/api/test_newsapi_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from src.api.schemas.trends import (
    NewsAPIFetchRequest,
    NewsAPIFetchResponse,
)


class TestNewsAPIFetchRequest:
    def test_valid_request_defaults(self) -> None:
        req = NewsAPIFetchRequest(domain_keywords=["cyber"])
        assert req.domain_keywords == ["cyber"]
        assert req.max_results == 30
        assert req.category == "technology"
        assert req.country == "us"

    def test_custom_values(self) -> None:
        req = NewsAPIFetchRequest(
            domain_keywords=["ai", "ml"],
            max_results=50,
            category="science",
            country="gb",
        )
        assert req.max_results == 50
        assert req.category == "science"
        assert req.country == "gb"

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NewsAPIFetchRequest(domain_keywords=[])

    def test_max_results_too_high(self) -> None:
        with pytest.raises(ValidationError):
            NewsAPIFetchRequest(
                domain_keywords=["x"], max_results=101,
            )

    def test_max_results_too_low(self) -> None:
        with pytest.raises(ValidationError):
            NewsAPIFetchRequest(
                domain_keywords=["x"], max_results=0,
            )


class TestNewsAPIFetchResponse:
    def test_response_shape(self) -> None:
        resp = NewsAPIFetchResponse(
            topics=[],
            total_fetched=20,
            total_after_filter=5,
        )
        assert resp.total_fetched == 20
        assert resp.total_after_filter == 5
        assert resp.topics == []
```

- [ ] **Step 5: Write endpoint tests**

Create `tests/unit/api/test_newsapi_endpoints.py`:

```python
from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.services.newsapi_client import NewsAPIArticle
from tests.unit.services.conftest import MockNewsAPIClient

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header


def _newsapi_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "domain_keywords": ["cyber"],
        "max_results": 30,
        "category": "technology",
        "country": "us",
    }
    base.update(overrides)
    return base


SAMPLE_ARTICLES: list[NewsAPIArticle] = [
    {
        "title": "Cybersecurity Trends 2026",
        "description": "Analysis of cybersecurity trends.",
        "url": "https://example.com/cyber",
        "urlToImage": "https://example.com/img.jpg",
        "publishedAt": "2026-03-15T10:00:00Z",
        "source": {"id": "test", "name": "Test Source"},
        "author": "Jane Doe",
        "content": "Full content about cybersecurity.",
    },
]


@pytest.fixture
def newsapi_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def newsapi_app(newsapi_settings: Settings) -> FastAPI:
    app = create_app(newsapi_settings)
    app.state.newsapi_client = MockNewsAPIClient(
        articles=SAMPLE_ARTICLES,
    )
    return app


@pytest.fixture
async def newsapi_client(
    newsapi_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=newsapi_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestNewsAPIEndpointAuth:
    async def test_no_token_returns_401(
        self,
        newsapi_client: httpx.AsyncClient,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
            headers=make_auth_header(
                "viewer", newsapi_settings,
            ),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
            headers=make_auth_header(
                "editor", newsapi_settings,
            ),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
            headers=make_auth_header(
                "admin", newsapi_settings,
            ),
        )
        assert resp.status_code == 200


class TestNewsAPIEndpointValidation:
    async def test_empty_keywords_returns_422(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(domain_keywords=[]),
            headers=make_auth_header(
                "editor", newsapi_settings,
            ),
        )
        assert resp.status_code == 422


class TestNewsAPIEndpointSuccess:
    async def test_response_shape(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(),
            headers=make_auth_header(
                "editor", newsapi_settings,
            ),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "total_fetched" in data
        assert "total_after_filter" in data
        assert data["total_fetched"] == 1

    async def test_no_matches_returns_empty(
        self,
        newsapi_client: httpx.AsyncClient,
        newsapi_settings: Settings,
    ) -> None:
        resp = await newsapi_client.post(
            "/api/v1/trends/newsapi/fetch",
            json=_newsapi_request(
                domain_keywords=["cooking"],
            ),
            headers=make_auth_header(
                "editor", newsapi_settings,
            ),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_after_filter"] == 0


class TestNewsAPIEndpoint503:
    async def test_api_error_returns_503(
        self,
        newsapi_settings: Settings,
    ) -> None:
        from src.services.newsapi_client import NewsAPIError

        class FailingClient(MockNewsAPIClient):
            async def fetch_top_headlines(
                self,
                category: str,
                country: str,
                page_size: int,
            ) -> list[NewsAPIArticle]:
                raise NewsAPIError("API down")

        app = create_app(newsapi_settings)
        app.state.newsapi_client = FailingClient()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/trends/newsapi/fetch",
                json=_newsapi_request(),
                headers=make_auth_header(
                    "editor",
                    newsapi_settings,
                ),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "newsapi_unavailable"
```

- [ ] **Step 6: Run all new tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_newsapi_schemas.py tests/unit/api/test_newsapi_endpoints.py -v`
Expected: All tests PASS.

- [ ] **Step 7: Run lint on all modified/created files**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/api/schemas/trends.py src/api/routers/trends.py src/config/settings.py && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/api/routers/trends.py`
Expected: No errors.

- [ ] **Step 8: Commit**

```bash
git add src/api/schemas/trends.py src/config/settings.py src/api/routers/trends.py tests/unit/api/test_newsapi_schemas.py tests/unit/api/test_newsapi_endpoints.py
git commit -m "feat(trend-004): add NewsAPI endpoint, schemas, settings, and tests"
```

---

## Chunk 4: Full Suite Verification and Tracking Updates

### Task 4: Run Full Test Suite and Update Tracking

**Files:**
- Modify: `project-management/PROGRESS.md`
- Modify: `project-management/BACKLOG.md`

- [ ] **Step 1: Run full test suite**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v --tb=short`
Expected: All existing tests still pass. All new TREND-004 tests pass. No regressions.

- [ ] **Step 2: Run full lint suite**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/ && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/ && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/`
Expected: All checks pass.

- [ ] **Step 3: Update PROGRESS.md**

Change TREND-004 row:
```markdown
| TREND-004 | NewsAPI Integration       | Done | `feature/TREND-004-newsapi-integration` | [plan](../docs/superpowers/plans/2026-03-15-trend-004-newsapi-integration.md) | [spec](../docs/superpowers/specs/2026-03-15-trend-004-newsapi-integration-design.md) |
```

- [ ] **Step 4: Update BACKLOG.md**

Add `— DONE` suffix to TREND-004 title and add status/plan/spec fields:
```markdown
### TREND-004: NewsAPI Integration [Should] — DONE
- **Status**: Done (branch `feature/TREND-004-newsapi-integration`)
- **Plan**: [`docs/superpowers/plans/2026-03-15-trend-004-newsapi-integration.md`](../docs/superpowers/plans/2026-03-15-trend-004-newsapi-integration.md)
- **Spec**: [`docs/superpowers/specs/2026-03-15-trend-004-newsapi-integration-design.md`](../docs/superpowers/specs/2026-03-15-trend-004-newsapi-integration-design.md)
```

- [ ] **Step 5: Commit tracking updates**

```bash
git add project-management/PROGRESS.md project-management/BACKLOG.md
git commit -m "docs: update tracking — TREND-004 Done"
```
