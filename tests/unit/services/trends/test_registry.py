import pytest

from src.api.schemas.topics import RawTopic
from src.services.trends.protocol import TrendFetchConfig
from src.services.trends.registry import TrendSourceRegistry


class _FakeSource:
    """Minimal TrendSource implementation for testing."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def source_name(self) -> str:
        return self._name

    async def fetch_and_normalize(
        self, config: TrendFetchConfig,
    ) -> list[RawTopic]:
        return []


class TestTrendSourceRegistry:
    def test_register_and_get(self) -> None:
        registry = TrendSourceRegistry()
        source = _FakeSource("test")
        registry.register(source)
        assert registry.get("test") is source

    def test_get_unknown_raises(self) -> None:
        registry = TrendSourceRegistry()
        with pytest.raises(KeyError):
            registry.get("unknown")

    def test_available_sources_sorted(self) -> None:
        registry = TrendSourceRegistry()
        registry.register(_FakeSource("reddit"))
        registry.register(_FakeSource("arxiv"))
        registry.register(_FakeSource("hackernews"))
        assert registry.available_sources() == [
            "arxiv", "hackernews", "reddit",
        ]

    def test_get_all_returns_copy(self) -> None:
        registry = TrendSourceRegistry()
        source = _FakeSource("test")
        registry.register(source)
        all_sources = registry.get_all()
        assert all_sources == {"test": source}
        all_sources["injected"] = _FakeSource("injected")
        assert "injected" not in registry.get_all()

    def test_duplicate_overwrites(self) -> None:
        registry = TrendSourceRegistry()
        first = _FakeSource("test")
        second = _FakeSource("test")
        registry.register(first)
        registry.register(second)
        assert registry.get("test") is second

    def test_empty_registry(self) -> None:
        registry = TrendSourceRegistry()
        assert registry.available_sources() == []
        assert registry.get_all() == {}
