from datetime import UTC, datetime

import pytest

from src.services.reddit import RedditService
from src.services.reddit_client import RedditAPIError, RedditPostResponse
from tests.unit.services.conftest import MockRedditClient


def _post(**overrides: object) -> RedditPostResponse:
    base: RedditPostResponse = {
        "id": "abc123",
        "title": "Test Post",
        "selftext": "Some content",
        "score": 100,
        "num_comments": 50,
        "created_utc": 1710000000.0,
        "url": "https://example.com",
        "permalink": "/r/test/comments/abc123/test_post/",
        "subreddit": "test",
        "upvote_ratio": 0.95,
        "crosspost_parent": None,
    }
    result: dict[str, object] = {**base, **overrides}
    return result  # type: ignore[return-value]


class TestScoreNormalization:
    def test_standard_score(self) -> None:
        """score=200, 100 comments, 2h ago, cap=1000.
        cv=50, rb=100*exp(-ln2/12*2)~89.1, raw=(60+25+17.8)=102.8
        trend=(102.8/1000)*100=10.28"""
        score = RedditService.calculate_score(
            score=200,
            num_comments=100,
            hours_ago=2.0,
            score_cap=1000.0,
        )
        assert round(score, 1) == 10.3

    def test_zero_comments_zero_score(self) -> None:
        """score=0, 0 comments, 1h ago.
        cv=0, rb~94.4, raw=(0+0+18.9)=18.9
        trend=(18.9/1000)*100=1.89"""
        score = RedditService.calculate_score(
            score=0,
            num_comments=0,
            hours_ago=1.0,
            score_cap=1000.0,
        )
        assert round(score, 1) == 1.9

    def test_high_score_capped_at_100(self) -> None:
        """Huge values should cap at 100."""
        score = RedditService.calculate_score(
            score=50000,
            num_comments=10000,
            hours_ago=0.5,
            score_cap=1000.0,
        )
        assert score == 100.0

    def test_very_recent_clamps_comment_velocity(self) -> None:
        """hours_ago < 1 -> clamped to 1 for comment_velocity denominator.
        recency_bonus still differs (uses raw hours_ago), so scores differ slightly."""
        score_recent = RedditService.calculate_score(
            score=100,
            num_comments=200,
            hours_ago=0.1,
            score_cap=1000.0,
        )
        score_1h = RedditService.calculate_score(
            score=100,
            num_comments=200,
            hours_ago=1.0,
            score_cap=1000.0,
        )
        # Both use comment_velocity = 200/1.0 = 200 (clamped),
        # but recency_bonus differs slightly. Scores close but not equal.
        assert abs(score_recent - score_1h) < 1.0
        assert score_recent > score_1h  # more recent -> higher recency_bonus


class TestVelocityCalculation:
    def test_standard_velocity(self) -> None:
        """100 score, 2 hours -> 50"""
        vel = RedditService.calculate_velocity(100, 2.0)
        assert vel == 50.0

    def test_very_recent_clamped_to_1h(self) -> None:
        """100 score, 0.1 hours -> clamped to 1 -> 100"""
        vel = RedditService.calculate_velocity(100, 0.1)
        assert vel == 100.0

    def test_old_post(self) -> None:
        """100 score, 20 hours -> 5"""
        vel = RedditService.calculate_velocity(100, 20.0)
        assert vel == 5.0

    def test_zero_score(self) -> None:
        vel = RedditService.calculate_velocity(0, 5.0)
        assert vel == 0.0
