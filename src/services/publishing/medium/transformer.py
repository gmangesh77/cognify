"""Medium transformer — CanonicalArticle to Medium HTML payload."""

from __future__ import annotations

import html as html_lib

import markdown

from src.models.content import CanonicalArticle
from src.models.publishing import PlatformPayload
from src.services.visuals.inject import (
    InjectionContext,
    inject_visuals,
    pick_cover_visual,
)

_MD_EXTENSIONS = ["tables", "fenced_code"]
_MAX_MEDIUM_TAGS = 5
_DEFAULT_API_BASE = "http://localhost:8000"


class MediumTransformer:
    """Pure transformer: CanonicalArticle -> Medium PlatformPayload."""

    def __init__(self, api_base_url: str = _DEFAULT_API_BASE) -> None:
        self._api_base = api_base_url.rstrip("/")

    def transform(self, article: CanonicalArticle) -> PlatformPayload:
        html_body = _build_html_body(article, self._api_base)
        metadata = _build_metadata(article, self._api_base)
        return PlatformPayload(
            platform="medium",
            article_id=article.id,
            content=html_body,
            metadata=metadata,
        )


def _build_html_body(article: CanonicalArticle, api_base: str) -> str:
    """Render markdown to HTML, prepend cover, then inject planned visuals."""
    html = markdown.markdown(article.body_markdown, extensions=_MD_EXTENSIONS)
    if article.image_specs or article.visuals:
        html = inject_visuals(
            article.model_copy(update={"body_markdown": html}),
            InjectionContext(api_base_url=api_base),
        )
    cover = pick_cover_visual(article)
    if cover is None and article.visuals:
        # Medium doesn't have a separate feature_image field, so prepend the
        # first available visual when nothing is explicitly tagged as cover.
        cover = article.visuals[0]
    if cover is not None:
        cover_url = _asset_url(cover.url, api_base)
        cover_alt = html_lib.escape(cover.alt_text or article.title)
        cover_html = (
            '<figure class="cog-cover">'
            f'<img src="{cover_url}" alt="{cover_alt}" '
            'style="max-width:100%;height:auto;" />'
            "</figure>\n"
        )
        html = cover_html + html
    return html


def _build_metadata(
    article: CanonicalArticle,
    api_base: str,
) -> dict[str, str | int | bool]:
    """Build Medium-specific metadata dict."""
    meta: dict[str, str | int | bool] = {
        "title": article.title,
        "contentFormat": "html",
    }
    tags = list(article.seo.keywords)[:_MAX_MEDIUM_TAGS]
    if tags:
        meta["tags"] = ",".join(tags)
    if article.seo.canonical_url:
        meta["canonicalUrl"] = article.seo.canonical_url
    cover = pick_cover_visual(article)
    if cover is None and article.visuals:
        cover = article.visuals[0]
    if cover is not None:
        meta["cover_image"] = _asset_url(cover.url, api_base)
    return meta


def _asset_url(path: str, api_base: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    base = api_base.rstrip("/")
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized.startswith("generated_assets/"):
        return f"{base}/{normalized}"
    return f"{base}/generated_assets/{normalized}"
