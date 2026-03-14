import pytest
from pydantic import ValidationError

from src.api.schemas.trends import GTFetchRequest, GTFetchResponse


class TestGTFetchRequest:
    def test_valid_request(self) -> None:
        req = GTFetchRequest(domain_keywords=["cyber"])
        assert req.domain_keywords == ["cyber"]
        assert req.country == "united_states"
        assert req.max_results == 30

    def test_custom_values(self) -> None:
        req = GTFetchRequest(
            domain_keywords=["ai", "ml"],
            country="united_kingdom",
            max_results=50,
        )
        assert req.country == "united_kingdom"
        assert req.max_results == 50

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GTFetchRequest(domain_keywords=[])

    def test_max_results_too_high(self) -> None:
        with pytest.raises(ValidationError):
            GTFetchRequest(domain_keywords=["x"], max_results=101)

    def test_max_results_too_low(self) -> None:
        with pytest.raises(ValidationError):
            GTFetchRequest(domain_keywords=["x"], max_results=0)


class TestGTFetchResponse:
    def test_response_shape(self) -> None:
        resp = GTFetchResponse(
            topics=[],
            total_trending=10,
            total_related=20,
            total_after_filter=5,
        )
        assert resp.total_trending == 10
        assert resp.total_related == 20
        assert resp.total_after_filter == 5
        assert resp.topics == []
