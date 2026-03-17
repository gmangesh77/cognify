# RESEARCH-002: Web Search Agent Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a SerpAPI-based web search agent that replaces the stub research agent, executes search queries from research facets, deduplicates results, and extracts structured claims via LLM.

**Architecture:** `WebSearchAgent` callable class satisfying `AgentFunction` signature. `SerpAPIClient` transport layer using httpx. LLM-based claims extraction with snippet fallback. Plugs into the existing orchestrator via `build_graph(llm, dispatcher, agent)`.

**Tech Stack:** httpx (existing), SerpAPI REST, langchain-core (FakeLLM in tests), Pydantic, pytest

**Spec:** [`docs/superpowers/specs/2026-03-17-research-002-web-search-agent-design.md`](../specs/2026-03-17-research-002-web-search-agent-design.md)

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/services/serpapi_client.py` | HTTP transport: SerpAPIClient, SerpAPIError, SerpAPIResult |
| `src/agents/research/web_search.py` | WebSearchAgent callable class (queries → dedup → claims → FacetFindings) |
| `src/config/settings.py` | Add serpapi_* settings (modify) |
| `tests/unit/services/test_serpapi_client.py` | Client tests with mocked httpx |
| `tests/unit/agents/research/test_web_search.py` | Agent tests with mocked client + FakeLLM |

---

## Task 1: Add SerpAPI Settings

**Files:**
- Modify: `src/config/settings.py`

- [ ] **Step 1: Add SerpAPI settings**

Add after the arXiv settings block at the end of `src/config/settings.py`:

```python
    # SerpAPI integration
    serpapi_api_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search"
    serpapi_timeout: float = 10.0
    serpapi_results_per_query: int = 10
```

- [ ] **Step 2: Run existing tests for regressions**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_app.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/config/settings.py
git commit -m "chore(research-002): add SerpAPI settings"
```

---

## Task 2: SerpAPI Client (Transport Layer)

**Files:**
- Create: `src/services/serpapi_client.py`
- Create: `tests/unit/services/test_serpapi_client.py`

- [ ] **Step 1: Write failing tests for SerpAPI client**

Create `tests/unit/services/test_serpapi_client.py`:

