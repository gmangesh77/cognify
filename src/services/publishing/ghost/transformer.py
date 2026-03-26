"""Ghost CMS transformer — CanonicalArticle to Ghost HTML payload."""

import json
import re

import markdown

from src.models.content import CanonicalArticle
from src.models.publishing import PlatformPayload

_MD_EXTENSIONS = ["tables", "fenced_code"]


class GhostTransformer:
    """Pure transformer: CanonicalArticle -> Ghost PlatformPayload."""

    def transform(self, article: CanonicalArticle) -> PlatformPayload:
        html_body = _build_html_body(article)
        metadata = _build_metadata(article)
        return PlatformPayload(
            platform="ghost",
            article_id=article.id,
            content=html_body,
            metadata=metadata,
        )


def _build_html_body(article: CanonicalArticle) -> str:
    """Convert markdown to HTML and inject JSON-LD."""
    html = markdown.markdown(article.body_markdown, extensions=_MD_EXTENSIONS)
    json_ld = _build_json_ld(article)
    if json_ld:
        html = json_ld + "\n" + html
    return html


def _build_json_ld(article: CanonicalArticle) -> str:
    """Generate a JSON-LD script tag from structured data."""
    sd = article.seo.structured_data
    if sd is None:
        return ""
    data = sd.model_dump(by_alias=True)
    script = json.dumps(data, indent=2)
    return f'<script type="application/ld+json">\n{script}\n</script>'


def _build_metadata(
    article: CanonicalArticle,
) -> dict[str, str | int | bool]:
    """Build Ghost-specific metadata dict."""
    meta: dict[str, str | int | bool] = {
        "title": article.title,
        "slug": _slugify(article.title),
        "custom_excerpt": article.summary,
        "meta_title": article.seo.title,
        "meta_description": article.seo.description,
    }
    if article.seo.canonical_url:
        meta["canonical_url"] = article.seo.canonical_url
    tags = _build_tags(article)
    if tags:
        meta["tags"] = tags
    if article.visuals:
        meta["feature_image"] = article.visuals[0].url
    return meta


def _build_tags(article: CanonicalArticle) -> str:
    """Combine domain + SEO keywords into a comma-separated tag string."""
    tags = [article.domain] + list(article.seo.keywords)
    unique = list(dict.fromkeys(tags))
    return ",".join(unique)


def _slugify(title: str) -> str:
    """Convert a title to a URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")
