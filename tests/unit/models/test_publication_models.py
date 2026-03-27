"""Tests for Publication and PublicationEvent domain models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.publishing import (
    Publication,
    PublicationEvent,
    PublicationStatus,
    PlatformSummary,
)


class TestPublicationEvent:
    def test_valid_construction(self) -> None:
        event = PublicationEvent(
            timestamp=datetime.now(UTC),
            status=PublicationStatus.FAILED,
            error_message="Connection timeout",
        )
        assert event.status == PublicationStatus.FAILED
        assert event.error_message == "Connection timeout"

    def test_success_event_no_error(self) -> None:
        event = PublicationEvent(
            timestamp=datetime.now(UTC),
            status=PublicationStatus.SUCCESS,
        )
        assert event.error_message is None

    def test_frozen(self) -> None:
        event = PublicationEvent(
            timestamp=datetime.now(UTC),
            status=PublicationStatus.SUCCESS,
        )
        with pytest.raises(Exception):
            event.status = PublicationStatus.FAILED  # type: ignore[misc]


class TestPublication:
    def _make(self, **overrides) -> Publication:
        defaults = {
            "id": uuid4(),
            "article_id": uuid4(),
            "platform": "ghost",
            "status": PublicationStatus.SUCCESS,
            "view_count": 0,
            "seo_score": 80,
            "event_history": [],
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        defaults.update(overrides)
        return Publication(**defaults)

    def test_valid_construction(self) -> None:
        pub = self._make(external_id="abc123", external_url="https://blog.example.com/post")
        assert pub.platform == "ghost"
        assert pub.seo_score == 80

    def test_defaults(self) -> None:
        pub = self._make()
        assert pub.external_id is None
        assert pub.external_url is None
        assert pub.published_at is None
        assert pub.error_message is None
        assert pub.event_history == []

    def test_frozen(self) -> None:
        pub = self._make()
        with pytest.raises(Exception):
            pub.status = PublicationStatus.FAILED  # type: ignore[misc]

    def test_with_event_history(self) -> None:
        events = [
            PublicationEvent(
                timestamp=datetime.now(UTC),
                status=PublicationStatus.FAILED,
                error_message="Timeout",
            ),
            PublicationEvent(
                timestamp=datetime.now(UTC),
                status=PublicationStatus.SUCCESS,
            ),
        ]
        pub = self._make(event_history=events)
        assert len(pub.event_history) == 2
        assert pub.event_history[0].status == PublicationStatus.FAILED

    def test_json_serialization(self) -> None:
        pub = self._make(
            event_history=[
                PublicationEvent(
                    timestamp=datetime.now(UTC),
                    status=PublicationStatus.SUCCESS,
                ),
            ],
        )
        data = pub.model_dump(mode="json")
        assert isinstance(data["event_history"], list)
        assert data["event_history"][0]["status"] == "success"


class TestPlatformSummary:
    def test_valid_construction(self) -> None:
        summary = PlatformSummary(
            platform="ghost", total=10, success=8, failed=1, scheduled=1,
        )
        assert summary.total == 10
        assert summary.success == 8