```python
"""Tests for the SerpAPI HTTP client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.serpapi_client import (
    SerpAPIClient,
    SerpAPIError,
    SerpAPIResult,
)


def _serpapi_response(num_results: int = 3) -> dict:
    """Build a fake SerpAPI JSON response."""
    return {
        "organic_results": [
            {
                "position": i + 1,
                "title": f"Result {i + 1}",
                "link": f"https://example.com/article-{i + 1}",
                "snippet": f"This is the snippet for result {i + 1}.",
            }
            for i in range(num_results)
        ]
    }


def _make_client() -> SerpAPIClient:
    return SerpAPIClient(
        api_key="test-key",
        base_url="https://serpapi.com/search",
        timeout=5.0,
        results_per_query=10,
    )


class TestSerpAPIClientSearch:
    async def test_returns_parsed_results(self) -> None:
        mock_resp = httpx.Response(200, json=_serpapi_response(3))
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("AI security", num_results=3)

        assert len(results) == 3
        assert all(isinstance(r, SerpAPIResult) for r in results)
        assert results[0].title == "Result 1"
        assert results[0].link == "https://example.com/article-1"
        assert results[0].position == 1

    async def test_empty_results(self) -> None:
        mock_resp = httpx.Response(200, json={"organic_results": []})
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("obscure query")

        assert results == []

    async def test_skips_results_without_snippet(self) -> None:
        resp_data = {
            "organic_results": [
                {"position": 1, "title": "Good", "link": "https://a.com", "snippet": "Has snippet"},
                {"position": 2, "title": "Bad", "link": "https://b.com"},
            ]
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("test")

        assert len(results) == 1
        assert results[0].title == "Good"

    async def test_raises_on_api_error(self) -> None:
        mock_resp = httpx.Response(401, json={"error": "Invalid API key"})
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SerpAPIError, match="401"):
                await client.search("test")

    async def test_raises_on_timeout(self) -> None:
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SerpAPIError, match="timed out"):
                await client.search("test")

    async def test_raises_on_connection_error(self) -> None:
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SerpAPIError, match="connection"):
                await client.search("test")

    async def test_passes_correct_params(self) -> None:
        mock_resp = httpx.Response(200, json=_serpapi_response(1))
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            await client.search("AI security", num_results=5)

            params = mock_client.get.call_args.kwargs["params"]
            assert params["q"] == "AI security"
            assert params["num"] == 5
            assert params["api_key"] == "test-key"
            assert params["engine"] == "google"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_serpapi_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement SerpAPI client**

Create `src/services/serpapi_client.py`:

```python
"""SerpAPI HTTP client for web search.

Transport layer only — handles HTTP calls, error wrapping, and response
parsing. No business logic. Follows the same pattern as hackernews_client.py.
"""

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class SerpAPIError(Exception):
    """Raised when SerpAPI returns an error or is unreachable."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class SerpAPIResult(BaseModel, frozen=True):
    """Typed search result from SerpAPI organic results."""

    title: str
    link: str
    snippet: str
    position: int


class SerpAPIClient:
    """HTTP client for SerpAPI Google search."""

    def __init__(
        self, api_key: str, base_url: str, timeout: float, results_per_query: int = 10
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._results_per_query = results_per_query

    async def search(
        self, query: str, num_results: int | None = None
    ) -> list[SerpAPIResult]:
        """Execute a search query and return organic results."""
        params = {
            "q": query,
            "num": num_results or self._results_per_query,
            "api_key": self._api_key,
            "engine": "google",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
            ) as client:
                resp = await client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            raise SerpAPIError(f"SerpAPI timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            raise SerpAPIError(
                f"SerpAPI connection failed: {exc}"
            ) from exc

        if not resp.is_success:
            raise SerpAPIError(
                f"SerpAPI returned {resp.status_code}",
                status_code=resp.status_code,
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise SerpAPIError(f"Invalid JSON response: {exc}") from exc

        return self._parse_results(data)

    def _parse_results(
        self, data: dict[str, object]
    ) -> list[SerpAPIResult]:
        """Parse organic_results, skipping entries without snippet."""
        raw: list[dict[str, object]] = data.get("organic_results", [])  # type: ignore[assignment]
        results: list[SerpAPIResult] = []
        for item in raw:
            snippet = item.get("snippet")
            if not snippet:
                continue
            results.append(
                SerpAPIResult(
                    title=str(item["title"]),
                    link=str(item["link"]),
                    snippet=str(snippet),
                    position=int(item.get("position", 0)),
                )
            )
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_serpapi_client.py -v`
Expected: All tests PASS

- [ ] **Step 5: Lint**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/services/serpapi_client.py && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/services/serpapi_client.py`
Expected: No issues

- [ ] **Step 6: Commit**

```bash
git add src/services/serpapi_client.py tests/unit/services/test_serpapi_client.py
git commit -m "feat(research-002): add SerpAPI client transport layer"
```

---

## Task 3: WebSearchAgent

**Files:**
- Create: `src/agents/research/web_search.py`
- Create: `tests/unit/agents/research/test_web_search.py`

- [ ] **Step 1: Write failing tests for WebSearchAgent**

Create `tests/unit/agents/research/test_web_search.py`:

```python
"""Tests for the WebSearchAgent callable class."""

import json
from unittest.mock import AsyncMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.web_search import WebSearchAgent
from src.models.research import FacetFindings, ResearchFacet, SourceDocument
from src.services.serpapi_client import SerpAPIClient, SerpAPIError, SerpAPIResult


def _make_facet(
    index: int = 0, queries: list[str] | None = None
) -> ResearchFacet:
    return ResearchFacet(
        index=index,
        title="AI Security",
        description="Emerging AI security threats",
        search_queries=queries or ["AI security 2026"],
    )


def _make_results(num: int = 3, url_prefix: str = "https://a.com") -> list[SerpAPIResult]:
    return [
        SerpAPIResult(
            title=f"Result {i}",
            link=f"{url_prefix}/article-{i}",
            snippet=f"Snippet about topic for result {i}.",
            position=i + 1,
        )
        for i in range(num)
    ]


def _claims_json(
    claims: list[str] | None = None, summary: str = "Test summary"
) -> str:
    return json.dumps({
        "claims": claims or ["Claim 1", "Claim 2", "Claim 3"],
        "summary": summary,
    })


class TestWebSearchAgentHappyPath:
    async def test_returns_facet_findings(self) -> None:
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = _make_results(3)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert isinstance(result, FacetFindings)
        assert result.facet_index == 0
        assert len(result.sources) == 3
        assert len(result.claims) == 3
        assert result.summary == "Test summary"

    async def test_sources_are_source_documents(self) -> None:
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = _make_results(2)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        for src in result.sources:
            assert isinstance(src, SourceDocument)
            assert src.url.startswith("https://")
            assert src.snippet != ""
            assert src.retrieved_at is not None


class TestWebSearchAgentDeduplication:
    async def test_deduplicates_across_queries(self) -> None:
        """3 queries returning overlapping URLs → deduplicated."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        # Query 1 and 2 share a URL
        results_q1 = _make_results(2, "https://a.com")
        results_q2 = [
            SerpAPIResult(title="Dup", link="https://a.com/article-0", snippet="Dup snippet", position=1),
            SerpAPIResult(title="Unique", link="https://b.com/unique", snippet="Unique snippet", position=2),
        ]
        mock_client.search.side_effect = [results_q1, results_q2]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = WebSearchAgent(mock_client, llm)
        result = await agent(facet)

        urls = [s.url for s in result.sources]
        assert len(urls) == len(set(urls))  # No duplicates
        assert len(result.sources) == 3  # 2 from q1 + 1 unique from q2


