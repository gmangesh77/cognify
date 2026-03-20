from typing import TypedDict

import httpx

from src.services.trends.protocol import TrendSourceError


class HNStoryResponse(TypedDict):
    objectID: str
    title: str
    url: str | None
    points: int | None
    num_comments: int | None
    story_text: str | None
    created_at_i: int


class HackerNewsAPIError(TrendSourceError):
    """Raised when the Algolia HN API is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__("hackernews", message)


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
        params: dict[str, str | int] = {
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
