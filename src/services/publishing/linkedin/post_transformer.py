"""LinkedIn post transformer: CanonicalArticle -> repurposed-post payload.

Registered under the `linkedin_post` platform key (AUTHOR-013), separate
from `linkedin` (the existing thought-leadership commentary post).
`PublishingService.publish`'s `content_override` seam swaps this
transformer's fallback body for the editor-approved repurposed text —
the transformer itself stays pure (ADR-004): no I/O, and it never reaches
into `content_override` handling, which lives entirely in the service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models.publishing import PlatformPayload
from src.services.publishing.linkedin.transformer import (
    _build_commentary,
    _build_metadata,
)

if TYPE_CHECKING:
    from src.models.content import CanonicalArticle

_DEFAULT_API_BASE = "http://localhost:8000"


class LinkedInPostTransformer:
    """Pure transformer for repurposed LinkedIn posts."""

    def __init__(self, api_base_url: str = _DEFAULT_API_BASE) -> None:
        self._api_base = api_base_url.rstrip("/")

    def transform(self, article: CanonicalArticle) -> PlatformPayload:
        # Fallback body used only when the caller publishes without a
        # `content_override` (i.e. skips the repurpose-and-edit flow).
        fallback_body = _build_commentary(article)
        metadata = _build_metadata(article, self._api_base)
        return PlatformPayload(
            platform="linkedin_post",
            article_id=article.id,
            content=fallback_body,
            metadata=metadata,
        )


__all__ = ["LinkedInPostTransformer"]