class TestWebSearchAgentErrors:
    async def test_partial_query_failure(self) -> None:
        """One query fails, others succeed → partial results."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.side_effect = [
            _make_results(2),
            SerpAPIError("API error"),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = WebSearchAgent(mock_client, llm)
        result = await agent(facet)

        assert len(result.sources) == 2  # Only from successful query
        assert result.claims != []

    async def test_all_queries_fail(self) -> None:
        """All queries fail → empty FacetFindings."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.side_effect = SerpAPIError("API error")
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = WebSearchAgent(mock_client, llm)
        result = await agent(facet)

        assert result.sources == []
        assert result.claims == []
        assert result.summary == ""

    async def test_llm_fallback_on_malformed_json(self) -> None:
        """LLM returns bad JSON → falls back to snippet-based claims."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = _make_results(3)
        llm = FakeListChatModel(responses=["not valid json"])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert len(result.sources) == 3
        # Fallback: first 3 snippets become claims
        assert len(result.claims) >= 1
        assert result.summary != ""


class TestWebSearchAgentSanitization:
    async def test_truncates_long_snippets(self) -> None:
        """Snippets longer than 500 chars are truncated."""
        long_snippet = "A" * 1000
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = [
            SerpAPIResult(title="Long", link="https://a.com/long", snippet=long_snippet, position=1),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert len(result.sources[0].snippet) <= 500

    async def test_strips_control_characters(self) -> None:
        """Control characters in snippets are removed."""
        dirty_snippet = "Clean\x00text\x0bhere\x1fend"
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = [
            SerpAPIResult(title="Dirty", link="https://a.com/dirty", snippet=dirty_snippet, position=1),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        snippet = result.sources[0].snippet
        assert "\x00" not in snippet
        assert "\x0b" not in snippet
        assert "Clean" in snippet
        assert "text" in snippet


class TestWebSearchAgentDeduplicationNormalization:
    async def test_normalizes_trailing_slash(self) -> None:
        """URLs with/without trailing slash are treated as same."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.side_effect = [
            [SerpAPIResult(title="A", link="https://a.com/page/", snippet="S1", position=1)],
            [SerpAPIResult(title="B", link="https://a.com/page", snippet="S2", position=1)],
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = WebSearchAgent(mock_client, llm)
        result = await agent(facet)

        assert len(result.sources) == 1  # Deduped


