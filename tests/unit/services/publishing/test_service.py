"""Tests for PublishingService orchestrator."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.content import CanonicalArticle
from src.models.publishing import PlatformPayload, PublicationResult, PublicationStatus
from src.services.publishing.service import PlatformPair, PublishingService


def _make_pair(transform_result=None, publish_result=None):
    transformer = MagicMock()
    adapter = AsyncMock()
    if transform_result:
        transformer.transform.return_value = transform_result
    else:
        transformer.transform.return_value = PlatformPayload(
            platform="test",
            article_id=uuid4(),
            content="<p>html</p>",
        )
    if publish_result:
        adapter.publish.return_value = publish_result
    else:
        adapter.publish.return_value = PublicationResult(
            article_id=uuid4(),
            platform="test",
            status=PublicationStatus.SUCCESS,
            external_id="ext-1",
            external_url="https://example.com/post",
        )
    return PlatformPair(transformer=transformer, adapter=adapter)


@pytest.fixture
def article_repo(sample_article: CanonicalArticle) -> AsyncMock:
    repo = AsyncMock()
    repo.get.return_value = sample_article
    return repo


class TestPublishingService:
    async def test_publish_transforms_and_publishes(
        self,
        article_repo: AsyncMock,
        sample_article: CanonicalArticle,
    ) -> None:
        pair = _make_pair()
        svc = PublishingService(article_repo)
        svc.register("test", pair)
        result = await svc.publish(sample_article.id, "test")
        pair.transformer.transform.assert_called_once_with(sample_article)
        pair.adapter.publish.assert_called_once()
        assert result.status == PublicationStatus.SUCCESS

    async def test_publish_unknown_platform(
        self,
        article_repo: AsyncMock,
        sample_article: CanonicalArticle,
    ) -> None:
        svc = PublishingService(article_repo)
        result = await svc.publish(sample_article.id, "nonexistent")
        assert result.status == PublicationStatus.FAILED
        assert "Unknown platform" in (result.error_message or "")

    async def test_publish_missing_article(self) -> None:
        repo = AsyncMock()
        repo.get.return_value = None
        svc = PublishingService(repo)
        svc.register("test", _make_pair())
        result = await svc.publish(uuid4(), "test")
        assert result.status == PublicationStatus.FAILED
        assert "not found" in (result.error_message or "")

    async def test_retries_on_network_error(
        self,
        article_repo: AsyncMock,
        sample_article: CanonicalArticle,
    ) -> None:
        pair = _make_pair()
        success = PublicationResult(
            article_id=sample_article.id,
            platform="test",
            status=PublicationStatus.SUCCESS,
        )
        pair.adapter.publish.side_effect = [
            Exception("timeout"),
            success,
        ]
        svc = PublishingService(article_repo)
        svc.register("test", pair)
        result = await svc.publish(sample_article.id, "test")
        assert result.status == PublicationStatus.SUCCESS
        assert pair.adapter.publish.call_count == 2

    async def test_no_retry_on_permanent_failure(
        self,
        article_repo: AsyncMock,
        sample_article: CanonicalArticle,
    ) -> None:
        failed = PublicationResult(
            article_id=sample_article.id,
            platform="test",
            status=PublicationStatus.FAILED,
            error_message="Bad request",
        )
        pair = _make_pair(publish_result=failed)
        svc = PublishingService(article_repo)
        svc.register("test", pair)
        result = await svc.publish(sample_article.id, "test")
        assert result.status == PublicationStatus.FAILED
        assert pair.adapter.publish.call_count == 1

    async def test_passes_schedule_at(
        self,
        article_repo: AsyncMock,
        sample_article: CanonicalArticle,
    ) -> None:
        from datetime import UTC, datetime, timedelta

        pair = _make_pair()
        svc = PublishingService(article_repo)
        svc.register("test", pair)
        future = datetime.now(UTC) + timedelta(hours=1)
        await svc.publish(sample_article.id, "test", schedule_at=future)
        call_args = pair.adapter.publish.call_args
        passed = call_args[0][1] if len(call_args[0]) > 1 else None
        kw = call_args.kwargs.get("schedule_at")
        assert passed == future or kw == future

    async def test_register_platform(self) -> None:
        svc = PublishingService(AsyncMock())
        pair = _make_pair()
        svc.register("ghost", pair)
        assert "ghost" in svc._platforms
