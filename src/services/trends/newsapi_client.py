from typing import TypedDict

import httpx
import structlog

from src.services.trends.protocol import TrendSourceError
from src.utils.safe_url import OutboundUrlError, assert_url_scheme_safe

logger = structlog.get_logger()


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
        self._base_url = _safe_base_url(base_url, "newsapi")
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


def _safe_base_url(url: str, source: str) -> str:
    """Validate `url` scheme + structure (INFRA-006 SSRF hardening).

    Configured outbound URLs go through `assert_url_scheme_safe` so a
    misconfigured `COGNIFY_*_BASE_URL` (e.g. an `ftp://` or a URL with
    embedded credentials) fails loudly at construction time rather
    than silently dialing the wrong place. DNS resolution is left to
    request time so the constructor stays offline-friendly.
    """
    try:
        return assert_url_scheme_safe(url)
    except OutboundUrlError as exc:
        logger.warning("trend_source_base_url_unsafe", source=source, error=str(exc))
        raise TrendSourceError(source, f"unsafe base_url for {source}: {exc}") from exc
