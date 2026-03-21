# RESEARCH-004: Literature Review Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Literature Review Agent that searches Semantic Scholar for academic papers, integrating alongside the existing web search agent via planner-tagged facet routing.

**Architecture:** New `SemanticScholarClient` (HTTP transport) + `LiteratureReviewAgent` (callable agent following `AgentFunction` protocol). The research planner tags facets with `source_type` (web/academic/both), and the orchestrator's `dispatch_agents` node routes facets to the correct agent. All findings flow through the existing Milvus indexing and RAG pipeline unchanged.

**Tech Stack:** Python 3.12, httpx (async HTTP), Pydantic (frozen models), structlog (logging), LangChain (LLM calls), LangGraph (orchestrator), pytest + FakeListChatModel (testing)

**Spec:** [`docs/superpowers/specs/2026-03-21-research-004-literature-review-agent-design.md`](../specs/2026-03-21-research-004-literature-review-agent-design.md)

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/services/semantic_scholar.py` | HTTP client for Semantic Scholar API + `ScholarPaper` model + `SemanticScholarError` |
| `src/agents/research/literature_review.py` | `LiteratureReviewAgent` callable class (mirrors `web_search.py`) |
| `tests/unit/services/test_semantic_scholar.py` | Unit tests for `SemanticScholarClient` |
| `tests/unit/agents/research/test_literature_review.py` | Unit tests for `LiteratureReviewAgent` |

### Modified Files

| File | Change |
|------|--------|
| `src/models/research.py:22-28` | Add `source_type: Literal[...]` to `ResearchFacet` |
| `src/config/settings.py:67-71` | Add Semantic Scholar config fields after SerpAPI block |
| `src/agents/research/planner.py:18-32` | Update prompts to emit `source_type` per facet |
| `src/agents/research/orchestrator.py:90-130` | Add `literature_agent_fn` param to `build_graph`, update `dispatch_agents` routing |
| `tests/unit/agents/research/test_planner.py` | Tests for `source_type` in plan output |
| `tests/unit/agents/research/test_orchestrator.py` | Tests for dual-agent routing + backward compat |

---

## Task 1: Add `source_type` to ResearchFacet Model

**Files:**
- Modify: `src/models/research.py:22-28`
- Test: existing tests must still pass

- [ ] **Step 1: Add `source_type` field to `ResearchFacet`**

In `src/models/research.py`, add the import and field:

```python
# Add to imports at line 1-2:
from typing import Literal

