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


class TestCrosspostDedup:
    def test_crosspost_parent_groups(self) -> None:
        """Posts with same crosspost_parent merged, highest score kept."""
        posts = [
            _post(id="1", title="Post A", score=50, crosspost_parent="parent_1", subreddit="sub1"),
            _post(id="2", title="Post A copy", score=200, crosspost_parent="parent_1", subreddit="sub2"),
            _post(id="3", title="Unique post", score=100, crosspost_parent=None, subreddit="sub1"),
        ]
        deduped, count = RedditService.deduplicate_crossposts(posts)
        assert len(deduped) == 2
        # The parent_1 group kept highest score (200)
        parent_group = [p for p in deduped if p["crosspost_parent"] == "parent_1"]
        assert len(parent_group) == 1
        assert parent_group[0]["score"] == 200

    def test_fuzzy_title_groups(self) -> None:
        """Posts with very similar titles (>0.85 ratio) merged."""
        posts = [
            _post(id="1", title="Breaking: Major cybersecurity breach at Company X", score=300, subreddit="sub1"),
            _post(id="2", title="Breaking: Major cybersecurity breach at Company X!", score=100, subreddit="sub2"),
            _post(id="3", title="Completely different topic", score=50, subreddit="sub1"),
        ]
        deduped, count = RedditService.deduplicate_crossposts(posts)
        assert len(deduped) == 2
        # Similar titles merged, highest score kept
        breach_post = [p for p in deduped if "breach" in p["title"]]
        assert len(breach_post) == 1
        assert breach_post[0]["score"] == 300

    def test_unique_posts_preserved(self) -> None:
        """All unique posts pass through unchanged."""
        posts = [
            _post(id="1", title="Cybersecurity breach investigation report", score=100),
            _post(id="2", title="New Python framework released today", score=200),
            _post(id="3", title="Machine learning advances in healthcare", score=300),
        ]
        deduped, count = RedditService.deduplicate_crossposts(posts)
        assert len(deduped) == 3
        assert count == 0

    def test_empty_input(self) -> None:
        deduped, count = RedditService.deduplicate_crossposts([])
        assert deduped == []
        assert count == 0

    def test_subreddit_count_tracked(self) -> None:
        """Merged groups report correct subreddit count."""
        posts = [
            _post(id="1", title="Same Post", score=50, crosspost_parent="parent_1", subreddit="sub1"),
            _post(id="2", title="Same Post", score=100, crosspost_parent="parent_1", subreddit="sub2"),
            _post(id="3", title="Same Post", score=75, crosspost_parent="parent_1", subreddit="sub3"),
        ]
        deduped, count = RedditService.deduplicate_crossposts(posts)
        assert len(deduped) == 1
        assert count == 2  # 3 posts -> 1 = 2 removed


