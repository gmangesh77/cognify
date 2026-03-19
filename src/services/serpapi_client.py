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
    date: str | None = None
    author: str | None = None


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
        params: dict[str, str | int] = {
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
            raise SerpAPIError(f"SerpAPI connection failed: {exc}") from exc

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

    def _parse_results(self, data: dict[str, object]) -> list[SerpAPIResult]:
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
                    position=int(str(item.get("position", 0))),
                    date=str(item["date"]) if item.get("date") else None,
                    author=str(item["author"]) if item.get("author") else None,
                )
            )
        return results
