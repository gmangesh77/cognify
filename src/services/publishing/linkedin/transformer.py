"""LinkedIn transformer: CanonicalArticle -> standalone thought-leadership post."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.models.publishing import PlatformPayload
from src.services.visuals.inject import pick_cover_visual

if TYPE_CHECKING:
    from src.models.content import CanonicalArticle

_MAX_HASHTAGS = 5
_MAX_COMMENTARY = 3000
_MAX_DESCRIPTION = 256
_DEFAULT_API_BASE = "http://localhost:8000"


class LinkedInTransformer:
    """Pure transformer for LinkedIn posts."""

    def __init__(self, api_base_url: str = _DEFAULT_API_BASE) -> None:
        self._api_base = api_base_url.rstrip("/")

    def transform(self, article: CanonicalArticle) -> PlatformPayload:
        commentary = _build_commentary(article)
        metadata = _build_metadata(article, self._api_base)
        return PlatformPayload(
            platform="linkedin",
            article_id=article.id,
            content=commentary,
            metadata=metadata,
        )


def _build_commentary(article: CanonicalArticle) -> str:
    parts: list[str] = []

    # Lead with key insights directly — no "this article" framing
    claims = getattr(article, "key_claims", []) or []
    if claims:
        # Use first claim as the hook (stripped of citations)
        hook = re.sub(r"\s*\[\d+\](\[\d+\])*", "", claims[0])
        parts.append(hook)
        parts.append("")

        # Remaining claims as takeaways
        if len(claims) > 1:
            for claim in claims[1:4]:
                clean = re.sub(r"\s*\[\d+\](\[\d+\])*", "", claim)
                parts.append(f"→ {clean}")
            parts.append("")
    else:
        # Fallback to summary if no claims, but strip "article" references
        summary = re.sub(
            r"(?i)^the article\s+(discusses|explores|examines|covers|presents)\s+",
            "",
            article.summary,
        )
        parts.append(summary)
        parts.append("")

    # Hashtags
    hashtags = _build_hashtags(article.seo.keywords)
    if hashtags:
        parts.append(hashtags)

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
    api_base: str,
) -> dict[str, str | int | bool]:
    desc = article.summary[:_MAX_DESCRIPTION]
    source_url = article.seo.canonical_url or ""
    meta: dict[str, str | int | bool] = {
        "title": article.title,
        "description": desc,
        "source_url": source_url,
        "visibility": "PUBLIC",
    }
    # Cover-image URL surfaced for the adapter's asset-upload dance.
    # The adapter (Phase 6 production rollout) will upload this URL to
    # LinkedIn's Assets API to obtain a digitalmediaAsset URN before
    # attaching to the post body. For Phase 3 we only expose the URL.
    cover = pick_cover_visual(article)
    if cover is None and article.visuals:
        cover = article.visuals[0]
    if cover is not None:
        meta["cover_image_url"] = _asset_url(cover.url, api_base)
        if cover.alt_text:
            meta["cover_image_alt"] = cover.alt_text
    return meta


def _asset_url(path: str, api_base: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    base = api_base.rstrip("/")
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized.startswith("generated_assets/"):
        return f"{base}/{normalized}"
    return f"{base}/generated_assets/{normalized}"
