from unittest.mock import MagicMock, patch

from src.config.settings import Settings
from src.services.trends import init_registry


class TestInitRegistry:
    def test_registers_all_five_sources(self) -> None:
        settings = Settings()
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

    def test_each_source_is_retrievable(self) -> None:
        settings = Settings()
        with patch(
            "src.services.trends.google_trends_client.TrendReq",
            return_value=MagicMock(),
        ):
            registry = init_registry(settings)
        for name in registry.available_sources():
            source = registry.get(name)
            assert source.source_name == name
