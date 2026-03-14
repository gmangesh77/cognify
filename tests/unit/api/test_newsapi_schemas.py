import pytest
from pydantic import ValidationError

from src.api.schemas.trends import (
    NewsAPIFetchRequest,
    NewsAPIFetchResponse,
)


class TestNewsAPIFetchRequest:
    def test_valid_request_defaults(self) -> None:
        req = NewsAPIFetchRequest(domain_keywords=["cyber"])
        assert req.domain_keywords == ["cyber"]
        assert req.max_results == 30
        assert req.category == "technology"
        assert req.country == "us"

    def test_custom_values(self) -> None:
        req = NewsAPIFetchRequest(
            domain_keywords=["ai", "ml"],
            max_results=50,
            category="science",
            country="gb",
        )
        assert req.max_results == 50
        assert req.category == "science"
        assert req.country == "gb"

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NewsAPIFetchRequest(domain_keywords=[])

    def test_max_results_too_high(self) -> None:
        with pytest.raises(ValidationError):
            NewsAPIFetchRequest(
                domain_keywords=["x"],
                max_results=101,
            )

    def test_max_results_too_low(self) -> None:
        with pytest.raises(ValidationError):
            NewsAPIFetchRequest(
                domain_keywords=["x"],
                max_results=0,
            )


class TestNewsAPIFetchResponse:
    def test_response_shape(self) -> None:
        resp = NewsAPIFetchResponse(
            topics=[],
            total_fetched=20,
            total_after_filter=5,
        )
        assert resp.total_fetched == 20
        assert resp.total_after_filter == 5
        assert resp.topics == []
