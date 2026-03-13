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


class TestWeightValidation:
    def test_valid_weights_accepted(self) -> None:
        svc = _make_service()  # defaults sum to 1.0
        assert svc is not None

    def test_invalid_weights_raise_error(self) -> None:
        settings = Settings(
            relevance_weight=0.5,
            recency_weight=0.5,
            velocity_weight=0.5,
            diversity_weight=0.5,
        )
        with pytest.raises(ValueError, match="must sum to 1.0"):
            _make_service(settings=settings)


class TestDomainFiltering:
    def test_matching_topics_pass(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(title="cybersecurity breach"),
            _make_topic(title="cooking recipes"),
        ]
        result = svc.filter_by_domain(topics, "cyber", ["cybersecurity"])
        assert len(result) == 1
        assert result[0].title == "cybersecurity breach"

    def test_empty_keywords_passes_all(self) -> None:
        svc = _make_service()
        topics = [_make_topic(), _make_topic()]
        result = svc.filter_by_domain(topics, "cyber", [])
        assert len(result) == 2

    def test_matches_in_description(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="Big news",
                description="A cybersecurity vulnerability",
            ),
        ]
        result = svc.filter_by_domain(topics, "cyber", ["cybersecurity"])
        assert len(result) == 1

    def test_matches_in_domain_keywords(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="Generic",
                domain_keywords=["cybersecurity"],
            ),
        ]
        result = svc.filter_by_domain(topics, "cyber", ["cybersecurity"])
        assert len(result) == 1

    def test_case_insensitive(self) -> None:
        svc = _make_service()
        topics = [_make_topic(title="CyberSecurity Breach")]
        result = svc.filter_by_domain(topics, "cyber", ["cybersecurity"])
        assert len(result) == 1


class TestDeduplication:
    def test_duplicates_removed(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="duplicate-A first",
                source="reddit",
                trend_score=80,
            ),
            _make_topic(
                title="duplicate-A second",
                source="hackernews",
                trend_score=60,
            ),
            _make_topic(title="unique topic", source="reddit"),
        ]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 2
        titles = [t.title for t in deduped]
        assert "duplicate-A first" in titles
        assert "duplicate-A second" not in titles

    def test_source_count_aggregated(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="duplicate-A v1",
                source="reddit",
                trend_score=90,
            ),
            _make_topic(
                title="duplicate-A v2",
                source="hackernews",
                trend_score=50,
            ),
        ]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 1
        assert counts[deduped[0].title] == 2

    def test_duplicate_info_populated(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="duplicate-A winner",
                source="reddit",
                trend_score=90,
            ),
            _make_topic(
                title="duplicate-A loser",
                source="hackernews",
                trend_score=50,
            ),
        ]
        _, _, dups = svc.deduplicate(topics)
        assert len(dups) == 1
        assert dups[0].title == "duplicate-A loser"
        assert dups[0].duplicate_of == "duplicate-A winner"
        assert dups[0].similarity == pytest.approx(1.0)

    def test_all_topics_are_duplicates(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="duplicate-A from reddit",
                source="reddit",
                trend_score=80,
            ),
            _make_topic(
                title="duplicate-A from hackernews",
                source="hackernews",
                trend_score=60,
            ),
            _make_topic(
                title="duplicate-A from google",
                source="google_trends",
                trend_score=40,
            ),
        ]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 1
        assert counts[deduped[0].title] == 3
        assert len(dups) == 2

    def test_no_duplicates_all_survive(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(title="unique one"),
            _make_topic(title="unique two"),
        ]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 2
        assert len(dups) == 0

    def test_single_topic(self) -> None:
        svc = _make_service()
        topics = [_make_topic(title="only one")]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 1
        assert counts[deduped[0].title] == 1
