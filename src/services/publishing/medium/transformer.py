"""Medium transformer — CanonicalArticle to Medium HTML payload."""

import markdown

from src.models.content import CanonicalArticle
from src.models.publishing import PlatformPayload

_MD_EXTENSIONS = ["tables", "fenced_code"]
_MAX_MEDIUM_TAGS = 5


class MediumTransformer:
    """Pure transformer: CanonicalArticle -> Medium PlatformPayload."""

    def transform(self, article: CanonicalArticle) -> PlatformPayload:
        html = markdown.markdown(article.body_markdown, extensions=_MD_EXTENSIONS)
        metadata = _build_metadata(article)
        return PlatformPayload(
            platform="medium",
            article_id=article.id,
            content=html,
            metadata=metadata,
        )


def _build_metadata(
    article: CanonicalArticle,
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
    return meta
