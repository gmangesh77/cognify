from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.api.schemas.topics import (
    DuplicateInfo,
    RankedTopic,
    RankTopicsRequest,
    RankTopicsResponse,
    RawTopic,
)


def _raw_topic(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Test Topic",
        "source": "hackernews",
        "trend_score": 75.0,
        "discovered_at": datetime.now(UTC).isoformat(),
    }
    base.update(overrides)
    return base


class TestRawTopic:
    def test_valid_topic(self) -> None:
        t = RawTopic(**_raw_topic())
        assert t.title == "Test Topic"
        assert t.velocity == 0
        assert t.domain_keywords == []

    def test_trend_score_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            RawTopic(**_raw_topic(trend_score=101))

    def test_negative_velocity(self) -> None:
        with pytest.raises(ValidationError):
            RawTopic(**_raw_topic(velocity=-1))


class TestRankTopicsRequest:
    def test_empty_topics_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankTopicsRequest(topics=[], domain="test")

    def test_over_500_topics_rejected(self) -> None:
        topics = [_raw_topic(title=f"Topic {i}") for i in range(501)]
        with pytest.raises(ValidationError):
            RankTopicsRequest(
                topics=topics,  # type: ignore[arg-type]
                domain="test",
            )

    def test_default_top_n(self) -> None:
        req = RankTopicsRequest(
            topics=[RawTopic(**_raw_topic())],
            domain="test",
        )
        assert req.top_n == 10


class TestRankedTopic:
    def test_includes_composite_score(self) -> None:
        t = RankedTopic(
            **_raw_topic(),
            composite_score=85.5,
            rank=1,
            source_count=2,
        )
        assert t.composite_score == 85.5
        assert t.rank == 1


class TestDuplicateInfo:
    def test_fields(self) -> None:
        d = DuplicateInfo(
            title="Dup",
            source="reddit",
            duplicate_of="Original",
            similarity=0.92,
        )
        assert d.duplicate_of == "Original"


class TestRankTopicsRequestBoundary:
    def test_top_n_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankTopicsRequest(
                topics=[RawTopic(**_raw_topic())],
                domain="test",
                top_n=0,
            )

    def test_top_n_over_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankTopicsRequest(
                topics=[RawTopic(**_raw_topic())],
                domain="test",
                top_n=101,
            )


class TestRankTopicsResponse:
    def test_response_shape(self) -> None:
        resp = RankTopicsResponse(
            ranked_topics=[],
            duplicates_removed=[],
            total_input=0,
            total_after_dedup=0,
            total_returned=0,
        )
        assert resp.total_input == 0
