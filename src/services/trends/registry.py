from src.services.trends.protocol import TrendSource


class TrendSourceRegistry:
    """Manages registered trend source instances."""

    def __init__(self) -> None:
        self._sources: dict[str, TrendSource] = {}

    def register(self, source: TrendSource) -> None:
        """Register a source. Overwrites if name exists."""
        self._sources[source.source_name] = source

    def get(self, name: str) -> TrendSource:
        """Get source by name. Raises KeyError if not found."""
        return self._sources[name]

    def get_all(self) -> dict[str, TrendSource]:
        """Return copy of all registered sources."""
        return dict(self._sources)

    def available_sources(self) -> list[str]:
        """Return sorted list of registered source names."""
        return sorted(self._sources.keys())
