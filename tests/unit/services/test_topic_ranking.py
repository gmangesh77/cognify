from datetime import UTC, datetime

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