class TestWebSearchAgentCallable:
    async def test_works_with_dispatcher(self) -> None:
        """Verify __call__ satisfies AgentFunction for the dispatcher."""
        from src.services.task_dispatch import AsyncIODispatcher

        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = _make_results(2)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = WebSearchAgent(mock_client, llm)
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(0), _make_facet(1)]

        # Need a fresh LLM response for each facet
        llm = FakeListChatModel(responses=[_claims_json(), _claims_json()])
        agent = WebSearchAgent(mock_client, llm)

        results = await dispatcher.dispatch(facets, agent)
        assert len(results) == 2
        assert results[0].facet_index == 0
        assert results[1].facet_index == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_web_search.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement WebSearchAgent**

Create `src/agents/research/web_search.py`:

```python
"""Web search agent using SerpAPI.

Replaces stub_research_agent from RESEARCH-001. Executes search queries
from a research facet, deduplicates by URL, and extracts claims via LLM.
Satisfies the AgentFunction signature as a callable class.
"""

import asyncio
import json
import re
from datetime import UTC, datetime

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.research import FacetFindings, ResearchFacet, SourceDocument
from src.services.serpapi_client import SerpAPIClient, SerpAPIError, SerpAPIResult

logger = structlog.get_logger()

_CLAIMS_SYSTEM = (
    "You are a research analyst. Extract key factual claims "
    "and a brief summary from search results. Respond with JSON only."
)

_CLAIMS_TEMPLATE = (
    "Search results about '{title}':\n\n{snippets}\n\n"
    "Extract 3-5 key factual claims and a 2-3 sentence summary.\n"
    'Return JSON: {{"claims": ["..."], "summary": "..."}}'
)

_MAX_SNIPPET_CHARS = 500
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitize(text: str) -> str:
    """Strip control characters from text (RISK-005 mitigation)."""
    return _CONTROL_CHAR_RE.sub("", text)[:_MAX_SNIPPET_CHARS]


class WebSearchAgent:
    """Callable research agent that searches the web via SerpAPI."""

    def __init__(
        self, serpapi_client: SerpAPIClient, llm: BaseChatModel
    ) -> None:
        self._client = serpapi_client
        self._llm = llm

    async def __call__(self, facet: ResearchFacet) -> FacetFindings:
        """Execute search, dedup, extract claims, return findings."""
        raw = await self._execute_queries(facet.search_queries)
        unique = self._deduplicate(raw)
        if not unique:
            return self._empty_findings(facet.index)
        sources = self._to_source_documents(unique)
        claims, summary = await self._extract_claims(facet.title, sources)
        return FacetFindings(
            facet_index=facet.index,
            sources=sources,
            claims=claims,
            summary=summary,
        )

    async def _execute_queries(
        self, queries: list[str]
    ) -> list[SerpAPIResult]:
        """Run all queries in parallel, collect results."""
        tasks = [self._safe_search(q) for q in queries]
        nested = await asyncio.gather(*tasks)
        return [r for batch in nested for r in batch]

    async def _safe_search(
        self, query: str
    ) -> list[SerpAPIResult]:
        """Search with error handling — returns empty on failure."""
        try:
            return await self._client.search(query)
        except SerpAPIError as exc:
            logger.warning(
                "serpapi_query_failed", query=query, error=str(exc)
            )
            return []

    def _deduplicate(
        self, results: list[SerpAPIResult]
    ) -> list[SerpAPIResult]:
        """Deduplicate by normalized URL, keep first occurrence."""
        seen: set[str] = set()
        unique: list[SerpAPIResult] = []
        for r in results:
            key = r.link.rstrip("/").lower()
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def _to_source_documents(
        self, results: list[SerpAPIResult]
    ) -> list[SourceDocument]:
        """Convert SerpAPI results to SourceDocument models."""
        now = datetime.now(UTC)
        return [
            SourceDocument(
                url=r.link,
                title=_sanitize(r.title),
                snippet=_sanitize(r.snippet),
                retrieved_at=now,
            )
            for r in results
        ]

    async def _extract_claims(
        self, title: str, sources: list[SourceDocument]
    ) -> tuple[list[str], str]:
        """Extract claims + summary via LLM, with fallback."""
        snippets = "\n".join(
            f"- [{s.title}]: {s.snippet}" for s in sources
        )
        msg = _CLAIMS_TEMPLATE.format(
            title=_sanitize(title), snippets=snippets
        )
        messages = [
            SystemMessage(content=_CLAIMS_SYSTEM),
            HumanMessage(content=msg),
        ]
        try:
            resp = await self._llm.ainvoke(messages)
            data = json.loads(resp.content)
            claims = data["claims"]
            summary = data["summary"]
            return claims, summary
        except (json.JSONDecodeError, KeyError, ValidationError) as exc:
            logger.warning("claims_extraction_failed", error=str(exc))
            return self._fallback_claims(title, sources)

    def _fallback_claims(
        self, title: str, sources: list[SourceDocument]
    ) -> tuple[list[str], str]:
        """Fallback: use snippets as claims if LLM fails."""
        claims = [s.snippet[:200] for s in sources[:3]]
        summary = f"Search results for: {title}"
        return claims, summary

    def _empty_findings(self, facet_index: int) -> FacetFindings:
        """Return empty findings when all queries fail."""
        return FacetFindings(
            facet_index=facet_index, sources=[], claims=[], summary=""
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_web_search.py -v`
Expected: All tests PASS

