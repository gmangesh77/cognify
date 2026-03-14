# TREND-005: arXiv Paper Feed Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add arXiv as the fifth trend source — client, service, schemas, API endpoint, settings, and full test coverage.

**Architecture:** Follows the established 3-tier trend source pattern (Client → Service → API endpoint). arXiv's public Atom XML API is queried via httpx, parsed with `xml.etree.ElementTree`, scored by recency + citation potential heuristic, and exposed through a POST endpoint.

**Tech Stack:** Python 3.12+, httpx, xml.etree.ElementTree, FastAPI, Pydantic, structlog, pytest

**Spec:** [`docs/superpowers/specs/2026-03-15-trend-005-arxiv-paper-feed-design.md`](../specs/2026-03-15-trend-005-arxiv-paper-feed-design.md)

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/services/arxiv_client.py` | HTTP client: fetch papers from arXiv API, parse XML, handle errors |
| Create | `src/services/arxiv.py` | Service: filtering, scoring, velocity, dedup, mapping to RawTopic |
| Create | `tests/unit/services/test_arxiv_client.py` | Client unit tests: HTTP mocking, XML parsing, error handling |
| Create | `tests/unit/services/test_arxiv.py` | Service unit tests: scoring, filtering, dedup, pipeline |
| Create | `tests/unit/api/test_arxiv_endpoints.py` | Endpoint tests: auth, validation, happy path, 503 |
| Modify | `src/config/settings.py` | Add arxiv_api_base_url, arxiv_request_timeout, arxiv_default_categories |
| Modify | `src/api/schemas/trends.py` | Add ArxivFetchRequest, ArxivFetchResponse |
| Modify | `src/api/routers/trends.py` | Add `_get_arxiv_service()` + `POST /trends/arxiv/fetch` |
| Modify | `tests/unit/services/conftest.py` | Add MockArxivClient |

---

## Chunk 1: Client Layer

### Task 1: Settings — Add arXiv Configuration

**Files:**
- Modify: `src/config/settings.py:51-57`

- [x] **Step 1: Add arXiv settings fields**

Add after the NewsAPI settings block (line 57) in `src/config/settings.py`:

```python
    # arXiv integration
    arxiv_api_base_url: str = "https://export.arxiv.org/api/query"
    arxiv_request_timeout: float = 15.0
    arxiv_default_categories: list[str] = [
        "cs.CR",
        "cs.AI",
        "cs.LG",
    ]
```

- [x] **Step 2: Verify settings load**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify python -c "from src.config.settings import Settings; s = Settings(); print(s.arxiv_api_base_url, s.arxiv_default_categories)"`

Expected: `https://export.arxiv.org/api/query ['cs.CR', 'cs.AI', 'cs.LG']`

- [x] **Step 3: Commit**

```bash
git add src/config/settings.py
git commit -m "feat(trend-005): add arXiv settings to config"
```

---

### Task 2: ArxivClient — TypedDict, Exception, and Client Class

**Files:**
- Create: `src/services/arxiv_client.py`
- Create: `tests/unit/services/test_arxiv_client.py`

- [x] **Step 1: Write the failing tests for ArxivClient**

Create `tests/unit/services/test_arxiv_client.py`:

