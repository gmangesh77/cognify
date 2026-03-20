from typing import TypedDict

import httpx

from src.services.trends.protocol import TrendSourceError


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


class NewsAPIError(TrendSourceError):
    """Raised when the NewsAPI is unreachable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__("newsapi", message)


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
        return [a for a in articles if a.get("title") != "[Removed]"]
