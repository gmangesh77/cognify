"""ArticleRepository.update_metadata (AUTHOR-006)."""

from uuid import uuid4

from src.services.content_repositories import InMemoryArticleRepository
from tests.unit.api.test_content_endpoints import _build_article


async def test_updates_title_subtitle_and_seo() -> None:
    repo = InMemoryArticleRepository()
    article = _build_article(uuid4())
    await repo.create(article)
    new_seo = article.seo.model_copy(update={"title": "New SEO title"})
    updated = await repo.update_metadata(
        article.id,
        {"title": "New title", "subtitle": "New sub", "seo": new_seo},
    )
    assert updated is not None
    assert updated.title == "New title"
    assert updated.subtitle == "New sub"
    assert updated.seo.title == "New SEO title"
    stored = await repo.get(article.id)
    assert stored is not None and stored.title == "New title"
    assert stored.body_markdown == article.body_markdown


async def test_partial_update_keeps_other_fields() -> None:
    repo = InMemoryArticleRepository()
    article = _build_article(uuid4())
    await repo.create(article)
    updated = await repo.update_metadata(article.id, {"subtitle": "Only sub"})
    assert updated is not None
    assert updated.title == article.title
    assert updated.subtitle == "Only sub"
    assert updated.seo.title == article.seo.title


async def test_unknown_article_returns_none() -> None:
    repo = InMemoryArticleRepository()
    assert await repo.update_metadata(uuid4(), {"title": "x"}) is None