```python
from unittest.mock import AsyncMock, patch
from xml.etree.ElementTree import ParseError

import httpx
import pytest

from src.services.arxiv_client import (
    ArxivAPIError,
    ArxivClient,
    ArxivPaper,
)

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2603.12345v1</id>
    <title>Adversarial Attacks on
    Neural Networks</title>
    <summary>We study adversarial attacks on deep neural networks.</summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <published>2026-03-15T12:00:00Z</published>
    <updated>2026-03-15T12:00:00Z</updated>
    <link href="http://arxiv.org/abs/2603.12345v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2603.12345v1" rel="related" type="application/pdf" title="pdf"/>
    <arxiv:primary_category term="cs.CR"/>
    <category term="cs.CR"/>
    <category term="cs.AI"/>
  </entry>
</feed>"""

EMPTY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""


class TestFetchPapers:
    async def test_successful_fetch(self) -> None:
        mock_response = httpx.Response(
            200,
            text=SAMPLE_XML,
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            papers = await client.fetch_papers(
                categories=["cs.CR"],
                max_results=10,
                sort_by="submittedDate",
            )
        assert len(papers) == 1
        paper = papers[0]
        assert paper["arxiv_id"] == "2603.12345v1"
        assert paper["title"] == "Adversarial Attacks on Neural Networks"
        assert paper["authors"] == ["Alice Smith", "Bob Jones"]
        assert paper["primary_category"] == "cs.CR"
        assert paper["categories"] == ["cs.CR", "cs.AI"]
        assert "pdf" in paper["pdf_url"]
        assert paper["abs_url"] == "http://arxiv.org/abs/2603.12345v1"

    async def test_empty_results(self) -> None:
        mock_response = httpx.Response(
            200,
            text=EMPTY_XML,
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            papers = await client.fetch_papers(
                categories=["cs.CR"],
                max_results=10,
                sort_by="submittedDate",
            )
        assert papers == []

    async def test_http_error_raises(self) -> None:
        mock_response = httpx.Response(
            500,
            text="Internal Server Error",
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(ArxivAPIError, match="500"):
                await client.fetch_papers(
                    categories=["cs.CR"],
                    max_results=10,
                    sort_by="submittedDate",
                )

    async def test_timeout_raises(self) -> None:
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException(
                "timed out",
            )
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(ArxivAPIError, match="timed out"):
                await client.fetch_papers(
                    categories=["cs.CR"],
                    max_results=10,
                    sort_by="submittedDate",
                )

    async def test_connection_error_raises(self) -> None:
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError(
                "refused",
            )
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(ArxivAPIError, match="refused"):
                await client.fetch_papers(
                    categories=["cs.CR"],
                    max_results=10,
                    sort_by="submittedDate",
                )

    async def test_invalid_xml_raises(self) -> None:
        mock_response = httpx.Response(
            200,
            text="not xml at all",
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(ArxivAPIError, match="parse"):
                await client.fetch_papers(
                    categories=["cs.CR"],
                    max_results=10,
                    sort_by="submittedDate",
                )

    async def test_title_whitespace_normalized(self) -> None:
        mock_response = httpx.Response(
            200,
            text=SAMPLE_XML,
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            papers = await client.fetch_papers(
                categories=["cs.CR"],
                max_results=10,
                sort_by="submittedDate",
            )
        assert "\n" not in papers[0]["title"]

    async def test_query_builds_correctly(self) -> None:
        mock_response = httpx.Response(
            200,
            text=EMPTY_XML,
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            await client.fetch_papers(
                categories=["cs.CR", "cs.AI"],
                max_results=20,
                sort_by="submittedDate",
            )
            call_kwargs = mock_client.get.call_args
            params = call_kwargs.kwargs.get(
                "params",
                call_kwargs.args[1] if len(call_kwargs.args) > 1 else {},
            )
            assert "cat:cs.CR" in params["search_query"]
            assert "cat:cs.AI" in params["search_query"]
            assert params["max_results"] == 20
            assert params["sortBy"] == "submittedDate"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_arxiv_client.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.arxiv_client'`

- [x] **Step 3: Implement ArxivClient**

Create `src/services/arxiv_client.py`:

