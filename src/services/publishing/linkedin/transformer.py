"""LinkedIn transformer: CanonicalArticle -> link-share PlatformPayload."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.models.publishing import PlatformPayload

if TYPE_CHECKING:
    from src.models.content import CanonicalArticle

_MAX_HASHTAGS = 5
_MAX_COMMENTARY = 3000
_MAX_DESCRIPTION = 256


class LinkedInTransformer:
    """Pure transformer for LinkedIn link-share posts."""

    def transform(self, article: CanonicalArticle) -> PlatformPayload:
        commentary = _build_commentary(article)
        metadata = _build_metadata(article)
        return PlatformPayload(
            platform="linkedin",
            article_id=article.id,
            content=commentary,
            metadata=metadata,
        )


def _build_commentary(article: CanonicalArticle) -> str:
    hashtags = _build_hashtags(article.seo.keywords)
    parts = [article.title, "", article.summary, "", hashtags]
    text = "\n".join(parts).strip()
    return text[:_MAX_COMMENTARY]


def _build_hashtags(keywords: list[str]) -> str:
    tags: list[str] = []
    for kw in keywords[:_MAX_HASHTAGS]:
        clean = re.sub(r"[^a-zA-Z0-9]", "", kw.lower())
        if clean:
            tags.append(f"#{clean}")
    return " ".join(tags)


def _build_metadata(
    article: CanonicalArticle,
) -> dict[str, str | int | bool]:
    desc = article.summary[:_MAX_DESCRIPTION]
    source_url = article.seo.canonical_url or ""
    return {
        "title": article.title,
        "description": desc,
        "source_url": source_url,
        "visibility": "PUBLIC",
    }
