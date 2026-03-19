"""Tests for the SerpAPI HTTP client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.serpapi_client import (
    SerpAPIClient,
    SerpAPIError,
    SerpAPIResult,
)


def _serpapi_response(num_results: int = 3) -> dict:
    """Build a fake SerpAPI JSON response."""
    return {
        "organic_results": [
            {
                "position": i + 1,
                "title": f"Result {i + 1}",
                "link": f"https://example.com/article-{i + 1}",
                "snippet": f"This is the snippet for result {i + 1}.",
            }
            for i in range(num_results)
        ]
    }


def _make_client() -> SerpAPIClient:
    return SerpAPIClient(
        api_key="test-key",
        base_url="https://serpapi.com/search",
        timeout=5.0,
        results_per_query=10,
    )


class TestSerpAPIClientSearch:
    async def test_returns_parsed_results(self) -> None:
        mock_resp = httpx.Response(200, json=_serpapi_response(3))
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("AI security", num_results=3)

        assert len(results) == 3
        assert all(isinstance(r, SerpAPIResult) for r in results)
        assert results[0].title == "Result 1"
        assert results[0].link == "https://example.com/article-1"
        assert results[0].position == 1

    async def test_empty_results(self) -> None:
        mock_resp = httpx.Response(200, json={"organic_results": []})
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("obscure query")

        assert results == []

    async def test_skips_results_without_snippet(self) -> None:
        resp_data = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Good",
                    "link": "https://a.com",
                    "snippet": "Has snippet",
                },
                {"position": 2, "title": "Bad", "link": "https://b.com"},
            ]
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("test")

        assert len(results) == 1
        assert results[0].title == "Good"

    async def test_raises_on_api_error(self) -> None:
        mock_resp = httpx.Response(401, json={"error": "Invalid API key"})
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SerpAPIError, match="401"):
                await client.search("test")

    async def test_raises_on_timeout(self) -> None:
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SerpAPIError, match="timed out"):
                await client.search("test")

    async def test_raises_on_connection_error(self) -> None:
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SerpAPIError, match="connection"):
                await client.search("test")

    async def test_passes_correct_params(self) -> None:
        mock_resp = httpx.Response(200, json=_serpapi_response(1))
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            await client.search("AI security", num_results=5)

            params = mock_client.get.call_args.kwargs["params"]
            assert params["q"] == "AI security"
            assert params["num"] == 5
            assert params["api_key"] == "test-key"
            assert params["engine"] == "google"


class TestSerpAPIClientDateAuthor:
    async def test_parse_results_extracts_date_and_author(self) -> None:
        resp_data = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Security Report 2026",
                    "link": "https://example.com/report",
                    "snippet": "A comprehensive security report.",
                    "date": "Mar 10, 2026",
                    "author": "Jane Smith",
                },
            ]
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("security report")

        assert len(results) == 1
        assert results[0].date == "Mar 10, 2026"
        assert results[0].author == "Jane Smith"

    async def test_parse_results_handles_missing_date_author(self) -> None:
        resp_data = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "No Metadata Article",
                    "link": "https://example.com/plain",
                    "snippet": "An article without date or author.",
                },
            ]
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.serpapi_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("plain article")

        assert len(results) == 1
        assert results[0].date is None
        assert results[0].author is None