```python
import re
import xml.etree.ElementTree as ET
from typing import TypedDict

import httpx

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"


class ArxivPaper(TypedDict):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    published: str
    updated: str
    pdf_url: str
    abs_url: str
    primary_category: str
    categories: list[str]


class ArxivAPIError(Exception):
    """Raised when arXiv API is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text


def _parse_entry(entry: ET.Element) -> ArxivPaper:
    raw_id = _text(entry.find(f"{{{_ATOM_NS}}}id"))
    arxiv_id = raw_id.rsplit("/", 1)[-1] if "/" in raw_id else raw_id

    raw_title = _text(entry.find(f"{{{_ATOM_NS}}}title"))
    title = re.sub(r"\s+", " ", raw_title).strip()

    abstract = _text(
        entry.find(f"{{{_ATOM_NS}}}summary"),
    ).strip()

    authors = [
        _text(a.find(f"{{{_ATOM_NS}}}name"))
        for a in entry.findall(f"{{{_ATOM_NS}}}author")
    ]

    published = _text(entry.find(f"{{{_ATOM_NS}}}published"))
    updated = _text(entry.find(f"{{{_ATOM_NS}}}updated"))

    abs_url = ""
    pdf_url = ""
    for link in entry.findall(f"{{{_ATOM_NS}}}link"):
        rel = link.get("rel", "")
        if rel == "alternate":
            abs_url = link.get("href", "")
        elif link.get("title") == "pdf":
            pdf_url = link.get("href", "")

    prim_el = entry.find(f"{{{_ARXIV_NS}}}primary_category")
    primary_category = prim_el.get("term", "") if prim_el is not None else ""

    categories = [
        cat.get("term", "")
        for cat in entry.findall(f"{{{_ATOM_NS}}}category")
        if cat.get("term")
    ]

    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        published=published,
        updated=updated,
        pdf_url=pdf_url,
        abs_url=abs_url,
        primary_category=primary_category,
        categories=categories,
    )


class ArxivClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout

    async def fetch_papers(
        self,
        categories: list[str],
        max_results: int,
        sort_by: str,
    ) -> list[ArxivPaper]:
        query = " OR ".join(
            f"cat:{cat}" for cat in categories
        )
        params: dict[str, str | int] = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
            ) as client:
                resp = await client.get(
                    self._base_url,
                    params=params,
                )
        except httpx.TimeoutException as exc:
            raise ArxivAPIError(
                f"arXiv timed out: {exc}",
            ) from exc
        except httpx.ConnectError as exc:
            raise ArxivAPIError(
                f"arXiv connection failed: {exc}",
            ) from exc
        if not resp.is_success:
            raise ArxivAPIError(
                f"arXiv returned {resp.status_code}",
            )
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            raise ArxivAPIError(
                f"arXiv XML parse error: {exc}",
            ) from exc
        entries = root.findall(f"{{{_ATOM_NS}}}entry")
        return [_parse_entry(e) for e in entries]
```

- [x] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_arxiv_client.py -v`

Expected: All 8 tests PASS

- [x] **Step 5: Commit**

```bash
git add src/services/arxiv_client.py tests/unit/services/test_arxiv_client.py
git commit -m "feat(trend-005): add arXiv API client with XML parsing and tests"
```

---

## Chunk 2: Schemas + Service Layer

### Task 3: Schemas — Add ArxivFetchRequest and ArxivFetchResponse

**Files:**
- Modify: `src/api/schemas/trends.py`

- [x] **Step 1: Add arXiv schemas**

Append to `src/api/schemas/trends.py` (after `NewsAPIFetchResponse`):

```python

class ArxivFetchRequest(BaseModel):
    domain_keywords: list[str] = Field(min_length=1)
    categories: list[str] = Field(
        default=["cs.CR", "cs.AI", "cs.LG"],
    )
    max_results: int = Field(default=30, ge=1, le=100)


class ArxivFetchResponse(BaseModel):
    topics: list[RawTopic]
    total_fetched: int
    total_after_filter: int
```

- [x] **Step 2: Verify import**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify python -c "from src.api.schemas.trends import ArxivFetchRequest, ArxivFetchResponse; print('OK')"`

Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add src/api/schemas/trends.py
git commit -m "feat(trend-005): add arXiv request/response schemas"
```

---

### Task 4: ArxivService — Scoring, Filtering, Dedup, Pipeline

**Files:**
- Create: `src/services/arxiv.py`
- Create: `tests/unit/services/test_arxiv.py`
- Modify: `tests/unit/services/conftest.py` — add MockArxivClient

- [x] **Step 1: Add MockArxivClient to conftest**

Add to `tests/unit/services/conftest.py` (after MockNewsAPIClient):

```python
from src.services.arxiv_client import ArxivClient, ArxivPaper


class MockArxivClient(ArxivClient):
    """Returns canned papers for deterministic testing."""

    def __init__(
        self,
        papers: list[ArxivPaper] | None = None,
    ) -> None:
        super().__init__(base_url="http://mock", timeout=1.0)
        self._papers = papers or []

    async def fetch_papers(
        self,
        categories: list[str],
        max_results: int,
        sort_by: str,
    ) -> list[ArxivPaper]:
        return self._papers[:max_results]
