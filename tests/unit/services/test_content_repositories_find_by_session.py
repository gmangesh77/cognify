"""Tests for ArticleRepository.find_by_session (AUTHOR-001 Task 3)."""

from uuid import uuid4

import pytest

from src.models.content import Provenance
from src.services.content_repositories import InMemoryArticleRepository
from tests.unit.models.test_content import _make_article


def _provenance_for(session_id: object) -> Provenance:
    return Provenance(
        research_session_id=session_id,
        primary_model="claude-opus-4",
        drafting_model="claude-sonnet-4",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="1.0.0",
    )


@pytest.mark.asyncio
async def test_find_by_session_returns_matching_article() -> None:
    repo = InMemoryArticleRepository()
    sid = uuid4()
    article = _make_article(provenance=_provenance_for(sid))
    await repo.create(article)
    assert (await repo.find_by_session(sid)) is not None
    assert (await repo.find_by_session(uuid4())) is None
