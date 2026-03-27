"""Ghost CMS transformer — CanonicalArticle to Ghost HTML payload."""

import json
import re

import markdown

from src.models.content import CanonicalArticle
from src.models.publishing import PlatformPayload

_MD_EXTENSIONS = ["tables", "fenced_code"]
_DEFAULT_API_BASE = "http://localhost:8000"


class GhostTransformer:
    """Pure transformer: CanonicalArticle -> Ghost PlatformPayload."""

    def __init__(self, api_base_url: str = _DEFAULT_API_BASE) -> None:
        self._api_base = api_base_url.rstrip("/")

    def transform(self, article: CanonicalArticle) -> PlatformPayload:
        html_body = _build_html_body(article, self._api_base)
        metadata = _build_metadata(article, self._api_base)
        return PlatformPayload(
            platform="ghost",
            article_id=article.id,
            content=html_body,
            metadata=metadata,
        )


def _build_html_body(article: CanonicalArticle, api_base: str) -> str:
    """Convert markdown to HTML, link citations, and inject JSON-LD."""
    body = _strip_references_section(article.body_markdown)
    html = markdown.markdown(body, extensions=_MD_EXTENSIONS)
    html = _linkify_citations(html, article)
    html = _rewrite_local_asset_urls(html, api_base)
    html += _build_references_html(article)
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
    article: CanonicalArticle, api_base: str,
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
        meta["feature_image"] = _asset_url(article.visuals[0].url, api_base)
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


def _strip_references_section(md: str) -> str:
    """Remove the raw References section from the markdown body."""
    return re.split(r"\n##\s+References\b", md, maxsplit=1)[0].rstrip()


def _build_references_html(article: CanonicalArticle) -> str:
    """Build a clean HTML references list from citations."""
    if not article.citations:
        return ""
    items = []
    for c in sorted(article.citations, key=lambda x: x.index):
        author = f" — {', '.join(c.authors)}" if c.authors else ""
        items.append(
            f'<li>[{c.index}] <a href="{c.url}" target="_blank" '
            f'rel="noopener">{c.title}</a>{author}</li>'
        )
    return (
        '\n<hr>\n<h2>References</h2>\n<ol style="list-style:none;padding:0">\n'
        + "\n".join(items)
        + "\n</ol>"
    )


def _linkify_citations(html: str, article: CanonicalArticle) -> str:
    """Convert plain [1], [2] references into clickable links."""
    url_map = {c.index: c.url for c in article.citations}
    def _replace_ref(match: re.Match) -> str:
        idx = int(match.group(1))
        url = url_map.get(idx)
        if url:
            return f'<a href="{url}" target="_blank" rel="noopener">[{idx}]</a>'
        return match.group(0)
    return re.sub(r"\[(\d+)\]", _replace_ref, html)


def _asset_url(path: str, api_base: str) -> str:
    """Convert a local file path to an HTTP URL served by the API."""
    if path.startswith(("http://", "https://")):
        return path
    normalized = path.replace("\\", "/")
    if normalized.startswith("generated_assets/"):
        return f"{api_base}/{normalized}"
    return f"{api_base}/generated_assets/{normalized}"


def _rewrite_local_asset_urls(html: str, api_base: str) -> str:
    """Replace local file paths in img src attributes with HTTP URLs."""
    def _replace(match: re.Match) -> str:
        url = match.group(1)
        return f'src="{_asset_url(url, api_base)}"'
    return re.sub(r'src="(generated_assets[^"]*)"', _replace, html)
