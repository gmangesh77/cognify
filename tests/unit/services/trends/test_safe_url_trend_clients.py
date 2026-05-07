"""INFRA-006 acceptance tests: trend clients reject unsafe base URLs.

Each trend client validates its configured base URL at construction
time so a misconfigured `COGNIFY_*_BASE_URL` (ftp://, embedded
credentials) fails fast instead of silently dialing the wrong place.
"""

from __future__ import annotations

import pytest

from src.services.trends.arxiv_client import ArxivAPIError, ArxivClient
from src.services.trends.hackernews_client import (
    HackerNewsAPIError,
    HackerNewsClient,
)
from src.services.trends.newsapi_client import NewsAPIClient
from src.services.trends.protocol import TrendSourceError


class TestNewsAPIClientBaseUrlValidation:
    def test_accepts_https_url(self) -> None:
        client = NewsAPIClient(
            api_key="k", base_url="https://newsapi.org/v2", timeout=10.0
        )
        assert client._base_url == "https://newsapi.org/v2"

    def test_rejects_ftp_scheme(self) -> None:
        with pytest.raises(TrendSourceError):
            NewsAPIClient(api_key="k", base_url="ftp://newsapi.org/v2", timeout=10.0)

    def test_rejects_userinfo(self) -> None:
        with pytest.raises(TrendSourceError):
            NewsAPIClient(
                api_key="k",
                base_url="https://user:pass@newsapi.org/v2",
                timeout=10.0,
            )


class TestHackerNewsClientBaseUrlValidation:
    def test_accepts_https_url(self) -> None:
        client = HackerNewsClient(
            base_url="https://hn.algolia.com/api/v1/search", timeout=10.0
        )
        assert "hn.algolia.com" in client._base_url

    def test_rejects_unsafe_scheme(self) -> None:
        with pytest.raises(HackerNewsAPIError):
            HackerNewsClient(base_url="file:///etc/passwd", timeout=10.0)


class TestArxivClientBaseUrlValidation:
    def test_accepts_https_url(self) -> None:
        client = ArxivClient(
            base_url="https://export.arxiv.org/api/query", timeout=10.0
        )
        assert "arxiv.org" in client._base_url

    def test_rejects_unsafe_scheme(self) -> None:
        with pytest.raises(ArxivAPIError):
            ArxivClient(base_url="ftp://export.arxiv.org/api/query", timeout=10.0)