# Update ResearchFacet at line 22-28:
class ResearchFacet(BaseModel, frozen=True):
    """A single research facet within a research plan."""

    index: int
    title: str
    description: str
    search_queries: list[str]
    source_type: Literal["web", "academic", "both"] = "web"
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/ -q --tb=short 2>&1 | tail -5`
Expected: All 697 tests pass (no regressions — default `"web"` preserves backward compat)

- [ ] **Step 3: Commit**

```bash
cd D:/Workbench/github/cognify-research-004 && git add src/models/research.py && git commit -m "feat(research-004): add source_type field to ResearchFacet"
```

---

## Task 2: SemanticScholarClient + ScholarPaper Model

**Files:**
- Create: `src/services/semantic_scholar.py`
- Create: `tests/unit/services/test_semantic_scholar.py`

- [ ] **Step 1: Write the test file**

Create `tests/unit/services/test_semantic_scholar.py`:

```python
"""Tests for the Semantic Scholar HTTP client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.semantic_scholar import (
    ScholarPaper,
    SemanticScholarClient,
    SemanticScholarError,
)


def _scholar_response(num_results: int = 3) -> dict:
    """Build a fake Semantic Scholar search response."""
    return {
        "total": num_results,
        "data": [
            {
                "paperId": f"paper-{i}",
                "title": f"Paper Title {i}",
                "abstract": f"This is the abstract for paper {i}.",
                "authors": [{"name": f"Author {i}"}],
                "year": 2025,
                "citationCount": 10 * (i + 1),
                "venue": "NeurIPS",
                "url": f"https://semanticscholar.org/paper/{i}",
                "externalIds": {"DOI": f"10.1234/paper.{i}"},
            }
            for i in range(num_results)
        ],
    }


def _make_client() -> SemanticScholarClient:
    return SemanticScholarClient(
        base_url="https://api.semanticscholar.org",
        timeout=5.0,
    )


class TestSemanticScholarClientSearch:
    async def test_returns_parsed_papers(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(3))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("machine learning security")

        assert len(results) == 3
        assert all(isinstance(r, ScholarPaper) for r in results)
        assert results[0].paper_id == "paper-0"
        assert results[0].title == "Paper Title 0"
        assert results[0].authors == ["Author 0"]
        assert results[0].citation_count == 10

    async def test_empty_results(self) -> None:
        mock_resp = httpx.Response(200, json={"total": 0, "data": []})
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("obscure query xyz")

        assert results == []

    async def test_skips_papers_without_abstract(self) -> None:
        resp_data = {
            "total": 2,
            "data": [
                {
                    "paperId": "p1",
                    "title": "Has Abstract",
                    "abstract": "Real abstract",
                    "authors": [{"name": "A"}],
                    "year": 2025,
                    "citationCount": 5,
                    "venue": "ICML",
                    "url": "https://s2.org/p1",
                    "externalIds": {},
                },
                {
                    "paperId": "p2",
                    "title": "No Abstract",
                    "abstract": None,
                    "authors": [{"name": "B"}],
                    "year": 2024,
                    "citationCount": 2,
                    "venue": "",
                    "url": "https://s2.org/p2",
                    "externalIds": {},
                },
            ],
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("test")

        assert len(results) == 1
        assert results[0].title == "Has Abstract"

    async def test_raises_on_api_error(self) -> None:
        mock_resp = httpx.Response(429, json={"error": "Rate limited"})
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SemanticScholarError, match="429"):
                await client.search("test")

    async def test_raises_on_timeout(self) -> None:
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SemanticScholarError, match="timed out"):
                await client.search("test")

    async def test_raises_on_connection_error(self) -> None:
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SemanticScholarError, match="refused"):
                await client.search("test")

    async def test_passes_correct_params(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(1))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            await client.search("AI security", max_results=5)

            call_kwargs = mock_client.get.call_args
            assert "paper/search" in str(call_kwargs)
            params = call_kwargs.kwargs["params"]
            assert params["query"] == "AI security"
            assert params["limit"] == 5

    async def test_configurable_base_url(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(1))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = SemanticScholarClient(
                base_url="https://test.local",
                timeout=5.0,
            )
            await client.search("test")

            url_arg = mock_client.get.call_args.args[0]
            assert url_arg.startswith("https://test.local")

    async def test_extracts_doi(self) -> None:
        resp_data = {
            "total": 1,
            "data": [
                {
                    "paperId": "p1",
                    "title": "DOI Paper",
                    "abstract": "Has DOI",
                    "authors": [],
                    "year": 2025,
                    "citationCount": 3,
                    "venue": "arXiv",
                    "url": "https://s2.org/p1",
                    "externalIds": {"DOI": "10.1234/test"},
                },
            ],
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("DOI test")

        assert results[0].doi == "10.1234/test"

    async def test_handles_missing_doi(self) -> None:
        resp_data = {
            "total": 1,
            "data": [
                {
                    "paperId": "p1",
                    "title": "No DOI",
                    "abstract": "No DOI",
                    "authors": [],
                    "year": 2025,
                    "citationCount": 0,
                    "venue": "",
                    "url": "https://s2.org/p1",
                    "externalIds": {},
                },
            ],
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("no doi")

        assert results[0].doi is None


class TestSemanticScholarClientApiKey:
    async def test_api_key_in_headers(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(1))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = SemanticScholarClient(
                base_url="https://api.semanticscholar.org",
                api_key="test-key-123",
                timeout=5.0,
            )
            await client.search("test")

            init_kwargs = mock_cls.call_args.kwargs
            assert init_kwargs["headers"]["x-api-key"] == "test-key-123"

    async def test_no_api_key_header_when_none(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(1))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()  # no api_key
            await client.search("test")

            init_kwargs = mock_cls.call_args.kwargs
            headers = init_kwargs.get("headers", {})
            assert "x-api-key" not in headers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/unit/services/test_semantic_scholar.py -v 2>&1 | head -10`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.semantic_scholar'`

- [ ] **Step 3: Write the implementation**

Create `src/services/semantic_scholar.py`:

```python
"""Semantic Scholar HTTP client for academic paper search.

