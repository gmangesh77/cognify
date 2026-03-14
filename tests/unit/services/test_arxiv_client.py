from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.arxiv_client import (
    ArxivAPIError,
    ArxivClient,
)

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2603.12345v1</id>
    <title>Adversarial Attacks on
    Neural Networks</title>
    <summary>We study adversarial attacks on deep neural networks.</summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <published>2026-03-15T12:00:00Z</published>
    <updated>2026-03-15T12:00:00Z</updated>
    <link href="http://arxiv.org/abs/2603.12345v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2603.12345v1" rel="related"
          type="application/pdf" title="pdf"/>
    <arxiv:primary_category term="cs.CR"/>
    <category term="cs.CR"/>
    <category term="cs.AI"/>
  </entry>
</feed>"""

EMPTY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""


class TestFetchPapers:
    async def test_successful_fetch(self) -> None:
        mock_response = httpx.Response(
            200,
            text=SAMPLE_XML,
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            papers = await client.fetch_papers(
                categories=["cs.CR"],
                max_results=10,
                sort_by="submittedDate",
            )
        assert len(papers) == 1
        paper = papers[0]
        assert paper["arxiv_id"] == "2603.12345v1"
        assert paper["title"] == "Adversarial Attacks on Neural Networks"
        assert paper["authors"] == ["Alice Smith", "Bob Jones"]
        assert paper["primary_category"] == "cs.CR"
        assert paper["categories"] == ["cs.CR", "cs.AI"]
        assert "pdf" in paper["pdf_url"]
        assert paper["abs_url"] == "http://arxiv.org/abs/2603.12345v1"

    async def test_empty_results(self) -> None:
        mock_response = httpx.Response(
            200,
            text=EMPTY_XML,
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            papers = await client.fetch_papers(
                categories=["cs.CR"],
                max_results=10,
                sort_by="submittedDate",
            )
        assert papers == []

    async def test_http_error_raises(self) -> None:
        mock_response = httpx.Response(
            500,
            text="Internal Server Error",
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(ArxivAPIError, match="500"):
                await client.fetch_papers(
                    categories=["cs.CR"],
                    max_results=10,
                    sort_by="submittedDate",
                )

    async def test_timeout_raises(self) -> None:
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException(
                "timed out",
            )
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(ArxivAPIError, match="timed out"):
                await client.fetch_papers(
                    categories=["cs.CR"],
                    max_results=10,
                    sort_by="submittedDate",
                )

    async def test_connection_error_raises(self) -> None:
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError(
                "refused",
            )
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(ArxivAPIError, match="refused"):
                await client.fetch_papers(
                    categories=["cs.CR"],
                    max_results=10,
                    sort_by="submittedDate",
                )

    async def test_invalid_xml_raises(self) -> None:
        mock_response = httpx.Response(
            200,
            text="not xml at all",
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            with pytest.raises(ArxivAPIError, match="parse"):
                await client.fetch_papers(
                    categories=["cs.CR"],
                    max_results=10,
                    sort_by="submittedDate",
                )

    async def test_title_whitespace_normalized(self) -> None:
        mock_response = httpx.Response(
            200,
            text=SAMPLE_XML,
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            papers = await client.fetch_papers(
                categories=["cs.CR"],
                max_results=10,
                sort_by="submittedDate",
            )
        assert "\n" not in papers[0]["title"]

    async def test_query_builds_correctly(self) -> None:
        mock_response = httpx.Response(
            200,
            text=EMPTY_XML,
            request=httpx.Request("GET", "http://test"),
        )
        with patch(
            "src.services.arxiv_client.httpx.AsyncClient",
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client,
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = ArxivClient(
                base_url="http://test",
                timeout=5.0,
            )
            await client.fetch_papers(
                categories=["cs.CR", "cs.AI"],
                max_results=20,
                sort_by="submittedDate",
            )
            call_kwargs = mock_client.get.call_args
            params = call_kwargs.kwargs.get(
                "params",
                call_kwargs.args[1] if len(call_kwargs.args) > 1 else {},
            )
            assert "cat:cs.CR" in params["search_query"]
            assert "cat:cs.AI" in params["search_query"]
            assert params["max_results"] == 20
            assert params["sortBy"] == "submittedDate"
