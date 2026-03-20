import pytest
from pydantic import ValidationError

from src.services.trends.protocol import TrendFetchConfig, TrendSourceError


class TestTrendFetchConfig:
    def test_valid_config(self) -> None:
        config = TrendFetchConfig(domain_keywords=["ai", "ml"])
        assert config.domain_keywords == ["ai", "ml"]
        assert config.max_results == 30

    def test_custom_max_results(self) -> None:
        config = TrendFetchConfig(domain_keywords=["ai"], max_results=10)
        assert config.max_results == 10

    def test_empty_keywords_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrendFetchConfig(domain_keywords=[])

    def test_max_results_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            TrendFetchConfig(domain_keywords=["ai"], max_results=0)

    def test_max_results_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            TrendFetchConfig(domain_keywords=["ai"], max_results=101)


class TestTrendSourceError:
    def test_format(self) -> None:
        err = TrendSourceError("hackernews", "API timeout")
        assert str(err) == "[hackernews] API timeout"
        assert err.source_name == "hackernews"

    def test_is_exception(self) -> None:
        err = TrendSourceError("reddit", "Rate limited")
        assert isinstance(err, Exception)
