"""Image-provider registry.

Mirrors `src/services/trends/registry.py` (TrendSource pattern, ARCH-002):
a runtime container of concrete `ImageProvider` instances keyed by `name`.
Adding a provider is one new file under `providers/` plus one `register()`
call in `init_registry()` — nothing else in the codebase needs to know.
"""

from __future__ import annotations

from src.services.visuals.providers.base import ImageProvider


class ImageProviderRegistry:
    """Registered image-provider instances, keyed by `name`."""

    def __init__(self) -> None:
        self._providers: dict[str, ImageProvider] = {}

    def register(self, provider: ImageProvider) -> None:
        """Register a provider. Overwrites if name exists."""
        self._providers[provider.name] = provider

    def get(self, name: str) -> ImageProvider:
        """Get provider by name. Raises KeyError if not registered."""
        return self._providers[name]

    def has(self, name: str) -> bool:
        """Return True if a provider with this name is registered."""
        return name in self._providers

    def get_all(self) -> dict[str, ImageProvider]:
        """Return a copy of all registered providers."""
        return dict(self._providers)

    def available_providers(self) -> list[str]:
        """Return the sorted list of registered provider names."""
        return sorted(self._providers.keys())