- [ ] **Step 5: Lint**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/agents/research/web_search.py && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/agents/research/web_search.py`
Expected: No issues

- [ ] **Step 6: Commit**

```bash
git add src/agents/research/web_search.py tests/unit/agents/research/test_web_search.py
git commit -m "feat(research-002): add WebSearchAgent with SerpAPI and LLM claims extraction"
```

---

## Task 4: Lint, Full Test Suite, Update Progress

**Files:**
- Modify: `project-management/PROGRESS.md`

- [ ] **Step 1: Run linter on all new code**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/services/serpapi_client.py src/agents/research/web_search.py`
Expected: No issues

- [ ] **Step 2: Run formatter check**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/ tests/`
Expected: No formatting issues. Fix any that arise.

- [ ] **Step 3: Run full test suite with coverage**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v --cov=src --cov-report=term-missing --tb=short`
Expected: All tests PASS, coverage ≥ 80% on new code

- [ ] **Step 4: Update PROGRESS.md**

Update the RESEARCH-002 row in `project-management/PROGRESS.md`:

| RESEARCH-002 | Web Search Agent | Done | `feature/RESEARCH-002-web-search-agent` | [plan](../docs/superpowers/plans/2026-03-17-research-002-web-search-agent.md) | [spec](../docs/superpowers/specs/2026-03-17-research-002-web-search-agent-design.md) |

Remove the RESEARCH-002 line from the "Stubs from RESEARCH-001 to replace" section (it's now done). Keep the RESEARCH-003 and infra ticket notes.

- [ ] **Step 5: Commit progress update**

```bash
git add project-management/PROGRESS.md
git commit -m "docs: update PROGRESS.md — RESEARCH-002 done"
```
