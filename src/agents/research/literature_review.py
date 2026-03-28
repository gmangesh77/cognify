"""Literature review agent using Semantic Scholar.

Searches academic papers via Semantic Scholar API, deduplicates by
paper ID, sanitizes text, and extracts claims via LLM. Satisfies
the AgentFunction signature as a callable class.
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
from src.utils.llm_json import parse_llm_json

logger = structlog.get_logger()

_CLAIMS_SYSTEM = (
    "You are an academic research analyst. Extract key factual claims "
    "and a summary from paper abstracts. Focus on methodology, findings, "
    "and statistical results. Respond with JSON only."
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
    """Strip control characters from text (RISK-005 mitigation)."""
    return _CONTROL_CHAR_RE.sub("", text)[:_MAX_SNIPPET_CHARS]


def _paper_url(paper: ScholarPaper) -> str:
    """Resolve paper URL with DOI and Semantic Scholar fallbacks."""
    if paper.url:
        return paper.url
    if paper.doi:
        return f"https://doi.org/{paper.doi}"
    return f"https://semanticscholar.org/paper/{paper.paper_id}"


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

    def _to_source_documents(self, papers: list[ScholarPaper]) -> list[SourceDocument]:
        """Convert ScholarPaper results to SourceDocument models."""
        now = datetime.now(UTC)
        return [
            SourceDocument(
                url=_paper_url(p),
                title=_sanitize(p.title),
                snippet=_sanitize(p.abstract),
                retrieved_at=now,
                published_at=datetime(p.year, 1, 1, tzinfo=UTC) if p.year else None,
                author=p.authors[0] if p.authors else None,
            )
            for p in papers
        ]

    async def _extract_claims(
        self, title: str, sources: list[SourceDocument]
    ) -> tuple[list[str], str]:
        """Extract claims + summary via LLM, with fallback."""
        abstracts = "\n".join(f"- [{s.title}]: {s.snippet}" for s in sources)
        msg = _CLAIMS_TEMPLATE.format(title=_sanitize(title), abstracts=abstracts)
        messages = [
            SystemMessage(content=_CLAIMS_SYSTEM),
            HumanMessage(content=msg),
        ]
        try:
            resp = await self._llm.ainvoke(messages)
            data = parse_llm_json(str(resp.content))
            claims = data["claims"]
            summary = data["summary"]
            return claims, summary
        except (json.JSONDecodeError, KeyError, ValidationError) as exc:
            logger.warning("claims_extraction_failed", error=str(exc))
            return self._fallback_claims(title, sources)

    def _fallback_claims(
        self, title: str, sources: list[SourceDocument]
    ) -> tuple[list[str], str]:
        """Fallback: use abstracts as claims if LLM fails."""
        claims = [s.snippet[:200] for s in sources[:3]]
        summary = f"Academic papers about: {title}"
        return claims, summary

    def _empty_findings(self, facet_index: int) -> FacetFindings:
        """Return empty findings when all queries fail."""
        return FacetFindings(facet_index=facet_index, sources=[], claims=[], summary="")
