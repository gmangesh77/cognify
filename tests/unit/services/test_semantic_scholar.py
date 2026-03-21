"""Tests for the Semantic Scholar HTTP client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.semantic_scholar import (
    ScholarPaper,
    SemanticScholarClient,
    SemanticScholarError,
)


def _scholar_response(num_results: int = 3) -> dict:
    """Build a fake Semantic Scholar search response."""
    return {
        "total": num_results,
        "data": [
            {
                "paperId": f"paper-{i}",
                "title": f"Paper Title {i}",
                "abstract": f"This is the abstract for paper {i}.",
                "authors": [{"name": f"Author {i}"}],
                "year": 2025,
                "citationCount": 10 * (i + 1),
                "venue": "NeurIPS",
                "url": f"https://semanticscholar.org/paper/{i}",
                "externalIds": {"DOI": f"10.1234/paper.{i}"},
            }
            for i in range(num_results)
        ],
    }


def _make_client() -> SemanticScholarClient:
    return SemanticScholarClient(
        base_url="https://api.semanticscholar.org",
        timeout=5.0,
    )


class TestSemanticScholarClientSearch:
    async def test_returns_parsed_papers(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(3))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("machine learning security")

        assert len(results) == 3
        assert all(isinstance(r, ScholarPaper) for r in results)
        assert results[0].paper_id == "paper-0"
        assert results[0].title == "Paper Title 0"
        assert results[0].authors == ["Author 0"]
        assert results[0].citation_count == 10

    async def test_empty_results(self) -> None:
        mock_resp = httpx.Response(200, json={"total": 0, "data": []})
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("obscure query xyz")

        assert results == []

    async def test_skips_papers_without_abstract(self) -> None:
        resp_data = {
            "total": 2,
            "data": [
                {
                    "paperId": "p1",
                    "title": "Has Abstract",
                    "abstract": "Real abstract",
                    "authors": [{"name": "A"}],
                    "year": 2025,
                    "citationCount": 5,
                    "venue": "ICML",
                    "url": "https://s2.org/p1",
                    "externalIds": {},
                },
                {
                    "paperId": "p2",
                    "title": "No Abstract",
                    "abstract": None,
                    "authors": [{"name": "B"}],
                    "year": 2024,
                    "citationCount": 2,
                    "venue": "",
                    "url": "https://s2.org/p2",
                    "externalIds": {},
                },
            ],
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("test")

        assert len(results) == 1
        assert results[0].title == "Has Abstract"

    async def test_raises_on_api_error(self) -> None:
        mock_resp = httpx.Response(429, json={"error": "Rate limited"})
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SemanticScholarError, match="429"):
                await client.search("test")

    async def test_raises_on_timeout(self) -> None:
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SemanticScholarError, match="timed out"):
                await client.search("test")

    async def test_raises_on_connection_error(self) -> None:
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            with pytest.raises(SemanticScholarError, match="refused"):
                await client.search("test")

    async def test_passes_correct_params(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(1))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            await client.search("AI security", max_results=5)

            call_kwargs = mock_client.get.call_args
            assert "paper/search" in str(call_kwargs)
            params = call_kwargs.kwargs["params"]
            assert params["query"] == "AI security"
            assert params["limit"] == 5

    async def test_configurable_base_url(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(1))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = SemanticScholarClient(
                base_url="https://test.local",
                timeout=5.0,
            )
            await client.search("test")

            url_arg = mock_client.get.call_args.args[0]
            assert url_arg.startswith("https://test.local")

    async def test_extracts_doi(self) -> None:
        resp_data = {
            "total": 1,
            "data": [
                {
                    "paperId": "p1",
                    "title": "DOI Paper",
                    "abstract": "Has DOI",
                    "authors": [],
                    "year": 2025,
                    "citationCount": 3,
                    "venue": "arXiv",
                    "url": "https://s2.org/p1",
                    "externalIds": {"DOI": "10.1234/test"},
                },
            ],
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("DOI test")

        assert results[0].doi == "10.1234/test"

    async def test_handles_missing_doi(self) -> None:
        resp_data = {
            "total": 1,
            "data": [
                {
                    "paperId": "p1",
                    "title": "No DOI",
                    "abstract": "No DOI",
                    "authors": [],
                    "year": 2025,
                    "citationCount": 0,
                    "venue": "",
                    "url": "https://s2.org/p1",
                    "externalIds": {},
                },
            ],
        }
        mock_resp = httpx.Response(200, json=resp_data)
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()
            results = await client.search("no doi")

        assert results[0].doi is None


class TestSemanticScholarClientApiKey:
    async def test_api_key_in_headers(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(1))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = SemanticScholarClient(
                base_url="https://api.semanticscholar.org",
                api_key="test-key-123",
                timeout=5.0,
            )
            await client.search("test")

            init_kwargs = mock_cls.call_args.kwargs
            assert init_kwargs["headers"]["x-api-key"] == "test-key-123"

    async def test_no_api_key_header_when_none(self) -> None:
        mock_resp = httpx.Response(200, json=_scholar_response(1))
        with patch("src.services.semantic_scholar.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = _make_client()  # no api_key
            await client.search("test")

            init_kwargs = mock_cls.call_args.kwargs
            headers = init_kwargs.get("headers", {})
            assert "x-api-key" not in headers
