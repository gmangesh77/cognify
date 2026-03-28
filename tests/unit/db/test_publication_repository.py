"""Unit tests for PgPublicationRepository using mocked sessions."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models.publishing import (
    PublicationStatus,
)


@pytest.fixture
def article_id():
    return uuid4()


class TestPgPublicationRepository:
    """Tests verify repository _to_model conversion logic."""

    def test_to_model_converts_row(self, article_id) -> None:
        from src.db.repositories import PgPublicationRepository

        row = MagicMock()
        row.id = uuid4()
        row.article_id = article_id
        row.platform = "ghost"
        row.status = "success"
        row.external_id = "g-123"
        row.external_url = "https://blog.example.com/post"
        row.published_at = datetime.now(UTC)
        row.view_count = 42
        row.seo_score = 80
        row.error_message = None
        row.event_history = [
            {
                "timestamp": "2026-03-27T10:00:00+00:00",
                "status": "success",
                "error_message": None,
            },
        ]
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        pub = PgPublicationRepository._to_model(row)
        assert pub.platform == "ghost"
        assert pub.status == PublicationStatus.SUCCESS
        assert pub.view_count == 42
        assert len(pub.event_history) == 1

    def test_to_model_empty_event_history(self, article_id) -> None:
        from src.db.repositories import PgPublicationRepository

        row = MagicMock()
        row.id = uuid4()
        row.article_id = article_id
        row.platform = "medium"
        row.status = "failed"
        row.external_id = None
        row.external_url = None
        row.published_at = None
        row.view_count = 0
        row.seo_score = 60
        row.error_message = "API error"
        row.event_history = []
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        pub = PgPublicationRepository._to_model(row)
        assert pub.status == PublicationStatus.FAILED
        assert pub.event_history == []
        assert pub.error_message == "API error"
