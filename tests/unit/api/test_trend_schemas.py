import pytest
from pydantic import ValidationError

from src.api.schemas.trends import (
    SourceResult,
    TrendFetchRequest,
    TrendFetchResponse,
)


class TestTrendFetchRequest:
    def test_defaults(self) -> None:
        req = TrendFetchRequest(domain_keywords=["ai"])
        assert req.max_results == 30
        assert req.sources is None

    def test_with_sources(self) -> None:
        req = TrendFetchRequest(
            domain_keywords=["ai"],
            sources=["hackernews", "reddit"],
        )
        assert req.sources == ["hackernews", "reddit"]

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrendFetchRequest(domain_keywords=[])


class TestSourceResult:
    def test_success_result(self) -> None:
        result = SourceResult(
            source_name="hackernews",
            topics=[],
            topic_count=0,
            duration_ms=42,
        )
        assert result.error is None

    def test_error_result(self) -> None:
        result = SourceResult(
            source_name="reddit",
            topics=[],
            topic_count=0,
            duration_ms=100,
            error="API timeout",
        )
        assert result.error == "API timeout"


class TestTrendFetchResponse:
    def test_combined_response(self) -> None:
        resp = TrendFetchResponse(
            topics=[],
            sources_queried=["hackernews"],
            source_results={},
        )
        assert resp.sources_queried == ["hackernews"]
