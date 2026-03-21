"""Semantic Scholar HTTP client for academic paper search.

Transport layer only — handles HTTP calls, error wrapping, and response
parsing. Follows the same pattern as serpapi_client.py.
"""

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger()

_SEARCH_FIELDS = (
    "paperId,title,abstract,authors,year,citationCount,venue,externalIds,url"
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
    constructing this model.
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

    async def search(self, query: str, max_results: int = 5) -> list[ScholarPaper]:
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
            raise SemanticScholarError(f"Semantic Scholar timed out: {exc}") from exc
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
            raise SemanticScholarError(f"Invalid JSON response: {exc}") from exc

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
            ext_ids = item.get("externalIds", {}) or {}
            doi_val = ext_ids.get("DOI")  # type: ignore[union-attr]
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
                    doi=str(doi_val) if doi_val else None,
                )
            )
        return papers
