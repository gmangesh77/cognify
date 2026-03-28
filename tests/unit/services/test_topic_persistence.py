"""Tests for topic persistence with cross-scan dedup."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.api.schemas.topics import RankedTopic
from src.services.topic_persistence import TopicPersistenceService


def _make_ranked(title: str, score: float) -> RankedTopic:
    return RankedTopic(
        title=title,
        description=f"About {title}",
        source="hackernews",
        external_url="https://example.com",
        trend_score=score,
        discovered_at=datetime.now(UTC),
        velocity=10.0,
        domain_keywords=["tech"],
        composite_score=score,
        rank=1,
        source_count=1,
    )


class TestTopicPersistenceService:
    @pytest.mark.asyncio
    async def test_inserts_new_topics(self) -> None:
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([], 0)
        repo.create_from_ranked.return_value = "new-id"
        embedding = MagicMock()
        embedding.embed.return_value = [[0.1, 0.2, 0.3]]

        svc = TopicPersistenceService(
            repo=repo,
            embedding_service=embedding,
            threshold=0.85,
        )
        result = await svc.persist_ranked_topics(
            [_make_ranked("New Topic", 80)],
            "tech",
        )
        assert result.new_count == 1
        assert result.updated_count == 0
        repo.create_from_ranked.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_on_match(self) -> None:
        from src.api.schemas.topics import PersistedTopic

        existing_id = uuid4()
        existing = PersistedTopic(
            id=existing_id,
            title="AI Trends",
            description="About AI",
            source="reddit",
            external_url="",
            trend_score=70,
            velocity=5,
            domain="tech",
            discovered_at=datetime.now(UTC),
            composite_score=70,
            rank=1,
            source_count=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([existing], 1)
        embedding = MagicMock()
        # Return similar embeddings (cosine sim ~1.0)
        embedding.embed.return_value = [[1.0, 0.0, 0.0]]

        svc = TopicPersistenceService(
            repo=repo,
            embedding_service=embedding,
            threshold=0.85,
        )
        result = await svc.persist_ranked_topics(
            [_make_ranked("AI Trends 2026", 85)],
            "tech",
        )
        assert result.new_count == 0
        assert result.updated_count == 1
        repo.update_from_scan.assert_called_once()

    @pytest.mark.asyncio
    async def test_mixed_new_and_updated(self) -> None:
        from src.api.schemas.topics import PersistedTopic

        existing = PersistedTopic(
            id=uuid4(),
            title="Existing Topic",
            description="",
            source="reddit",
            external_url="",
            trend_score=60,
            velocity=0,
            domain="tech",
            discovered_at=datetime.now(UTC),
            composite_score=60,
            rank=1,
            source_count=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([existing], 1)
        repo.create_from_ranked.return_value = "new-id"
        embedding = MagicMock()
        # First call: embed new topics (2 topics)
        # Second call: embed existing topics (1 topic)
        # Similar for first, different for second
        embedding.embed.side_effect = [
            [[1.0, 0.0], [0.0, 1.0]],  # new topics
            [[1.0, 0.0]],  # existing topics
        ]

        svc = TopicPersistenceService(
            repo=repo,
            embedding_service=embedding,
            threshold=0.85,
        )
        result = await svc.persist_ranked_topics(
            [
                _make_ranked("Existing Topic Refreshed", 70),
                _make_ranked("Brand New Topic", 50),
            ],
            "tech",
        )
        assert result.new_count == 1
        assert result.updated_count == 1

    @pytest.mark.asyncio
    async def test_empty_input(self) -> None:
        repo = AsyncMock()
        embedding = MagicMock()
        svc = TopicPersistenceService(
            repo=repo,
            embedding_service=embedding,
            threshold=0.85,
        )
        result = await svc.persist_ranked_topics([], "tech")
        assert result.new_count == 0
        assert result.updated_count == 0
        assert result.total_persisted == 0
