from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.trends.hackernews_client import (
    HackerNewsAPIError,
    HackerNewsClient,
)

SAMPLE_HIT = {
    "objectID": "123",
    "title": "Cybersecurity Trends 2026",
    "url": "https://example.com/cyber",
    "points": 150,
    "num_comments": 42,
    "story_text": "A deep dive into security.",
    "created_at_i": 1710000000,
}


class TestFetchStories:
    async def test_successful_fetch(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"hits": [SAMPLE_HIT]},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.trends.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            stories = await client.fetch_stories("cyber", 10, 30)

        assert len(stories) == 1
        assert stories[0]["title"] == "Cybersecurity Trends 2026"
        assert stories[0]["points"] == 150

    async def test_empty_results(self) -> None:
        mock_response = httpx.Response(
            200,
            json={"hits": []},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.trends.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            stories = await client.fetch_stories("niche", 10, 30)

        assert stories == []

    async def test_http_error_raises(self) -> None:
        mock_response = httpx.Response(
            500,
            json={"message": "server error"},
            request=httpx.Request("GET", "http://test"),
        )
        with patch("src.services.trends.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(HackerNewsAPIError, match="500"):
                await client.fetch_stories("cyber", 10, 30)

    async def test_timeout_raises(self) -> None:
        with patch("src.services.trends.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(HackerNewsAPIError, match="timed out"):
                await client.fetch_stories("cyber", 10, 30)

    async def test_connection_error_raises(self) -> None:
        with patch("src.services.trends.hackernews_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = HackerNewsClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(HackerNewsAPIError, match="refused"):
                await client.fetch_stories("cyber", 10, 30)
