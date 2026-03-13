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


class TestVelocityScoring:
    def test_highest_velocity_scores_100(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(velocity=10),
            _make_topic(velocity=50),
            _make_topic(velocity=100),
        ]
        scores = svc._score_velocity(topics)
        assert abs(scores[2] - 100.0) < 0.01

    def test_lowest_velocity_scores_0(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(velocity=10),
            _make_topic(velocity=50),
        ]
        scores = svc._score_velocity(topics)
        assert abs(scores[0]) < 0.01

    def test_all_equal_velocity_returns_50(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(velocity=5),
            _make_topic(velocity=5),
        ]
        scores = svc._score_velocity(topics)
        assert all(abs(s - 50.0) < 0.01 for s in scores)

    def test_all_zero_velocity_returns_50(self) -> None:
        svc = _make_service()
        topics = [_make_topic(velocity=0), _make_topic(velocity=0)]
        scores = svc._score_velocity(topics)
        assert all(abs(s - 50.0) < 0.01 for s in scores)

    def test_single_topic_returns_50(self) -> None:
        svc = _make_service()
        scores = svc._score_velocity([_make_topic(velocity=42)])
        assert abs(scores[0] - 50.0) < 0.01


class TestDiversityScoring:
    def test_single_source_scores_33(self) -> None:
        svc = _make_service()
        score = svc._score_diversity(1)
        assert abs(score - 33.0) < 1

    def test_two_sources_scores_66(self) -> None:
        svc = _make_service()
        score = svc._score_diversity(2)
        assert abs(score - 66.0) < 1

    def test_three_or_more_sources_scores_100(self) -> None:
        svc = _make_service()
        assert abs(svc._score_diversity(3) - 100.0) < 1
        assert abs(svc._score_diversity(5) - 100.0) < 1