```

- [x] **Step 2: Write the failing tests for ArxivService**

Create `tests/unit/services/test_arxiv.py`:

```python
from datetime import UTC, datetime

from src.api.schemas.topics import RawTopic
from src.services.arxiv import ArxivService
from src.services.arxiv_client import ArxivPaper
from tests.unit.services.conftest import MockArxivClient


def _paper(**overrides: object) -> ArxivPaper:
    base: ArxivPaper = {
        "arxiv_id": "2603.12345v1",
        "title": "Adversarial Attacks on Neural Networks",
        "abstract": "We study adversarial attacks on deep neural nets.",
        "authors": ["Alice Smith", "Bob Jones"],
        "published": "2026-03-15T12:00:00Z",
        "updated": "2026-03-15T12:00:00Z",
        "pdf_url": "http://arxiv.org/pdf/2603.12345v1",
        "abs_url": "http://arxiv.org/abs/2603.12345v1",
        "primary_category": "cs.CR",
        "categories": ["cs.CR", "cs.AI"],
    }
    result: dict[str, object] = {**base, **overrides}
    return result  # type: ignore[return-value]


class TestScoreCalculation:
    def test_fresh_paper_high_score(self) -> None:
        score = ArxivService.calculate_score(0.0, 2, 200)
        assert score > 70.0

    def test_week_old_paper_moderate(self) -> None:
        score = ArxivService.calculate_score(7.0, 2, 200)
        assert 30.0 < score < 70.0

    def test_old_paper_low_score(self) -> None:
        score = ArxivService.calculate_score(30.0, 1, 50)
        assert score < 25.0

    def test_many_categories_boosts_score(self) -> None:
        score_1 = ArxivService.calculate_score(1.0, 1, 200)
        score_4 = ArxivService.calculate_score(1.0, 4, 200)
        assert score_4 > score_1

    def test_longer_abstract_boosts_score(self) -> None:
        score_short = ArxivService.calculate_score(1.0, 2, 50)
        score_long = ArxivService.calculate_score(1.0, 2, 500)
        assert score_long > score_short

    def test_score_capped_at_100(self) -> None:
        score = ArxivService.calculate_score(0.0, 10, 1500)
        assert score <= 100.0

    def test_category_contribution_capped(self) -> None:
        score_4 = ArxivService.calculate_score(0.0, 4, 200)
        score_8 = ArxivService.calculate_score(0.0, 8, 200)
        assert score_4 == score_8

    def test_abstract_contribution_capped(self) -> None:
        score_1k = ArxivService.calculate_score(0.0, 2, 1000)
        score_2k = ArxivService.calculate_score(0.0, 2, 2000)
        assert score_1k == score_2k


class TestVelocityCalculation:
    def test_fresh_paper(self) -> None:
        vel = ArxivService.calculate_velocity(0.5)
        assert vel == 1.0

    def test_one_day_old(self) -> None:
        vel = ArxivService.calculate_velocity(1.0)
        assert vel == 1.0

    def test_seven_days_old(self) -> None:
        vel = ArxivService.calculate_velocity(7.0)
        assert round(vel, 4) == round(1.0 / 7.0, 4)


