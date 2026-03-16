"""Tests for publishing contract models and protocols."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.publishing import (
    Adapter,
    PlatformPayload,
    PublicationResult,
    PublicationStatus,
    Transformer,
)
from src.models.content import CanonicalArticle


class TestPlatformPayload:
    def test_valid_construction(self):
        payload = PlatformPayload(
            platform="ghost",
            article_id=uuid4(),
            content="<h1>Title</h1><p>Body</p>",
        )
        assert payload.platform == "ghost"
        assert payload.metadata == {}

    def test_empty_platform_rejected(self):
        with pytest.raises(ValidationError):
            PlatformPayload(
                platform="",
                article_id=uuid4(),
                content="content",
            )

    def test_metadata_accepts_mixed_types(self):
        payload = PlatformPayload(
            platform="wordpress",
            article_id=uuid4(),
            content="content",
            metadata={"featured": True, "word_count": 1500, "slug": "test-post"},
        )
        assert payload.metadata["featured"] is True
        assert payload.metadata["word_count"] == 1500

    def test_serialization_round_trip(self):
        payload = PlatformPayload(
            platform="ghost",
            article_id=uuid4(),
            content="<p>Body</p>",
            metadata={"tag": "test"},
        )
        data = payload.model_dump()
        restored = PlatformPayload.model_validate(data)
        assert restored.platform == payload.platform


class TestPublicationStatus:
    def test_values(self):
        assert PublicationStatus.SUCCESS == "success"
        assert PublicationStatus.FAILED == "failed"
        assert PublicationStatus.SCHEDULED == "scheduled"


class TestPublicationResult:
    def test_success_result(self):
        result = PublicationResult(
            article_id=uuid4(),
            platform="ghost",
            status=PublicationStatus.SUCCESS,
            external_id="abc123",
            external_url="https://blog.example.com/post/abc123",
            published_at=datetime.now(UTC),
        )
        assert result.status == PublicationStatus.SUCCESS
        assert result.error_message is None

    def test_failed_result(self):
        result = PublicationResult(
            article_id=uuid4(),
            platform="ghost",
            status=PublicationStatus.FAILED,
            error_message="Invalid API key",
        )
        assert result.status == PublicationStatus.FAILED
        assert result.error_message == "Invalid API key"
        assert result.external_id is None

    def test_scheduled_result(self):
        result = PublicationResult(
            article_id=uuid4(),
            platform="wordpress",
            status=PublicationStatus.SCHEDULED,
        )
        assert result.status == PublicationStatus.SCHEDULED


class TestTransformerProtocol:
    def test_class_satisfies_protocol(self):
        class MockTransformer:
            def transform(self, article: CanonicalArticle) -> PlatformPayload:
                return PlatformPayload(
                    platform="test",
                    article_id=article.id,
                    content=article.body_markdown,
                )

        assert isinstance(MockTransformer(), Transformer)

    def test_non_conforming_class_fails(self):
        class NotATransformer:
            def do_something(self) -> None:
                pass

        assert not isinstance(NotATransformer(), Transformer)


class TestAdapterProtocol:
    def test_class_satisfies_protocol(self):
        class MockAdapter:
            async def publish(
                self,
                payload: PlatformPayload,
                schedule_at: datetime | None = None,
            ) -> PublicationResult:
                return PublicationResult(
                    article_id=payload.article_id,
                    platform=payload.platform,
                    status=PublicationStatus.SUCCESS,
                )

        assert isinstance(MockAdapter(), Adapter)

    def test_non_conforming_class_fails(self):
        class NotAnAdapter:
            def upload(self) -> None:
                pass

        assert not isinstance(NotAnAdapter(), Adapter)
