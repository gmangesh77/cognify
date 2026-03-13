import pytest
from pydantic import ValidationError

from src.api.schemas.trends import HNFetchRequest, HNFetchResponse


class TestHNFetchRequest:
    def test_valid_request(self) -> None:
        req = HNFetchRequest(domain_keywords=["cyber"])
        assert req.domain_keywords == ["cyber"]
        assert req.max_results == 30
        assert req.min_points == 10

    def test_custom_values(self) -> None:
        req = HNFetchRequest(
            domain_keywords=["ai", "ml"],
            max_results=50,
            min_points=20,
        )
        assert req.max_results == 50
        assert req.min_points == 20

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HNFetchRequest(domain_keywords=[])

    def test_max_results_too_high(self) -> None:
        with pytest.raises(ValidationError):
            HNFetchRequest(domain_keywords=["x"], max_results=101)

    def test_max_results_too_low(self) -> None:
        with pytest.raises(ValidationError):
            HNFetchRequest(domain_keywords=["x"], max_results=0)

    def test_negative_min_points(self) -> None:
        with pytest.raises(ValidationError):
            HNFetchRequest(domain_keywords=["x"], min_points=-1)


class TestHNFetchResponse:
    def test_response_shape(self) -> None:
        resp = HNFetchResponse(
            topics=[],
            total_fetched=10,
            total_after_filter=3,
        )
        assert resp.total_fetched == 10
        assert resp.total_after_filter == 3
        assert resp.topics == []