class TestDomainFiltering:
    def test_matches_title(self) -> None:
        paper = _paper(title="Cybersecurity attack model")
        matched = ArxivService.filter_by_domain(
            [paper], ["cyber"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_matches_abstract(self) -> None:
        paper = _paper(
            title="Normal title",
            abstract="A study on cybersecurity threats.",
        )
        matched = ArxivService.filter_by_domain(
            [paper], ["cyber"],
        )
        assert len(matched) == 1

    def test_matches_categories(self) -> None:
        paper = _paper(
            title="Normal",
            abstract="Normal",
            categories=["cs.CR"],
        )
        matched = ArxivService.filter_by_domain(
            [paper], ["cs.CR"],
        )
        assert len(matched) == 1

    def test_matches_author(self) -> None:
        paper = _paper(
            title="Normal",
            abstract="Normal",
            authors=["Cyber Expert"],
        )
        matched = ArxivService.filter_by_domain(
            [paper], ["cyber"],
        )
        assert len(matched) == 1

    def test_case_insensitive(self) -> None:
        paper = _paper(title="CYBERSECURITY Analysis")
        matched = ArxivService.filter_by_domain(
            [paper], ["cyber"],
        )
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        paper = _paper(title="Cooking with AI")
        matched = ArxivService.filter_by_domain(
            [paper], ["cyber"],
        )
        assert len(matched) == 0

    def test_multiple_keywords(self) -> None:
        paper = _paper(title="New AI model for attacks")
        matched = ArxivService.filter_by_domain(
            [paper], ["cyber", "AI"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]


class TestTopicMapping:
    def test_full_mapping(self) -> None:
        paper = _paper(
            title="Cyber Alert Paper",
            abstract="A major finding about threats.",
            abs_url="http://arxiv.org/abs/2603.99999v1",
        )
        topic = ArxivService.map_to_raw_topic(
            paper,
            score=75.0,
            velocity=0.5,
            matched_keywords=["cyber"],
        )
        assert topic.title == "Cyber Alert Paper"
        assert topic.source == "arxiv"
        assert topic.external_url == "http://arxiv.org/abs/2603.99999v1"
        assert topic.trend_score == 75.0
        assert topic.velocity == 0.5
        assert topic.domain_keywords == ["cyber"]

    def test_long_abstract_truncated(self) -> None:
        paper = _paper(abstract="x" * 500)
        topic = ArxivService.map_to_raw_topic(
            paper, 50.0, 0.5, ["test"],
        )
        assert len(topic.description) == 200


class TestDeduplication:
    def test_duplicate_ids_keep_higher_score(self) -> None:
        t1 = RawTopic(
            title="Paper A",
            source="arxiv",
            external_url="http://arxiv.org/abs/2603.11111v1",
            trend_score=30.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="Paper A (v2)",
            source="arxiv",
            external_url="http://arxiv.org/abs/2603.11111v1",
            trend_score=70.0,
            discovered_at=datetime.now(UTC),
        )
        result = ArxivService._deduplicate([t1, t2])
        assert len(result) == 1
        assert result[0].trend_score == 70.0

    def test_different_ids_kept(self) -> None:
        t1 = RawTopic(
            title="Paper A",
            source="arxiv",
            external_url="http://arxiv.org/abs/2603.11111v1",
            trend_score=50.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="Paper B",
            source="arxiv",
            external_url="http://arxiv.org/abs/2603.22222v1",
            trend_score=60.0,
            discovered_at=datetime.now(UTC),
        )
        result = ArxivService._deduplicate([t1, t2])
        assert len(result) == 2

    def test_empty_input(self) -> None:
        result = ArxivService._deduplicate([])
        assert result == []


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        papers: list[ArxivPaper] = [
            _paper(
                title="Cybersecurity attack model",
                arxiv_id="2603.11111v1",
                abs_url="http://arxiv.org/abs/2603.11111v1",
            ),
            _paper(
                title="Cooking with algorithms",
                arxiv_id="2603.22222v1",
                abs_url="http://arxiv.org/abs/2603.22222v1",
            ),
        ]
        mock_client = MockArxivClient(papers=papers)
        service = ArxivService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            categories=["cs.CR"],
            max_results=30,
        )
        assert result.total_fetched == 2
        assert result.total_after_filter == 1
        assert len(result.topics) == 1
        assert result.topics[0].title == "Cybersecurity attack model"

    async def test_empty_papers(self) -> None:
        mock_client = MockArxivClient(papers=[])
        service = ArxivService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            categories=["cs.CR"],
            max_results=30,
        )
        assert result.total_fetched == 0
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_no_matches(self) -> None:
        papers = [_paper(title="Cooking blog paper")]
        mock_client = MockArxivClient(papers=papers)
        service = ArxivService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            categories=["cs.CR"],
            max_results=30,
        )
        assert result.total_fetched == 1
        assert result.total_after_filter == 0

    async def test_max_results_caps_fetch(self) -> None:
        papers = [
            _paper(
                title=f"Cyber paper {i}",
                arxiv_id=f"2603.{i:05d}v1",
                abs_url=f"http://arxiv.org/abs/2603.{i:05d}v1",
            )
            for i in range(10)
        ]
        mock_client = MockArxivClient(papers=papers)
        service = ArxivService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            categories=["cs.CR"],
            max_results=3,
        )
        assert result.total_fetched == 3
