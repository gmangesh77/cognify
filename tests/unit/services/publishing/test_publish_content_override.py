"""Tests for PublishingService.publish(..., content_override=...) (AUTHOR-013).

The override seam lets a caller (the LinkedIn repurpose publish endpoint)
substitute the transformer's content with editor-approved text while
leaving every other publish concern (retries, persistence, article status)
untouched — ADR-004: the transformer stays pure, the service owns the
override.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.models.content import CanonicalArticle
from src.models.publishing import PlatformPayload, PublicationResult, PublicationStatus
from src.services.publishing.service import PlatformPair, PublishingService


def _make_pair(article_id, content: str = "original transformer content"):
    transformer = MagicMock()
    transformer.transform.return_value = PlatformPayload(
        platform="linkedin_post",
        article_id=article_id,
        content=content,
    )
    adapter = AsyncMock()
    adapter.publish.return_value = PublicationResult(
        article_id=article_id,
        platform="linkedin_post",
        status=PublicationStatus.SUCCESS,
        external_id="urn:li:share:1",
        external_url="https://linkedin.com/feed/update/1",
    )
    return transformer, adapter


class TestContentOverride:
    async def test_override_reaches_adapter_and_persists_publication(
        self, sample_article: CanonicalArticle
    ) -> None:
        transformer, adapter = _make_pair(sample_article.id)
        article_repo = AsyncMock()
        article_repo.get.return_value = sample_article
        pub_repo = AsyncMock()
        pub_repo.get_by_article_platform.return_value = None

        svc = PublishingService(article_repo, pub_repo)
        svc.register("linkedin_post", PlatformPair(transformer, adapter))

        result = await svc.publish(
            sample_article.id, "linkedin_post", content_override="Editor-approved text"
        )

        assert result.status == PublicationStatus.SUCCESS
        sent_payload = adapter.publish.call_args[0][0]
        assert sent_payload.content == "Editor-approved text"
        pub_repo.create.assert_awaited_once()
        created = pub_repo.create.await_args[0][0]
        assert created.platform == "linkedin_post"

    async def test_without_override_transformer_content_passes_through(
        self, sample_article: CanonicalArticle
    ) -> None:
        transformer, adapter = _make_pair(sample_article.id, content="from transformer")
        article_repo = AsyncMock()
        article_repo.get.return_value = sample_article

        svc = PublishingService(article_repo)
        svc.register("linkedin_post", PlatformPair(transformer, adapter))

        await svc.publish(sample_article.id, "linkedin_post")

        sent_payload = adapter.publish.call_args[0][0]
        assert sent_payload.content == "from transformer"

    async def test_override_none_is_a_noop(
        self, sample_article: CanonicalArticle
    ) -> None:
        transformer, adapter = _make_pair(sample_article.id, content="untouched")
        article_repo = AsyncMock()
        article_repo.get.return_value = sample_article

        svc = PublishingService(article_repo)
        svc.register("linkedin_post", PlatformPair(transformer, adapter))

        await svc.publish(sample_article.id, "linkedin_post", content_override=None)

        sent_payload = adapter.publish.call_args[0][0]
        assert sent_payload.content == "untouched"
