from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.newsapi_client import (
    NewsAPIClient,
    NewsAPIError,
)

SAMPLE_ARTICLE = {
    "title": "Cybersecurity Alert",
    "description": "A major breach was reported.",
    "url": "https://example.com/cyber",
    "urlToImage": "https://example.com/img.jpg",
    "publishedAt": "2026-03-15T10:00:00Z",
    "source": {"id": "test-source", "name": "Test Source"},
    "author": "Jane Doe",
    "content": "Full article content here...",
}


class TestFetchTopHeadlines:
    async def test_successful_fetch(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"status": "ok", "articles": [SAMPLE_ARTICLE]},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            articles = await client.fetch_top_headlines(
                "technology",
                "us",
                30,
            )
        assert len(articles) == 1
        assert articles[0]["title"] == "Cybersecurity Alert"

    async def test_empty_results(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"status": "ok", "articles": []},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            articles = await client.fetch_top_headlines(
                "technology",
                "us",
                30,
            )
        assert articles == []

    async def test_api_error_status_raises(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"status": "error", "code": "apiKeyInvalid"},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="bad-key",
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(NewsAPIError, match="apiKeyInvalid"):
                await client.fetch_top_headlines(
                    "technology",
                    "us",
                    30,
                )

    async def test_http_error_raises(self) -> None:
        mock_response = httpx.Response(
            500,
            json={"message": "server error"},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(NewsAPIError, match="500"):
                await client.fetch_top_headlines(
                    "technology",
                    "us",
                    30,
                )

    async def test_timeout_raises(self) -> None:
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(NewsAPIError, match="timed out"):
                await client.fetch_top_headlines(
                    "technology",
                    "us",
                    30,
                )

    async def test_connection_error_raises(self) -> None:
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(NewsAPIError, match="refused"):
                await client.fetch_top_headlines(
                    "technology",
                    "us",
                    30,
                )

    async def test_removed_articles_filtered(self) -> None:
        articles = [
            SAMPLE_ARTICLE,
            {**SAMPLE_ARTICLE, "title": "[Removed]"},
        ]
        mock_response = httpx.Response(
            200,
            json={"status": "ok", "articles": articles},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.newsapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = NewsAPIClient(
                api_key="test-key",
                base_url="http://test",
                timeout=5.0,
            )
            result = await client.fetch_top_headlines(
                "technology",
                "us",
                30,
            )
        assert len(result) == 1
        assert result[0]["title"] == "Cybersecurity Alert"
