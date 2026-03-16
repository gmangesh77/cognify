"""Core domain models and cross-cutting contracts."""

from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
)
from src.models.publishing import (
    Adapter,
    PlatformPayload,
    PublicationResult,
    PublicationStatus,
    Transformer,
)

__all__ = [
    "CanonicalArticle",
    "Citation",
    "ContentType",
    "ImageAsset",
    "Provenance",
    "SEOMetadata",
    "Adapter",
    "PlatformPayload",
    "PublicationResult",
    "PublicationStatus",
    "Transformer",
]