```

- [x] **Step 3: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_arxiv.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.arxiv'`

- [x] **Step 4: Implement ArxivService**

Create `src/services/arxiv.py`:

```python
import math
import time
from datetime import UTC, datetime

import structlog

from src.api.schemas.topics import RawTopic
from src.api.schemas.trends import ArxivFetchResponse
from src.services.arxiv_client import ArxivClient, ArxivPaper

logger = structlog.get_logger()

# 7-day half-life for recency decay
_RECENCY_LAMBDA = math.log(2) / 7


class ArxivService:
    def __init__(self, client: ArxivClient) -> None:
        self._client = client

    @staticmethod
    def calculate_score(
        days_ago: float,
        num_categories: int,
        abstract_length: int,
    ) -> float:
        recency = math.exp(-_RECENCY_LAMBDA * days_ago) * 100
        cat_bonus = min(60.0, num_categories * 15.0)
        abs_bonus = min(40.0, abstract_length / 25)
        citation = cat_bonus + abs_bonus
        raw = recency * 0.6 + citation * 0.4
        return min(100.0, raw)

    @staticmethod
    def calculate_velocity(days_ago: float) -> float:
        return 1.0 / max(1.0, days_ago)

    @staticmethod
    def filter_by_domain(
        papers: list[ArxivPaper],
        domain_keywords: list[str],
    ) -> list[tuple[ArxivPaper, list[str]]]:
        results: list[tuple[ArxivPaper, list[str]]] = []
        for paper in papers:
            title = paper["title"].lower()
            abstract = paper["abstract"].lower()
            cats = " ".join(paper["categories"]).lower()
            authors = " ".join(paper["authors"]).lower()
            text = f"{title} {abstract} {cats} {authors}"
            matched = [
                kw for kw in domain_keywords if kw.lower() in text
            ]
            if matched:
                results.append((paper, matched))
        return results

    @staticmethod
    def map_to_raw_topic(
        paper: ArxivPaper,
        score: float,
        velocity: float,
        matched_keywords: list[str],
    ) -> RawTopic:
        return RawTopic(
            title=paper["title"],
            description=paper["abstract"][:200],
            source="arxiv",
            external_url=paper["abs_url"],
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
        by_url: dict[str, RawTopic] = {}
        for topic in topics:
            url = topic.external_url
            if url in by_url:
                if topic.trend_score > by_url[url].trend_score:
                    by_url[url] = topic
            else:
                by_url[url] = topic
        return list(by_url.values())

    async def fetch_and_normalize(
        self,
        domain_keywords: list[str],
        categories: list[str],
        max_results: int,
    ) -> ArxivFetchResponse:
        start = time.monotonic()
        logger.info(
            "arxiv_fetch_started",
            domain_keywords=domain_keywords,
            categories=categories,
            max_results=max_results,
        )
        papers = await self._client.fetch_papers(
            categories,
            max_results,
            sort_by="submittedDate",
        )
        total_fetched = len(papers)
        filtered = self.filter_by_domain(
            papers, domain_keywords,
        )
        logger.debug(
            "arxiv_items_filtered",
            before_count=total_fetched,
            after_count=len(filtered),
        )
        now = datetime.now(UTC)
        topics: list[RawTopic] = []
        for paper, kws in filtered:
            published = paper.get("published", "")
            try:
                pub_dt = datetime.fromisoformat(
                    published.replace("Z", "+00:00"),
                )
                days_ago = max(
                    0.0,
                    (now - pub_dt).total_seconds() / 86400,
                )
            except (ValueError, TypeError):
                days_ago = 30.0
            score = self.calculate_score(
                days_ago,
                len(paper["categories"]),
                len(paper["abstract"]),
            )
            velocity = self.calculate_velocity(days_ago)
            topics.append(
                self.map_to_raw_topic(paper, score, velocity, kws),
            )
        deduped = self._deduplicate(topics)
        duration_ms = round(
            (time.monotonic() - start) * 1000,
        )
        logger.info(
            "arxiv_fetch_completed",
            total_fetched=total_fetched,
            total_after_filter=len(topics),
            total_after_dedup=len(deduped),
            duration_ms=duration_ms,
        )
        return ArxivFetchResponse(
            topics=deduped,
            total_fetched=total_fetched,
            total_after_filter=len(topics),
        )
```

