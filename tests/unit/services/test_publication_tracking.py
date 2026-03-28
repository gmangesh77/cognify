"""Tests for publication tracking in PublishingService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.content import SchemaOrgAuthor, SEOMetadata, StructuredDataLD
from src.models.publishing import PublicationStatus


class TestComputeSeoScore:
    def test_all_fields_present(self) -> None:
        from src.services.publishing.service import compute_seo_score

        seo = SEOMetadata(
            title="Test Title for SEO",
            description="A meta description for testing purposes.",
            keywords=["test", "seo"],
            canonical_url="https://example.com/article",
            structured_data=StructuredDataLD(
                context="https://schema.org",
                type="Article",
                headline="Test",
                description="Test description",
                author=SchemaOrgAuthor(),
                datePublished=datetime.now(UTC).isoformat(),
                dateModified=datetime.now(UTC).isoformat(),
            ),
        )
        assert compute_seo_score(seo) == 100

    def test_no_optional_fields(self) -> None:
        from src.services.publishing.service import compute_seo_score

        seo = SEOMetadata(
            title="Test Title",
            description="Description",
            keywords=[],
            canonical_url=None,
            structured_data=None,
        )
        assert compute_seo_score(seo) == 40

    def test_keywords_only(self) -> None:
        from src.services.publishing.service import compute_seo_score

        seo = SEOMetadata(
            title="T",
            description="D",
            keywords=["k1"],
        )
        assert compute_seo_score(seo) == 60

    def test_all_optional_fields(self) -> None:
        from src.services.publishing.service import compute_seo_score

        seo = SEOMetadata(
            title="T",
            description="D",
            keywords=["k1"],
            canonical_url="https://example.com",
            structured_data=StructuredDataLD(
                context="https://schema.org",
                type="Article",
                headline="Test",
                description="Test description",
                author=SchemaOrgAuthor(),
                datePublished=datetime.now(UTC).isoformat(),
                dateModified=datetime.now(UTC).isoformat(),
            ),
        )
        assert compute_seo_score(seo) == 100


class TestPublishingServicePersistence:
    @pytest.fixture
    def article_repo(self):
        repo = AsyncMock()
        article = MagicMock()
        article.id = uuid4()
        article.seo = SEOMetadata(title="T", description="D", keywords=["k"])
        repo.get.return_value = article
        return repo

    @pytest.fixture
    def pub_repo(self):
        repo = AsyncMock()
        repo.get_by_article_platform.return_value = None
        repo.create.side_effect = lambda p: p
        repo.update.side_effect = lambda p: p
        return repo

    @pytest.fixture
    def adapter(self):
        from src.models.publishing import PublicationResult

        adapter = AsyncMock()
        adapter.publish.return_value = PublicationResult(
            article_id=uuid4(),
            platform="ghost",
            status=PublicationStatus.SUCCESS,
            external_id="g-1",
            external_url="https://blog.example.com/post",
            published_at=datetime.now(UTC),
        )
        return adapter

    @pytest.fixture
    def transformer(self):
        t = MagicMock()
        t.transform.return_value = MagicMock(platform="ghost")
        return t

    @pytest.fixture
    def service(self, article_repo, pub_repo, transformer, adapter):
        from src.services.publishing.service import PlatformPair, PublishingService

        svc = PublishingService(article_repo, pub_repo)
        svc.register("ghost", PlatformPair(transformer=transformer, adapter=adapter))
        return svc

    @pytest.mark.asyncio
    async def test_publish_creates_publication_record(
        self, service, pub_repo, article_repo,
    ) -> None:
        result = await service.publish(article_repo.get.return_value.id, "ghost")
        assert result.status == PublicationStatus.SUCCESS
        pub_repo.create.assert_called_once()
        created = pub_repo.create.call_args[0][0]
        assert created.platform == "ghost"
        assert created.seo_score == 60
        assert len(created.event_history) == 1

    @pytest.mark.asyncio
    async def test_publish_updates_existing_record(
        self, service, pub_repo, article_repo,
    ) -> None:
        from src.models.publishing import Publication

        existing = Publication(
            id=uuid4(),
            article_id=article_repo.get.return_value.id,
            platform="ghost",
            status=PublicationStatus.FAILED,
            seo_score=60,
            error_message="old error",
            event_history=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        pub_repo.get_by_article_platform.return_value = existing

        result = await service.publish(article_repo.get.return_value.id, "ghost")
        assert result.status == PublicationStatus.SUCCESS
        pub_repo.update.assert_called_once()
        pub_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_republishes_failed(
        self, service, pub_repo, article_repo,
    ) -> None:
        from src.models.publishing import Publication

        pub_id = uuid4()
        failed = Publication(
            id=pub_id,
            article_id=article_repo.get.return_value.id,
            platform="ghost",
            status=PublicationStatus.FAILED,
            seo_score=60,
            error_message="Timeout",
            event_history=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        pub_repo.get.return_value = failed

        result = await service.retry(pub_id)
        assert result.status == PublicationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_retry_rejects_non_failed(
        self, service, pub_repo, article_repo,
    ) -> None:
        from src.models.publishing import Publication

        pub_id = uuid4()
        success = Publication(
            id=pub_id,
            article_id=article_repo.get.return_value.id,
            platform="ghost",
            status=PublicationStatus.SUCCESS,
            seo_score=80,
            event_history=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        pub_repo.get.return_value = success

        with pytest.raises(ValueError, match="Only failed publications"):
            await service.retry(pub_id)
