from datetime import UTC, datetime

from src.services.hackernews import HackerNewsService
from src.services.hackernews_client import HNStoryResponse
from tests.unit.services.conftest import MockHackerNewsClient


def _story(**overrides: object) -> HNStoryResponse:
    base: HNStoryResponse = {
        "objectID": "1",
        "title": "Test Story",
        "url": "https://example.com",
        "points": 100,
        "num_comments": 20,
        "story_text": None,
        "created_at_i": 1710000000,
    }
    result: dict[str, object] = {**base, **overrides}
    return result  # type: ignore[return-value]


class TestScoreNormalization:
    def test_standard_score(self) -> None:
        """50 points, 20 comments, cap 300: (35+6)/300*100 ≈ 13.67"""
        score = HackerNewsService.calculate_score(50, 20, 300.0)
        assert round(score, 2) == 13.67

    def test_high_score_capped_at_100(self) -> None:
        """500 points, 200 comments, cap 300 → exceeds cap → 100"""
        score = HackerNewsService.calculate_score(500, 200, 300.0)
        assert score == 100.0

    def test_zero_points_zero_comments(self) -> None:
        score = HackerNewsService.calculate_score(0, 0, 300.0)
        assert score == 0.0

    def test_exact_cap(self) -> None:
        """300 points, 0 comments, cap 300: (210+0)/300*100 = 70"""
        score = HackerNewsService.calculate_score(300, 0, 300.0)
        assert score == 70.0


class TestVelocityCalculation:
    def test_recent_high_points(self) -> None:
        """100 points, 2 hours ago → velocity 50"""
        vel = HackerNewsService.calculate_velocity(100, 2.0)
        assert vel == 50.0

    def test_old_story(self) -> None:
        """100 points, 20 hours ago → velocity 5"""
        vel = HackerNewsService.calculate_velocity(100, 20.0)
        assert vel == 5.0

    def test_very_recent_clamped_to_1h(self) -> None:
        """100 points, 0.1 hours → clamped to 1h → velocity 100"""
        vel = HackerNewsService.calculate_velocity(100, 0.1)
        assert vel == 100.0

    def test_zero_points(self) -> None:
        vel = HackerNewsService.calculate_velocity(0, 5.0)
        assert vel == 0.0


class TestDomainFiltering:
    def test_matches_title(self) -> None:
        story = _story(title="Cybersecurity breach report")
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_matches_url(self) -> None:
        story = _story(
            title="A normal title",
            url="https://cybernews.com/article",
        )
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 1

    def test_case_insensitive(self) -> None:
        story = _story(title="CYBERSECURITY NEWS")
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        story = _story(title="Cooking recipes")
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 0

    def test_multiple_keywords_any_match(self) -> None:
        story = _story(title="New AI model released")
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber", "AI"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]

    def test_none_url_handled(self) -> None:
        story = _story(title="Cyber topic", url=None)
        matched = HackerNewsService.filter_by_domain(
            [story], ["cyber"],
        )
        assert len(matched) == 1


class TestStoryMapping:
    def test_full_mapping(self) -> None:
        story = _story(
            objectID="42",
            title="Cyber Attack Analysis",
            url="https://example.com/cyber",
            points=150,
            num_comments=40,
            story_text="Detailed analysis of attack.",
            created_at_i=1710000000,
        )
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["cyber"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.title == "Cyber Attack Analysis"
        assert topic.source == "hackernews"
        assert topic.external_url == "https://example.com/cyber"
        assert topic.domain_keywords == ["cyber"]
        assert topic.description == "Detailed analysis of attack."
        assert 0 <= topic.trend_score <= 100
        assert topic.velocity > 0

    def test_missing_url_uses_hn_link(self) -> None:
        story = _story(objectID="99", url=None)
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["test"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert "news.ycombinator.com/item?id=99" in topic.external_url

    def test_missing_story_text_empty_description(self) -> None:
        story = _story(story_text=None)
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["test"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.description == ""

    def test_long_story_text_truncated(self) -> None:
        story = _story(story_text="x" * 500)
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["test"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert len(topic.description) == 200

    def test_none_points_treated_as_zero(self) -> None:
        story = _story(points=None, num_comments=None)
        topic = HackerNewsService.map_to_raw_topic(
            story,
            matched_keywords=["test"],
            points_cap=300.0,
            now=datetime(2024, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert topic.trend_score == 0.0
        assert topic.velocity == 0.0


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        stories: list[HNStoryResponse] = [
            _story(
                objectID="1",
                title="Cybersecurity breach",
                points=200,
                num_comments=50,
            ),
            _story(
                objectID="2",
                title="Cooking recipes",
                points=300,
                num_comments=100,
            ),
        ]
        mock_client = MockHackerNewsClient(stories=stories)
        service = HackerNewsService(
            client=mock_client,
            points_cap=300.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            max_results=30,
            min_points=10,
        )
        assert result.total_fetched == 2
        assert result.total_after_filter == 1
        assert len(result.topics) == 1
        assert result.topics[0].title == "Cybersecurity breach"

    async def test_empty_stories(self) -> None:
        mock_client = MockHackerNewsClient(stories=[])
        service = HackerNewsService(
            client=mock_client,
            points_cap=300.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            max_results=30,
            min_points=10,
        )
        assert result.total_fetched == 0
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_no_matches_after_filter(self) -> None:
        stories = [_story(title="Cooking blog")]
        mock_client = MockHackerNewsClient(stories=stories)
        service = HackerNewsService(
            client=mock_client,
            points_cap=300.0,
        )
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            max_results=30,
            min_points=10,
        )
        assert result.total_fetched == 1
        assert result.total_after_filter == 0
