from unittest.mock import MagicMock, patch

from src.config.settings import Settings
from src.services.trends import init_registry


def _settings_with_all_keys() -> Settings:
    """Settings with credentials populated so all 5 sources register."""
    return Settings(
        newsapi_api_key="test-newsapi-key",
        reddit_client_id="test-reddit-id",
        reddit_client_secret="test-reddit-secret",
    )


class TestInitRegistry:
    def test_registers_all_five_sources_when_credentials_present(self) -> None:
        """All 5 sources register when their API credentials are configured."""
        settings = _settings_with_all_keys()
        with patch(
            "src.services.trends.google_trends_client.TrendReq",
            return_value=MagicMock(),
        ):
            registry = init_registry(settings)
        names = registry.available_sources()
        assert len(names) == 5
        assert "arxiv" in names
        assert "google_trends" in names
        assert "hackernews" in names
        assert "newsapi" in names
        assert "reddit" in names

    def test_skips_newsapi_and_reddit_without_credentials(self) -> None:
        """Sources requiring API keys are skipped (AB#16751) so they don't
        spam errors on every scan when credentials aren't configured."""
        settings = Settings(
            newsapi_api_key="",
            reddit_client_id="",
            reddit_client_secret="",
        )
        with patch(
            "src.services.trends.google_trends_client.TrendReq",
            return_value=MagicMock(),
        ):
            registry = init_registry(settings)
        names = registry.available_sources()
        assert "newsapi" not in names
        assert "reddit" not in names
        # The 3 keyless sources still register
        assert "arxiv" in names
        assert "google_trends" in names
        assert "hackernews" in names

    def test_each_source_is_retrievable(self) -> None:
        settings = _settings_with_all_keys()
        with patch(
            "src.services.trends.google_trends_client.TrendReq",
            return_value=MagicMock(),
        ):
            registry = init_registry(settings)
        for name in registry.available_sources():
            source = registry.get(name)
            assert source.source_name == name