- [x] **Step 5: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_arxiv.py tests/unit/services/test_arxiv_client.py -v`

Expected: All tests PASS (after Task 4 Step 1 adds the schema)

- [x] **Step 6: Commit**

```bash
git add src/services/arxiv.py tests/unit/services/test_arxiv.py tests/unit/services/conftest.py
git commit -m "feat(trend-005): add arXiv service with scoring, filtering, dedup, and tests"
```

---

## Chunk 3: API Layer

### Task 5: API Endpoint — POST /trends/arxiv/fetch

**Files:**
- Modify: `src/api/routers/trends.py`
- Create: `tests/unit/api/test_arxiv_endpoints.py`

- [x] **Step 1: Write the failing endpoint tests**

Create `tests/unit/api/test_arxiv_endpoints.py`:

```python
from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.services.arxiv_client import ArxivPaper
from tests.unit.services.conftest import MockArxivClient

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header


def _arxiv_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "domain_keywords": ["cyber"],
        "categories": ["cs.CR"],
        "max_results": 30,
    }
    base.update(overrides)
    return base


SAMPLE_PAPERS: list[ArxivPaper] = [
    {
        "arxiv_id": "2603.12345v1",
        "title": "Cybersecurity Trends in 2026",
        "abstract": "A study on cybersecurity trends.",
        "authors": ["Alice Smith"],
        "published": "2026-03-15T12:00:00Z",
        "updated": "2026-03-15T12:00:00Z",
        "pdf_url": "http://arxiv.org/pdf/2603.12345v1",
        "abs_url": "http://arxiv.org/abs/2603.12345v1",
        "primary_category": "cs.CR",
        "categories": ["cs.CR", "cs.AI"],
    },
]


@pytest.fixture
def arxiv_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def arxiv_app(arxiv_settings: Settings) -> FastAPI:
    app = create_app(arxiv_settings)
    app.state.arxiv_client = MockArxivClient(
        papers=SAMPLE_PAPERS,
    )
    return app