Transport layer only — handles HTTP calls, error wrapping, and response
parsing. Follows the same pattern as serpapi_client.py.
"""

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger()

_SEARCH_FIELDS = (
    "paperId,title,abstract,authors,year,"
    "citationCount,venue,externalIds,url"
)


class SemanticScholarError(Exception):
    """Raised when Semantic Scholar API returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class ScholarPaper(BaseModel, frozen=True):
    """Typed paper result from Semantic Scholar search.

    Note: abstract is non-optional (str, not str | None) because
    _parse_results filters out papers without abstracts before
    constructing this model. Spec says str | None — this is an
    intentional tightening at the model boundary.
    """

    paper_id: str
    title: str
    abstract: str
    authors: list[str]
    year: int | None = None
    citation_count: int = 0
    venue: str | None = None
    url: str
    doi: str | None = None


class SemanticScholarClient:
    """HTTP client for Semantic Scholar paper search."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._api_key = api_key

    async def search(
        self, query: str, max_results: int = 5
    ) -> list[ScholarPaper]:
        """Search for papers matching a query string."""
        url = f"{self._base_url}/graph/v1/paper/search"
        params: dict[str, str | int] = {
            "query": query,
            "limit": max_results,
            "fields": _SEARCH_FIELDS,
        }
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=headers
            ) as client:
                resp = await client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise SemanticScholarError(
                f"Semantic Scholar timed out: {exc}"
            ) from exc
        except httpx.ConnectError as exc:
            raise SemanticScholarError(
                f"Semantic Scholar connection failed: {exc}"
            ) from exc

        if not resp.is_success:
            raise SemanticScholarError(
                f"Semantic Scholar returned {resp.status_code}",
                status_code=resp.status_code,
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise SemanticScholarError(
                f"Invalid JSON response: {exc}"
            ) from exc

        return self._parse_results(data)

    def _parse_results(self, data: dict[str, object]) -> list[ScholarPaper]:
        """Parse search results, skipping papers without abstracts."""
        raw: list[dict[str, object]] = data.get("data", [])  # type: ignore[assignment]
        papers: list[ScholarPaper] = []
        for item in raw:
            abstract = item.get("abstract")
            if not abstract:
                continue
            authors_raw = item.get("authors", [])
            external_ids = item.get("externalIds", {}) or {}
            papers.append(
                ScholarPaper(
                    paper_id=str(item["paperId"]),
                    title=str(item["title"]),
                    abstract=str(abstract),
                    authors=[str(a["name"]) for a in authors_raw],  # type: ignore[index]
                    year=int(item["year"]) if item.get("year") else None,  # type: ignore[arg-type]
                    citation_count=int(item.get("citationCount", 0)),  # type: ignore[arg-type]
                    venue=str(item["venue"]) if item.get("venue") else None,
                    url=str(item.get("url", "")),
                    doi=str(external_ids.get("DOI")) if external_ids.get("DOI") else None,  # type: ignore[union-attr]
                )
            )
        return papers
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/unit/services/test_semantic_scholar.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-research-004 && git add src/services/semantic_scholar.py tests/unit/services/test_semantic_scholar.py && git commit -m "feat(research-004): add SemanticScholarClient with ScholarPaper model"
```

---

## Task 3: Settings Configuration

**Files:**
- Modify: `src/config/settings.py:67-71`

- [ ] **Step 1: Add Semantic Scholar config fields**

In `src/config/settings.py`, add after the SerpAPI block (after line 71):

```python
    # Semantic Scholar integration
    semantic_scholar_base_url: str = "https://api.semanticscholar.org"
    semantic_scholar_api_key: str = ""
    semantic_scholar_timeout: float = 10.0
    semantic_scholar_results_per_query: int = 5
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/ -q --tb=short 2>&1 | tail -5`
Expected: All tests pass (new fields have defaults)

- [ ] **Step 3: Commit**

```bash
cd D:/Workbench/github/cognify-research-004 && git add src/config/settings.py && git commit -m "feat(research-004): add Semantic Scholar config to settings"
```

---

## Task 4: LiteratureReviewAgent

**Files:**
- Create: `src/agents/research/literature_review.py`
- Create: `tests/unit/agents/research/test_literature_review.py`

- [ ] **Step 1: Write the test file**

Create `tests/unit/agents/research/test_literature_review.py`:

```python
"""Tests for the LiteratureReviewAgent callable class."""

import json
from unittest.mock import AsyncMock

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.literature_review import LiteratureReviewAgent
from src.models.research import FacetFindings, ResearchFacet, SourceDocument
from src.services.semantic_scholar import (
    ScholarPaper,
    SemanticScholarClient,
    SemanticScholarError,
)


def _make_facet(index: int = 0, queries: list[str] | None = None) -> ResearchFacet:
    return ResearchFacet(
        index=index,
        title="Zero-Day Detection",
        description="ML-based detection methods",
        search_queries=queries or ["zero-day detection ML"],
        source_type="academic",
    )


def _make_papers(
    num: int = 3, id_prefix: str = "paper"
) -> list[ScholarPaper]:
    return [
        ScholarPaper(
            paper_id=f"{id_prefix}-{i}",
            title=f"Paper Title {i}",
            abstract=f"This paper investigates topic {i} with novel methods.",
            authors=[f"Author {i}"],
            year=2025,
            citation_count=10 * (i + 1),
            venue="NeurIPS",
            url=f"https://semanticscholar.org/paper/{id_prefix}-{i}",
            doi=f"10.1234/{id_prefix}.{i}",
        )
        for i in range(num)
    ]


def _claims_json(
    claims: list[str] | None = None, summary: str = "Academic summary"
) -> str:
    return json.dumps(
        {
            "claims": claims or [
                "Smith et al. (2025) found method A outperforms B",
                "Detection accuracy improved by 15%",
                "Novel approach uses transformer architecture",
            ],
            "summary": summary,
        }
    )


class TestLiteratureReviewAgentHappyPath:
    async def test_returns_facet_findings(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(3)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert isinstance(result, FacetFindings)
        assert result.facet_index == 0
        assert len(result.sources) == 3
        assert len(result.claims) == 3
        assert result.summary == "Academic summary"

    async def test_sources_are_source_documents(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(2)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        for src in result.sources:
            assert isinstance(src, SourceDocument)
            assert src.url.startswith("https://")
            assert src.snippet != ""
            assert src.retrieved_at is not None
            assert src.author is not None

    async def test_maps_year_to_published_at(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(1)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert result.sources[0].published_at is not None
        assert result.sources[0].published_at.year == 2025

    async def test_uses_doi_url_when_url_empty(self) -> None:
        paper = ScholarPaper(
            paper_id="p1",
            title="DOI Paper",
            abstract="Has DOI but no URL",
            authors=["A"],
            year=2025,
            citation_count=5,
            url="",
            doi="10.1234/test",
        )
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = [paper]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert result.sources[0].url == "https://doi.org/10.1234/test"


class TestLiteratureReviewAgentDeduplication:
    async def test_deduplicates_by_paper_id(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        papers_q1 = _make_papers(2, "paper")
        papers_q2 = [
            ScholarPaper(
                paper_id="paper-0",  # duplicate
                title="Dup",
                abstract="Dup abstract",
                authors=["A"],
                year=2025,
                citation_count=5,
                url="https://s2.org/dup",
            ),
            ScholarPaper(
                paper_id="unique-1",
                title="Unique",
                abstract="Unique abstract",
                authors=["B"],
                year=2024,
                citation_count=3,
                url="https://s2.org/unique",
            ),
        ]
        mock_client.search.side_effect = [papers_q1, papers_q2]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(facet)

        assert len(result.sources) == 3  # 2 from q1 + 1 unique from q2


class TestLiteratureReviewAgentSanitization:
    async def test_strips_control_characters(self) -> None:
        paper = ScholarPaper(
            paper_id="p1",
            title="Clean\x00Title\x0bHere",
            abstract="Clean\x00abstract\x1ftext",
            authors=["A"],
            year=2025,
            citation_count=5,
            url="https://s2.org/p1",
        )
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = [paper]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert "\x00" not in result.sources[0].title
        assert "\x00" not in result.sources[0].snippet
        assert "\x0b" not in result.sources[0].title

    async def test_truncates_long_abstracts(self) -> None:
        paper = ScholarPaper(
            paper_id="p1",
            title="Long",
            abstract="A" * 1000,
            authors=["A"],
            year=2025,
            citation_count=5,
            url="https://s2.org/p1",
        )
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = [paper]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert len(result.sources[0].snippet) <= 500


class TestLiteratureReviewAgentErrors:
    async def test_partial_query_failure(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.side_effect = [
            _make_papers(2),
            SemanticScholarError("API error"),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(facet)

        assert len(result.sources) == 2
        assert result.claims != []

    async def test_all_queries_fail(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.side_effect = SemanticScholarError("API error")
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(facet)

        assert result.sources == []
        assert result.claims == []
        assert result.summary == ""

    async def test_llm_fallback_on_malformed_json(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(3)
        llm = FakeListChatModel(responses=["not valid json"])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert len(result.sources) == 3
        assert len(result.claims) >= 1
        assert result.summary != ""


class TestLiteratureReviewAgentUrlFallback:
    async def test_fallback_to_semanticscholar_url(self) -> None:
        paper = ScholarPaper(
            paper_id="p1",
            title="No URL No DOI",
            abstract="Has neither URL nor DOI",
            authors=["A"],
            year=2025,
            citation_count=5,
            url="",
            doi=None,
        )
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = [paper]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert result.sources[0].url == "https://semanticscholar.org/paper/p1"


class TestLiteratureReviewAgentConfigurable:
    async def test_max_results_per_query(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(3)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm, max_results_per_query=10)
        await agent(_make_facet())

        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs.get("max_results") == 10 or call_kwargs.args[1:] == (10,)

    async def test_works_with_dispatcher(self) -> None:
        from src.services.task_dispatch import AsyncIODispatcher

        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(2)
        llm = FakeListChatModel(responses=[_claims_json(), _claims_json()])
        agent = LiteratureReviewAgent(mock_client, llm)

        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(0), _make_facet(1)]

        results = await dispatcher.dispatch(facets, agent)
        assert len(results) == 2
        assert results[0].facet_index == 0
        assert results[1].facet_index == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/unit/agents/research/test_literature_review.py -v 2>&1 | head -10`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.agents.research.literature_review'`

- [ ] **Step 3: Write the implementation**

Create `src/agents/research/literature_review.py`:

```python
"""Literature review agent using Semantic Scholar.