class TestDomainFiltering:
    def test_matches_title(self) -> None:
        post = _post(title="Cybersecurity breach report")
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_matches_selftext(self) -> None:
        post = _post(
            title="A normal title",
            selftext="Deep dive into cybersecurity trends",
        )
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 1

    def test_matches_subreddit_name(self) -> None:
        post = _post(
            title="A normal title",
            selftext="Normal text",
            subreddit="cybersecurity",
        )
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 1

    def test_case_insensitive(self) -> None:
        post = _post(title="CYBERSECURITY NEWS")
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        post = _post(title="Cooking recipes", selftext="Delicious food", subreddit="cooking")
        matched = RedditService.filter_by_domain(
            [post], ["cyber"],
        )
        assert len(matched) == 0

    def test_multiple_keywords_any_match(self) -> None:
        post = _post(title="New AI model released")
        matched = RedditService.filter_by_domain(
            [post], ["cyber", "AI"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]


class TestMapToRawTopic:
    def test_full_mapping(self) -> None:
        post = _post(
            id="abc123",
            title="Cyber Attack Analysis",
            selftext="Detailed analysis of the attack.",
            score=150,
            num_comments=40,
            created_utc=1710000000.0,
            permalink="/r/cybersecurity/comments/abc123/cyber_attack/",
            subreddit="cybersecurity",
        )
        topic = RedditService.map_to_raw_topic(
            post,
            matched_keywords=["cyber"],
            score_cap=1000.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.title == "Cyber Attack Analysis"
        assert topic.source == "reddit"
        assert topic.external_url == "https://www.reddit.com/r/cybersecurity/comments/abc123/cyber_attack/"
        assert topic.domain_keywords == ["cyber"]
        assert topic.description == "Detailed analysis of the attack."
        assert 0 <= topic.trend_score <= 100
        assert topic.velocity > 0

    def test_empty_selftext(self) -> None:
        post = _post(selftext="")
        topic = RedditService.map_to_raw_topic(
            post,
            matched_keywords=["test"],
            score_cap=1000.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.description == ""

    def test_long_selftext_truncated(self) -> None:
        post = _post(selftext="x" * 500)
        topic = RedditService.map_to_raw_topic(
            post,
            matched_keywords=["test"],
            score_cap=1000.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert len(topic.description) == 200

    def test_zero_score_and_comments(self) -> None:
        post = _post(score=0, num_comments=0)
        topic = RedditService.map_to_raw_topic(
            post,
            matched_keywords=["test"],
            score_cap=1000.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.velocity == 0.0
        assert topic.trend_score >= 0  # recency_bonus still contributes


# Pipeline tests use default created_utc timestamps. Since fetch_and_normalize
# calls datetime.now(UTC) internally (no now= override), scores will be based on
# actual wall-clock time. Tests assert on structure and counts rather than exact
# score values.


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        posts: dict[str, list[RedditPostResponse]] = {
            "cybersecurity": [
                _post(id="1", title="Cybersecurity breach", score=200, num_comments=50, subreddit="cybersecurity"),
                _post(id="2", title="Cooking recipes", score=300, num_comments=100, subreddit="cybersecurity"),
            ],
            "netsec": [
                _post(id="3", title="Network security tips", score=150, num_comments=30, subreddit="netsec"),
            ],
        }
        mock_client = MockRedditClient(posts=posts)
        service = RedditService(
            client=mock_client,
            score_cap=1000.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber", "security"],
            subreddits=["cybersecurity", "netsec"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.total_fetched == 3
        assert result.subreddits_scanned == 2
        assert result.total_after_filter >= 1  # at least cyber/security posts match
        assert all(t.source == "reddit" for t in result.topics)

    async def test_empty_results(self) -> None:
        mock_client = MockRedditClient(posts={})
        service = RedditService(
            client=mock_client,
            score_cap=1000.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            subreddits=["empty"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.total_fetched == 0
        assert result.topics == []

    async def test_no_matches_after_filter(self) -> None:
        posts: dict[str, list[RedditPostResponse]] = {
            "cooking": [
                _post(id="1", title="Best recipes", subreddit="cooking"),
            ],
        }
        mock_client = MockRedditClient(posts=posts)
        service = RedditService(
            client=mock_client,
            score_cap=1000.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            subreddits=["cooking"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.total_fetched == 1
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_crosspost_dedup_in_pipeline(self) -> None:
        """Same crosspost_parent across subreddits -> deduped."""
        posts: dict[str, list[RedditPostResponse]] = {
            "cybersecurity": [
                _post(id="1", title="Cyber breach", score=100, crosspost_parent="parent_1", subreddit="cybersecurity"),
            ],
            "netsec": [
                _post(id="2", title="Cyber breach copy", score=200, crosspost_parent="parent_1", subreddit="netsec"),
            ],
        }
        mock_client = MockRedditClient(posts=posts)
        service = RedditService(
            client=mock_client,
            score_cap=1000.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            subreddits=["cybersecurity", "netsec"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.total_fetched == 2
        assert result.total_after_dedup == 1

    async def test_partial_subreddit_failure(self) -> None:
        """One subreddit fails, others still processed."""

        class PartialFailClient(MockRedditClient):
            async def fetch_subreddit_posts(
                self,
                subreddit: str,
                sort: str,
                time_filter: str,
                limit: int,
            ) -> list[RedditPostResponse]:
                if subreddit == "private_sub":
                    raise RedditAPIError("Subreddit is private")
                return await super().fetch_subreddit_posts(
                    subreddit, sort, time_filter, limit,
                )

        posts: dict[str, list[RedditPostResponse]] = {
            "cybersecurity": [
                _post(id="1", title="Cyber news", score=100, subreddit="cybersecurity"),
            ],
        }
        client = PartialFailClient(posts=posts)
        service = RedditService(client=client, score_cap=1000.0)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            subreddits=["cybersecurity", "private_sub"],
            max_results=20,
            sort="hot",
            time_filter="day",
        )
        assert result.subreddits_scanned == 1
        assert result.total_fetched == 1

    async def test_all_subreddits_fail_raises(self) -> None:
        """All subreddits fail -> RedditAPIError raised."""

        class AllFailClient(MockRedditClient):
            async def fetch_subreddit_posts(
                self,
                subreddit: str,
                sort: str,
                time_filter: str,
                limit: int,
            ) -> list[RedditPostResponse]:
                raise RedditAPIError("API down")

        client = AllFailClient(posts={})
        service = RedditService(client=client, score_cap=1000.0)
        with pytest.raises(RedditAPIError, match="All subreddits failed"):
            await service.fetch_and_normalize(
                domain_keywords=["cyber"],
                subreddits=["sub1", "sub2"],
                max_results=20,
                sort="hot",
                time_filter="day",
            )
