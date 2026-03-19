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
from dateutil.parser import parse as parse_date
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


def _parse_serpapi_date(date_str: str | None) -> datetime | None:
    """Parse a date string from SerpAPI into a datetime, or None."""
    if not date_str:
        return None
    try:
        parsed: datetime = parse_date(date_str)
        return parsed
    except (ValueError, OverflowError):
        logger.warning("serpapi_date_parse_failed", date_string=date_str)
        return None


class WebSearchAgent:
    """Callable research agent that searches the web via SerpAPI."""

    def __init__(self, serpapi_client: SerpAPIClient, llm: BaseChatModel) -> None:
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

    async def _execute_queries(self, queries: list[str]) -> list[SerpAPIResult]:
        """Run all queries in parallel, collect results."""
        tasks = [self._safe_search(q) for q in queries]
        nested = await asyncio.gather(*tasks)
        return [r for batch in nested for r in batch]

    async def _safe_search(self, query: str) -> list[SerpAPIResult]:
        """Search with error handling — returns empty on failure."""
        try:
            return await self._client.search(query)
        except SerpAPIError as exc:
            logger.warning("serpapi_query_failed", query=query, error=str(exc))
            return []

    def _deduplicate(self, results: list[SerpAPIResult]) -> list[SerpAPIResult]:
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
                published_at=_parse_serpapi_date(r.date),
                author=r.author,
            )
            for r in results
        ]

    async def _extract_claims(
        self, title: str, sources: list[SourceDocument]
    ) -> tuple[list[str], str]:
        """Extract claims + summary via LLM, with fallback."""
        snippets = "\n".join(f"- [{s.title}]: {s.snippet}" for s in sources)
        msg = _CLAIMS_TEMPLATE.format(title=_sanitize(title), snippets=snippets)
        messages = [
            SystemMessage(content=_CLAIMS_SYSTEM),
            HumanMessage(content=msg),
        ]
        try:
            resp = await self._llm.ainvoke(messages)
            data = json.loads(str(resp.content))
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
        return FacetFindings(facet_index=facet_index, sources=[], claims=[], summary="")