Searches academic papers, deduplicates, extracts claims via LLM.
Satisfies the AgentFunction signature as a callable class.
Mirrors the WebSearchAgent pattern from RESEARCH-002.
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
from src.services.semantic_scholar import (
    ScholarPaper,
    SemanticScholarClient,
    SemanticScholarError,
)

logger = structlog.get_logger()

_CLAIMS_SYSTEM = (
    "You are an academic research analyst. Extract key factual claims "
    "and a summary from paper abstracts. Focus on methodology, "
    "findings, and statistical results. Respond with JSON only."
)

_CLAIMS_TEMPLATE = (
    "Paper abstracts about '{title}':\n\n{abstracts}\n\n"
    "Extract 3-5 key factual claims (cite as Author et al. (year)) "
    "and a 2-3 sentence summary of research contributions.\n"
    'Return JSON: {{"claims": ["..."], "summary": "..."}}'
)

_MAX_SNIPPET_CHARS = 500
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitize(text: str) -> str:
    """Strip control characters (RISK-005 mitigation)."""
    return _CONTROL_CHAR_RE.sub("", text)[:_MAX_SNIPPET_CHARS]


class LiteratureReviewAgent:
    """Callable research agent that searches Semantic Scholar."""

    def __init__(
        self,
        client: SemanticScholarClient,
        llm: BaseChatModel,
        max_results_per_query: int = 5,
    ) -> None:
        self._client = client
        self._llm = llm
        self._max_results = max_results_per_query

    async def __call__(self, facet: ResearchFacet) -> FacetFindings:
        """Search papers, dedup, extract claims, return findings."""
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

    async def _execute_queries(self, queries: list[str]) -> list[ScholarPaper]:
        """Run all queries in parallel, collect results."""
        tasks = [self._safe_search(q) for q in queries]
        nested = await asyncio.gather(*tasks)
        return [p for batch in nested for p in batch]

    async def _safe_search(self, query: str) -> list[ScholarPaper]:
        """Search with error handling — returns empty on failure."""
        try:
            return await self._client.search(query, max_results=self._max_results)
        except SemanticScholarError as exc:
            logger.warning("scholar_query_failed", query=query, error=str(exc))
            return []

    def _deduplicate(self, papers: list[ScholarPaper]) -> list[ScholarPaper]:
        """Deduplicate by paper_id, keep first occurrence."""
        seen: set[str] = set()
        unique: list[ScholarPaper] = []
        for p in papers:
            if p.paper_id not in seen:
                seen.add(p.paper_id)
                unique.append(p)
        return unique

    def _to_source_documents(
        self, papers: list[ScholarPaper]
    ) -> list[SourceDocument]:
        """Convert ScholarPaper to SourceDocument models."""
        now = datetime.now(UTC)
        return [
            SourceDocument(
                url=self._paper_url(p),
                title=_sanitize(p.title),
                snippet=_sanitize(p.abstract),
                retrieved_at=now,
                published_at=datetime(p.year, 1, 1, tzinfo=UTC) if p.year else None,
                author=p.authors[0] if p.authors else None,
            )
            for p in papers
        ]

    def _paper_url(self, paper: ScholarPaper) -> str:
        """Get best URL: paper URL or DOI fallback."""
        if paper.url:
            return paper.url
        if paper.doi:
            return f"https://doi.org/{paper.doi}"
        return f"https://semanticscholar.org/paper/{paper.paper_id}"

    async def _extract_claims(
        self, title: str, sources: list[SourceDocument]
    ) -> tuple[list[str], str]:
        """Extract claims + summary via LLM, with fallback."""
        abstracts = "\n".join(
            f"- [{s.title}] ({s.author or 'Unknown'}): {s.snippet}"
            for s in sources
        )
        msg = _CLAIMS_TEMPLATE.format(title=_sanitize(title), abstracts=abstracts)
        messages = [
            SystemMessage(content=_CLAIMS_SYSTEM),
            HumanMessage(content=msg),
        ]
        try:
            resp = await self._llm.ainvoke(messages)
            data = json.loads(str(resp.content))
            return data["claims"], data["summary"]
        except (json.JSONDecodeError, KeyError, ValidationError) as exc:
            logger.warning("academic_claims_extraction_failed", error=str(exc))
            return self._fallback_claims(title, sources)

    def _fallback_claims(
        self, title: str, sources: list[SourceDocument]
    ) -> tuple[list[str], str]:
        """Fallback: use first sentences of abstracts as claims."""
        claims = [s.snippet[:200] for s in sources[:3]]
        summary = f"Academic literature on: {title}"
        return claims, summary

    def _empty_findings(self, facet_index: int) -> FacetFindings:
        """Return empty findings when all queries fail."""
        return FacetFindings(
            facet_index=facet_index, sources=[], claims=[], summary=""
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/unit/agents/research/test_literature_review.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-research-004 && git add src/agents/research/literature_review.py tests/unit/agents/research/test_literature_review.py && git commit -m "feat(research-004): add LiteratureReviewAgent with Semantic Scholar"
```

---

## Task 5: Update Research Planner for `source_type`

**Files:**
- Modify: `src/agents/research/planner.py:18-32`
- Modify: `tests/unit/agents/research/test_planner.py`

- [ ] **Step 1: Write new tests for `source_type` in planner output**

Add to `tests/unit/agents/research/test_planner.py`:

```python
# Add this helper function after existing helpers:
def _plan_json_with_source_types() -> str:
    return json.dumps(
        {
            "facets": [
                {
                    "index": 0,
                    "title": "Recent incidents",
                    "description": "Current events",
                    "search_queries": ["recent incidents 2026"],
                    "source_type": "web",
                },
                {
                    "index": 1,
                    "title": "Detection methods",
                    "description": "ML approaches",
                    "search_queries": ["detection ML"],
                    "source_type": "academic",
                },
                {
                    "index": 2,
                    "title": "Mitigation strategies",
                    "description": "Both practical and research",
                    "search_queries": ["mitigation strategies"],
                    "source_type": "both",
                },
            ],
            "reasoning": "Mixed plan",
        }
    )


# Add this test class:
class TestPlannerSourceType:
    async def test_plan_includes_source_type(self) -> None:
        llm = FakeListChatModel(responses=[_plan_json_with_source_types()])
        plan = await generate_research_plan(_make_topic(), llm)
        assert plan.facets[0].source_type == "web"
        assert plan.facets[1].source_type == "academic"
        assert plan.facets[2].source_type == "both"

    async def test_default_source_type_is_web(self) -> None:
        """Facets without source_type default to 'web'."""
        llm = FakeListChatModel(responses=[_plan_json(3)])
        plan = await generate_research_plan(_make_topic(), llm)
        for facet in plan.facets:
            assert facet.source_type == "web"
```

- [ ] **Step 2: Run tests to verify the new ones pass**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/unit/agents/research/test_planner.py -v`
Expected: New tests should PASS (model default handles missing field; source_type test uses explicit JSON)

- [ ] **Step 3: Update planner prompts**

In `src/agents/research/planner.py`, update the prompts:

Replace `_SYSTEM_PROMPT` (lines 18-22) with:

```python
_SYSTEM_PROMPT = (
    "You are a research planning assistant. Given a topic, generate a "
    "research plan with 3-5 facets. Each facet should cover a distinct "
    "angle of the topic.\n\n"
    "For each facet, set source_type to one of:\n"
    '- "web": current events, industry news, practical guides\n'
    '- "academic": research papers, methodologies, empirical studies\n'
    '- "both": topics needing both web and scholarly sources\n\n'
    "Respond with valid JSON only."
)
```

Replace `_USER_TEMPLATE` (lines 24-32) with:

```python
_USER_TEMPLATE = (
    "Plan research for this topic:\n"
    "Title: {title}\n"
    "Description: {description}\n"
    "Domain: {domain}\n\n"
    'Return JSON: {{"facets": [{{"index": 0, "title": "...", '
    '"description": "...", "search_queries": ["..."], '
    '"source_type": "web|academic|both"}}], '
    '"reasoning": "..."}}'
)
```

- [ ] **Step 4: Run all planner tests**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/unit/agents/research/test_planner.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-research-004 && git add src/agents/research/planner.py tests/unit/agents/research/test_planner.py && git commit -m "feat(research-004): update planner to emit source_type per facet"
```

---

## Task 6: Update Orchestrator for Dual-Agent Routing

**Note:** `orchestrator.py` is already 224 lines (pre-existing violation of the 200-line standard). This task adds ~12 lines for `_route_and_dispatch`. Extracting to a separate file is deferred — the function is tightly coupled to the graph builder's closure scope.

**Files:**
- Modify: `src/agents/research/orchestrator.py:90-130`
- Modify: `tests/unit/agents/research/test_orchestrator.py`

- [ ] **Step 1: Write new tests for dual-agent routing**

Add to `tests/unit/agents/research/test_orchestrator.py`:

```python
# Add to imports:
from src.models.research import ResearchFacet

# Add this helper:
def _plan_json_with_source_types() -> str:
    return json.dumps(
        {
            "facets": [
                {
                    "index": 0,
                    "title": "Web Facet",
                    "description": "Web only",
                    "search_queries": ["q0"],
                    "source_type": "web",
                },
                {
                    "index": 1,
                    "title": "Academic Facet",
                    "description": "Academic only",
                    "search_queries": ["q1"],
                    "source_type": "academic",
                },
                {
                    "index": 2,
                    "title": "Both Facet",
                    "description": "Both sources",
                    "search_queries": ["q2"],
                    "source_type": "both",
                },
            ],
            "reasoning": "Mixed plan",
        }
    )


# Add a tracking stub agent:
async def _tracking_agent(facet: ResearchFacet) -> FacetFindings:
    """Stub that returns findings with facet_index for tracking."""
    return FacetFindings(
        facet_index=facet.index,
        sources=[],
        claims=[f"from-tracking-{facet.index}"],
        summary=f"tracking-{facet.index}",
    )


# Add test class:
class TestDualAgentRouting:
    async def test_literature_agent_receives_academic_facets(self) -> None:
        """Academic facets go to literature agent, not web agent."""
        web_calls: list[int] = []
        lit_calls: list[int] = []

        async def web_agent(facet: ResearchFacet) -> FacetFindings:
            web_calls.append(facet.index)
            return await stub_research_agent(facet)

        async def lit_agent(facet: ResearchFacet) -> FacetFindings:
            lit_calls.append(facet.index)
            return await stub_research_agent(facet)

        llm = FakeListChatModel(
            responses=[_plan_json_with_source_types(), _eval_json(True)]
        )
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(
            llm, dispatcher, web_agent, literature_agent_fn=lit_agent
        )
        result = await graph.ainvoke(_initial_state())
        assert result["status"] == "complete"
        # web facet (0) + both facet (2) -> web agent
        assert 0 in web_calls
        assert 2 in web_calls
        # academic facet (1) + both facet (2) -> lit agent
        assert 1 in lit_calls
        assert 2 in lit_calls
        # facet 0 should NOT go to lit agent
        assert 0 not in lit_calls

    async def test_backward_compat_without_literature_agent(self) -> None:
        """Without literature_agent_fn, all facets go to web agent."""
        llm = FakeListChatModel(
            responses=[_plan_json_with_source_types(), _eval_json(True)]
        )
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent)
        result = await graph.ainvoke(_initial_state())
        assert result["status"] == "complete"
        # All 3 facets + both facet doubled = at least 3 findings
        assert len(result["findings"]) >= 3

    async def test_both_facet_produces_two_findings(self) -> None:
        """source_type='both' dispatches to both agents."""
        llm = FakeListChatModel(
            responses=[_plan_json_with_source_types(), _eval_json(True)]
        )
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(
            llm, dispatcher, stub_research_agent,
            literature_agent_fn=stub_research_agent,
        )
        result = await graph.ainvoke(_initial_state())
        assert result["status"] == "complete"
        # web(0) + academic(1) + both(2)*2 = 4 findings
        assert len(result["findings"]) == 4
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/unit/agents/research/test_orchestrator.py::TestDualAgentRouting -v 2>&1 | head -20`
Expected: FAIL — `build_graph() got an unexpected keyword argument 'literature_agent_fn'`

- [ ] **Step 3: Update `build_graph` and `dispatch_agents`**

In `src/agents/research/orchestrator.py`, update `build_graph` (lines 90-95) to:

```python
def build_graph(
    llm: BaseChatModel,
    dispatcher: TaskDispatcher,
    agent_fn: AgentFunction,
    literature_agent_fn: AgentFunction | None = None,
    indexing_deps: IndexingDeps | None = None,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    """Build and compile the research orchestrator graph."""
    graph = StateGraph(ResearchState)
```

Update `dispatch_agents` (lines 104-130) to route by `source_type`:

```python
    async def dispatch_agents(state: ResearchState) -> dict:  # type: ignore[type-arg]
        plan = _validate_plan(state)
        evaluation = _validate_evaluation(state)
        if evaluation and evaluation.weak_facets:
            weak = set(evaluation.weak_facets)
            facets = [f for f in plan.facets if f.index in weak]
        else:
            facets = list(plan.facets)

        results = await _route_and_dispatch(
            facets, dispatcher, agent_fn, literature_agent_fn
        )

        now = datetime.now(UTC)
        tasks = [
            FacetTask(
                facet_index=f.index,
                status="completed",
                started_at=now,
                completed_at=now,
            )
            for f in facets
        ]
        return {
            "findings": results,
            "dispatched_tasks": tasks,
            "round_number": state["round_number"] + 1,
            "status": "researching",
        }
```

Add the `_route_and_dispatch` helper function (before `build_graph`):

```python
async def _route_and_dispatch(
    facets: list[ResearchFacet],
    dispatcher: TaskDispatcher,
    agent_fn: AgentFunction,
    literature_agent_fn: AgentFunction | None,
) -> list[FacetFindings]:
    """Split facets by source_type, dispatch to correct agents."""
    web_facets = [f for f in facets if f.source_type in ("web", "both")]
    academic_facets = [f for f in facets if f.source_type in ("academic", "both")]

    results: list[FacetFindings] = []
    if web_facets:
        results.extend(await dispatcher.dispatch(web_facets, agent_fn))
    if academic_facets and literature_agent_fn is not None:
        results.extend(await dispatcher.dispatch(academic_facets, literature_agent_fn))
    elif academic_facets:
        results.extend(await dispatcher.dispatch(academic_facets, agent_fn))
    return results
```

Also add the import for `ResearchFacet` at line 19:

```python
from src.models.research import (
    ChunkMetadata,
    DocumentChunk,
    EvaluationResult,
    FacetFindings,
    FacetTask,
    ResearchFacet,
    ResearchPlan,
    TopicInput,
)
```

- [ ] **Step 4: Run all orchestrator tests**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/unit/agents/research/test_orchestrator.py -v`
Expected: All tests PASS (old and new)

- [ ] **Step 5: Run full test suite**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/ -q --tb=short 2>&1 | tail -5`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
cd D:/Workbench/github/cognify-research-004 && git add src/agents/research/orchestrator.py tests/unit/agents/research/test_orchestrator.py && git commit -m "feat(research-004): add dual-agent routing to orchestrator dispatch"
```

---

## Task 7: Final Integration Verification

**Files:** No new files — verification only

- [ ] **Step 1: Run full test suite**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: All tests pass (697 original + ~35 new = ~732 tests)

- [ ] **Step 2: Run linting**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run ruff check src/services/semantic_scholar.py src/agents/research/literature_review.py src/models/research.py src/agents/research/orchestrator.py src/agents/research/planner.py`
Expected: No lint errors

- [ ] **Step 3: Run type checking on new files**

Run: `cd D:/Workbench/github/cognify-research-004 && uv run mypy src/services/semantic_scholar.py src/agents/research/literature_review.py --strict`
Expected: No type errors

- [ ] **Step 4: Verify file sizes within coding standards**

All new files should be < 200 lines:
- `src/services/semantic_scholar.py` — ~95 lines
- `src/agents/research/literature_review.py` — ~130 lines

Run: `wc -l D:/Workbench/github/cognify-research-004/src/services/semantic_scholar.py D:/Workbench/github/cognify-research-004/src/agents/research/literature_review.py`
Expected: Both under 200 lines
