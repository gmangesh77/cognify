"""Tests for manual topic creation — repository, dedup service, and endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.api.schemas.topic_analysis import ManualTopicCreateRequest
from src.api.schemas.topics import PersistedTopic
from src.services.topic_persistence import TopicPersistenceService


def _make_request(**kwargs: object) -> ManualTopicCreateRequest:
    defaults: dict[str, object] = {
        "title": "AI Security Trends 2026",
        "description": "An overview of AI-driven security threats.",
        "domain": "cybersecurity",
        "keywords": ["AI", "security"],
        "force_create": False,
    }
    defaults.update(kwargs)
    return ManualTopicCreateRequest(**defaults)  # type: ignore[arg-type]


def _make_persisted(
    topic_id: object = None,
    title: str = "AI Security Trends 2026",
    domain: str = "cybersecurity",
) -> PersistedTopic:
    now = datetime.now(UTC)
    return PersistedTopic(
        id=topic_id or uuid4(),
        title=title,
        description="About AI security",
        source="manual",
        external_url="",
        trend_score=0.0,
        velocity=0.0,
        domain=domain,
        discovered_at=now,
        composite_score=None,
        rank=None,
        source_count=1,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestPgTopicRepositoryCreateManual:
    @pytest.mark.asyncio
    async def test_create_manual_returns_uuid(self) -> None:
        """create_manual inserts a row and returns its UUID."""
        from src.db.repositories import PgTopicRepository

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        repo = PgTopicRepository(mock_sf)
        req = _make_request()

        topic_id = await repo.create_manual(req)

        assert topic_id is not None
        mock_session.add.assert_called_once()
        await mock_session.commit()

    @pytest.mark.asyncio
    async def test_create_manual_uses_manual_source(self) -> None:
        """create_manual creates a TopicRow with source='manual' and trend_score=0.0."""
        from src.db.repositories import PgTopicRepository
        from src.db.tables import TopicRow

        captured_row: list[TopicRow] = []

        mock_session = MagicMock()  # sync mock so .add() is synchronous
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        def _capture_add(row: object) -> None:
            captured_row.append(row)  # type: ignore[arg-type]

        mock_session.add.side_effect = _capture_add
        mock_sf = MagicMock(return_value=mock_session)

        repo = PgTopicRepository(mock_sf)
        req = _make_request(title="Test Topic", domain="tech", keywords=["k1"])

        await repo.create_manual(req)

        assert len(captured_row) == 1
        row = captured_row[0]
        assert isinstance(row, TopicRow)
        assert row.source == "manual"
        assert row.trend_score == 0.0
        assert row.velocity == 0.0
        assert row.title == "Test Topic"
        assert row.domain == "tech"
        assert row.domain_keywords == ["k1"]
        assert row.composite_score is None
        assert row.rank is None


# ---------------------------------------------------------------------------
# TopicPersistenceService.find_duplicate_by_title tests
# ---------------------------------------------------------------------------


class TestFindDuplicateByTitle:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_existing_topics(self) -> None:
        """No existing topics → returns None."""
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([], 0)
        embedding = MagicMock()

        svc = TopicPersistenceService(repo=repo, embedding_service=embedding)

        result = await svc.find_duplicate_by_title("New Topic", "tech")

        assert result is None
        repo.list_by_domain.assert_called_once_with("tech", 1, 200)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_title_match(self) -> None:
        """Existing topics with different titles → returns None."""
        existing_id = uuid4()
        existing = _make_persisted(topic_id=existing_id, title="Cloud Security")
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([existing], 1)
        embedding = MagicMock()

        svc = TopicPersistenceService(repo=repo, embedding_service=embedding)

        result = await svc.find_duplicate_by_title("AI Security Trends", "cybersecurity")

        assert result is None

    @pytest.mark.asyncio
    async def test_finds_exact_title_match(self) -> None:
        """Exact title match (case-insensitive) → returns existing topic ID."""
        existing_id = uuid4()
        existing = _make_persisted(
            topic_id=existing_id,
            title="AI Security Trends 2026",
            domain="cybersecurity",
        )
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([existing], 1)
        embedding = MagicMock()

        svc = TopicPersistenceService(repo=repo, embedding_service=embedding)

        result = await svc.find_duplicate_by_title(
            "AI Security Trends 2026", "cybersecurity"
        )

        assert result == existing_id

    @pytest.mark.asyncio
    async def test_finds_match_case_insensitive(self) -> None:
        """Title match is case-insensitive and trims whitespace."""
        existing_id = uuid4()
        existing = _make_persisted(topic_id=existing_id, title="  Cloud Native 2026  ")
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([existing], 1)
        embedding = MagicMock()

        svc = TopicPersistenceService(repo=repo, embedding_service=embedding)

        result = await svc.find_duplicate_by_title(
            "cloud native 2026", "cybersecurity"
        )

        assert result == existing_id


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestManualTopicCreateRequest:
    def test_valid_request(self) -> None:
        req = ManualTopicCreateRequest(
            title="Valid Title",
            description="A valid description.",
            domain="tech",
        )
        assert req.title == "Valid Title"
        assert req.keywords == []
        assert req.force_create is False

    def test_title_too_short_raises(self) -> None:
        with pytest.raises(Exception):
            ManualTopicCreateRequest(
                title="AB",
                description="desc",
                domain="tech",
            )

    def test_keywords_default_empty(self) -> None:
        req = ManualTopicCreateRequest(
            title="Some Title",
            description="desc",
            domain="tech",
        )
        assert req.keywords == []
