"""ArticleDraftRepository.find_by_article_id (AUTHOR-004 Task 4)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.models.content_pipeline import ArticleDraft
from src.services.content_repositories import InMemoryArticleDraftRepository


def _draft(article_id: UUID | None, created_at: datetime) -> ArticleDraft:
    return ArticleDraft(
        session_id=uuid4(),
        topic_id=uuid4(),
        article_id=article_id,
        created_at=created_at,
    )


@pytest.mark.asyncio
async def test_find_by_article_id_returns_newest_matching_draft() -> None:
    repo = InMemoryArticleDraftRepository()
    article_id = uuid4()
    now = datetime.now(UTC)
    older = await repo.create(_draft(article_id, now - timedelta(minutes=5)))
    newer = await repo.create(_draft(article_id, now))
    await repo.create(_draft(None, now))  # unfinalised draft — never matches
    found = await repo.find_by_article_id(article_id)
    assert found is not None
    assert found.id == newer.id != older.id


@pytest.mark.asyncio
async def test_find_by_article_id_is_none_when_unknown() -> None:
    repo = InMemoryArticleDraftRepository()
    await repo.create(_draft(uuid4(), datetime.now(UTC)))
    assert await repo.find_by_article_id(uuid4()) is None
