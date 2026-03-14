from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.services.google_trends_client import (
    GoogleTrendsAPIError,
    GoogleTrendsClient,
)


class TestFetchTrendingSearches:
    async def test_successful_fetch(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.return_value = pd.DataFrame(
            {0: ["AI security", "quantum computing"]},
        )

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            results = await client.fetch_trending_searches("united_states")

        assert len(results) == 2
        assert results[0]["title"] == "AI security"
        assert results[1]["title"] == "quantum computing"

    async def test_empty_results(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.return_value = pd.DataFrame(
            {0: []},
        )

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            results = await client.fetch_trending_searches("united_states")

        assert results == []

    async def test_pytrends_error_raises(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.side_effect = Exception(
            "API error",
        )

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            with pytest.raises(GoogleTrendsAPIError, match="API error"):
                await client.fetch_trending_searches("united_states")

    async def test_timeout_raises(self) -> None:
        from requests.exceptions import Timeout

        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.side_effect = Timeout(
            "Connection timed out",
        )

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            with pytest.raises(
                GoogleTrendsAPIError,
                match="timed out",
            ):
                await client.fetch_trending_searches("united_states")


class TestFetchRelatedQueries:
    async def test_successful_fetch(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.related_queries.return_value = {
            "cybersecurity": {
                "rising": pd.DataFrame(
                    {"query": ["cyber attack 2026"], "value": [500]},
                ),
                "top": pd.DataFrame(
                    {"query": ["network security"], "value": [80]},
                ),
            },
        }

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            results = await client.fetch_related_queries(
                ["cybersecurity"],
            )

        assert len(results) == 2
        rising = [r for r in results if r["query_type"] == "rising"]
        top = [r for r in results if r["query_type"] == "top"]
        assert len(rising) == 1
        assert rising[0]["title"] == "cyber attack 2026"
        assert rising[0]["value"] == 500
        assert len(top) == 1
        assert top[0]["title"] == "network security"

    async def test_breakout_value_converted(self) -> None:
        mock_pytrends = MagicMock()
        mock_pytrends.related_queries.return_value = {
            "ai": {
                "rising": pd.DataFrame(
                    {"query": ["ai breakout"], "value": ["Breakout"]},
                ),
                "top": None,
            },
        }

        with patch(
            "src.services.google_trends_client.TrendReq",
            return_value=mock_pytrends,
        ):
            client = GoogleTrendsClient(
                language="en-US",
                timezone_offset=360,
                timeout=15.0,
            )
            results = await client.fetch_related_queries(["ai"])

        assert len(results) == 1
        assert results[0]["value"] == 5000
        assert isinstance(results[0]["value"], int)