@pytest.fixture
async def arxiv_client(
    arxiv_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=arxiv_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestArxivEndpointAuth:
    async def test_no_token_returns_401(
        self,
        arxiv_client: httpx.AsyncClient,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
            headers=make_auth_header(
                "viewer", arxiv_settings,
            ),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
            headers=make_auth_header(
                "editor", arxiv_settings,
            ),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
            headers=make_auth_header(
                "admin", arxiv_settings,
            ),
        )
        assert resp.status_code == 200


class TestArxivEndpointValidation:
    async def test_empty_keywords_returns_422(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(domain_keywords=[]),
            headers=make_auth_header(
                "editor", arxiv_settings,
            ),
        )
        assert resp.status_code == 422


class TestArxivEndpointSuccess:
    async def test_response_shape(
        self,
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(),
            headers=make_auth_header(
                "editor", arxiv_settings,
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
        arxiv_client: httpx.AsyncClient,
        arxiv_settings: Settings,
    ) -> None:
        resp = await arxiv_client.post(
            "/api/v1/trends/arxiv/fetch",
            json=_arxiv_request(
                domain_keywords=["cooking"],
            ),
            headers=make_auth_header(
                "editor", arxiv_settings,
            ),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_after_filter"] == 0


class TestArxivEndpoint503:
    async def test_api_error_returns_503(
        self,
        arxiv_settings: Settings,
    ) -> None:
        from src.services.arxiv_client import ArxivAPIError

        class FailingClient(MockArxivClient):
            async def fetch_papers(
                self,
                categories: list[str],
                max_results: int,
                sort_by: str,
            ) -> list[ArxivPaper]:
                raise ArxivAPIError("API down")

        app = create_app(arxiv_settings)
        app.state.arxiv_client = FailingClient()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/trends/arxiv/fetch",
                json=_arxiv_request(),
                headers=make_auth_header(
                    "editor",
                    arxiv_settings,
                ),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "arxiv_unavailable"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_arxiv_endpoints.py -v`

Expected: FAIL — 404 (endpoint doesn't exist yet)

- [x] **Step 3: Add arxiv endpoint to trends router**

Add imports at top of `src/api/routers/trends.py`:

```python
from src.api.schemas.trends import (
    ArxivFetchRequest,
    ArxivFetchResponse,
    # ... existing imports ...
)
from src.services.arxiv import ArxivService
from src.services.arxiv_client import (
    ArxivAPIError,
    ArxivClient,
)
```

Add the dependency function and endpoint at the end of the file:

```python
def _get_arxiv_service(request: Request) -> ArxivService:
    settings = request.app.state.settings
    if hasattr(request.app.state, "arxiv_client"):
        client = request.app.state.arxiv_client
    else:
        client = ArxivClient(
            base_url=settings.arxiv_api_base_url,
            timeout=settings.arxiv_request_timeout,
        )
    return ArxivService(client=client)


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/arxiv/fetch",
    response_model=ArxivFetchResponse,
    summary="Fetch trending arXiv papers",
)
async def fetch_arxiv(
    request: Request,
    body: ArxivFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> ArxivFetchResponse:
    service = _get_arxiv_service(request)
    try:
        return await service.fetch_and_normalize(
            domain_keywords=body.domain_keywords,
            categories=body.categories,
            max_results=body.max_results,
        )
    except ArxivAPIError as exc:
        logger.error(
            "arxiv_api_error",
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="arxiv_unavailable",
            message="arXiv API is not available",
        ) from exc
```

- [x] **Step 4: Run all arXiv tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_arxiv_endpoints.py tests/unit/services/test_arxiv.py tests/unit/services/test_arxiv_client.py -v`

Expected: All tests PASS

- [x] **Step 5: Commit**

```bash
git add src/api/routers/trends.py tests/unit/api/test_arxiv_endpoints.py
git commit -m "feat(trend-005): add arXiv API endpoint with auth, rate limiting, and tests"
```

---

### Task 6: Full Regression + Lint + Format

- [x] **Step 1: Run full test suite**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest --cov=src --cov-report=term-missing -v`

Expected: All tests pass, no regressions in existing sources.

- [x] **Step 2: Run ruff check and format**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/ tests/ && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/ tests/`

Expected: No lint or format errors. If any, fix and re-run.

- [x] **Step 3: Run ruff format (apply fixes if needed)**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format src/ tests/`

- [x] **Step 4: Commit formatting fixes (if any)**

```bash
git add -u
git commit -m "style(trend-005): apply ruff formatting to arXiv modules"
```

---

### Task 7: Update Project Tracking

- [x] **Step 1: Update PROGRESS.md**

Change TREND-005 row to:

```
| TREND-005 | arXiv Paper Feed          | Done | `feature/TREND-005-arxiv-paper-feed` | [plan](../docs/superpowers/plans/2026-03-15-trend-005-arxiv-paper-feed.md) | [spec](../docs/superpowers/specs/2026-03-15-trend-005-arxiv-paper-feed-design.md) |
```

- [x] **Step 2: Update BACKLOG.md**

Add status, plan, and spec links to the TREND-005 entry:

```markdown
### TREND-005: arXiv Paper Feed [Should] — DONE
**As a** researcher, **I want** recent arXiv papers in my domain tracked, **so that** academic trends are captured.
- **Status**: Done (branch `feature/TREND-005-arxiv-paper-feed`)
- **Plan**: [`docs/superpowers/plans/2026-03-15-trend-005-arxiv-paper-feed.md`](../docs/superpowers/plans/2026-03-15-trend-005-arxiv-paper-feed.md)
- **Spec**: [`docs/superpowers/specs/2026-03-15-trend-005-arxiv-paper-feed-design.md`](../docs/superpowers/specs/2026-03-15-trend-005-arxiv-paper-feed-design.md)
```

- [x] **Step 3: Commit tracking updates**

```bash
git add project-management/PROGRESS.md project-management/BACKLOG.md
git commit -m "docs: update tracking — TREND-005 Done"
```
