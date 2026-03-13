from datetime import UTC, datetime, timedelta

import pytest

from src.api.schemas.topics import RawTopic
from src.config.settings import Settings
from src.services.topic_ranking import TopicRankingService

from .conftest import MockEmbeddingService


def _make_topic(**overrides: object) -> RawTopic:
    defaults: dict[str, object] = {
        "title": "Test Topic",
        "source": "hackernews",
        "trend_score": 50.0,
        "discovered_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return RawTopic(**defaults)  # type: ignore[arg-type]


def _make_service(
    settings: Settings | None = None,
) -> TopicRankingService:
    return TopicRankingService(
        settings=settings or Settings(),
        embedding_service=MockEmbeddingService(),
    )


class TestRelevanceScoring:
    def test_matching_keywords_score_high(self) -> None:
        svc = _make_service()
        score = svc._score_relevance(
            _make_topic(
                title="cybersecurity breach detected",
                domain_keywords=["security"],
            ),
            ["cybersecurity", "breach", "security"],
        )
        assert score > 0

    def test_no_matching_keywords_score_zero(self) -> None:
        svc = _make_service()
        score = svc._score_relevance(
            _make_topic(
                title="cooking recipes for dinner",
                domain_keywords=["food"],
            ),
            ["cybersecurity", "hacking"],
        )
        assert score == 0

    def test_empty_domain_keywords_returns_50(self) -> None:
        svc = _make_service()
        score = svc._score_relevance(
            _make_topic(title="anything"),
            [],
        )
        assert score == 50

    def test_empty_topic_tokens_returns_zero(self) -> None:
        svc = _make_service()
        score = svc._score_relevance(
            _make_topic(title="", description="", domain_keywords=[]),
            ["cybersecurity"],
        )
        assert score == 0


class TestRecencyScoring:
    def test_just_now_scores_100(self) -> None:
        svc = _make_service()
        topic = _make_topic(discovered_at=datetime.now(UTC))
        score = svc._score_recency(topic)
        assert abs(score - 100.0) < 1.0

    def test_24h_ago_scores_about_50(self) -> None:
        svc = _make_service()
        topic = _make_topic(
            discovered_at=datetime.now(UTC) - timedelta(hours=24),
        )
        score = svc._score_recency(topic)
        assert 45 < score < 55

    def test_72h_ago_scores_about_12(self) -> None:
        svc = _make_service()
        topic = _make_topic(
            discovered_at=datetime.now(UTC) - timedelta(hours=72),
        )
        score = svc._score_recency(topic)
        assert 8 < score < 18

    def test_future_discovered_at_clamped_to_100(self) -> None:
        svc = _make_service()
        topic = _make_topic(
            discovered_at=datetime.now(UTC) + timedelta(hours=1),
        )
        score = svc._score_recency(topic)
        assert abs(score - 100.0) < 0.01
