from src.services.google_trends import GoogleTrendsService
from src.services.google_trends_client import (
    GTRelatedQuery,
    GTTrendingSearch,
)
from tests.unit.services.conftest import MockGoogleTrendsClient


class TestScoreCalculation:
    def test_trending_score_fixed_70(self) -> None:
        score = GoogleTrendsService.calculate_score("trending", 0)
        assert score == 70.0

    def test_rising_100_percent(self) -> None:
        """100% rise -> 50 + (100/100)*10 = 60"""
        score = GoogleTrendsService.calculate_score("rising", 100)
        assert score == 60.0

    def test_rising_500_percent(self) -> None:
        """500% rise -> 50 + (500/100)*10 = 100"""
        score = GoogleTrendsService.calculate_score("rising", 500)
        assert score == 100.0

    def test_rising_breakout_capped(self) -> None:
        """5000 (Breakout) -> min(100, 50 + 500) = 100"""
        score = GoogleTrendsService.calculate_score("rising", 5000)
        assert score == 100.0

    def test_top_direct_mapping(self) -> None:
        score = GoogleTrendsService.calculate_score("top", 80)
        assert score == 80.0

    def test_top_zero(self) -> None:
        score = GoogleTrendsService.calculate_score("top", 0)
        assert score == 0.0


class TestVelocityCalculation:
    def test_trending_velocity(self) -> None:
        vel = GoogleTrendsService.calculate_velocity("trending", 0)
        assert vel == 50.0

    def test_rising_velocity(self) -> None:
        """200% -> min(100, 200/10) = 20"""
        vel = GoogleTrendsService.calculate_velocity("rising", 200)
        assert vel == 20.0

    def test_rising_breakout_velocity_capped(self) -> None:
        """5000 -> min(100, 500) = 100"""
        vel = GoogleTrendsService.calculate_velocity("rising", 5000)
        assert vel == 100.0

    def test_top_velocity(self) -> None:
        vel = GoogleTrendsService.calculate_velocity("top", 80)
        assert vel == 5.0


class TestDomainFiltering:
    def test_matches_title(self) -> None:
        items: list[GTTrendingSearch | GTRelatedQuery] = [
            GTTrendingSearch(title="cybersecurity trends"),
        ]
        matched = GoogleTrendsService.filter_by_domain(
            items,
            ["cyber"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_case_insensitive(self) -> None:
        items: list[GTTrendingSearch | GTRelatedQuery] = [
            GTTrendingSearch(title="AI SECURITY NEWS"),
        ]
        matched = GoogleTrendsService.filter_by_domain(items, ["ai"])
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        items: list[GTTrendingSearch | GTRelatedQuery] = [
            GTTrendingSearch(title="cooking recipes"),
        ]
        matched = GoogleTrendsService.filter_by_domain(
            items,
            ["cyber"],
        )
        assert len(matched) == 0

    def test_multiple_keywords_any_match(self) -> None:
        items: list[GTTrendingSearch | GTRelatedQuery] = [
            GTTrendingSearch(title="New AI model released"),
        ]
        matched = GoogleTrendsService.filter_by_domain(
            items,
            ["cyber", "AI"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]


class TestMapToRawTopic:
    def test_trending_mapping(self) -> None:
        topic = GoogleTrendsService.map_to_raw_topic(
            title="AI security trends",
            query_type="trending",
            value=0,
            matched_keywords=["AI", "security"],
        )
        assert topic.title == "AI security trends"
        assert topic.source == "google_trends"
        assert topic.description == ""
        assert topic.trend_score == 70.0
        assert topic.velocity == 50.0
        assert topic.domain_keywords == ["AI", "security"]
        assert "trends.google.com" in topic.external_url
        assert "AI+security+trends" in topic.external_url

    def test_rising_mapping(self) -> None:
        topic = GoogleTrendsService.map_to_raw_topic(
            title="cyber attack",
            query_type="rising",
            value=300,
            matched_keywords=["cyber"],
        )
        assert topic.trend_score == 80.0
        assert topic.velocity == 30.0

    def test_top_mapping(self) -> None:
        topic = GoogleTrendsService.map_to_raw_topic(
            title="network security",
            query_type="top",
            value=90,
            matched_keywords=["security"],
        )
        assert topic.trend_score == 90.0
        assert topic.velocity == 5.0


class TestDeduplication:
    async def test_higher_score_wins(self) -> None:
        trending: list[GTTrendingSearch] = [
            GTTrendingSearch(title="AI Security"),
        ]
        related: list[GTRelatedQuery] = [
            GTRelatedQuery(
                title="ai security",
                value=500,
                query_type="rising",
                seed_keyword="ai",
            ),
        ]
        mock = MockGoogleTrendsClient(
            trending=trending,
            related=related,
        )
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["ai", "security"],
            country="united_states",
            max_results=30,
        )
        assert len(result.topics) == 1
        # Rising score (100) > trending score (70)
        assert result.topics[0].trend_score == 100.0

    async def test_first_wins_on_equal_score(self) -> None:
        related: list[GTRelatedQuery] = [
            GTRelatedQuery(
                title="AI Security",
                value=80,
                query_type="top",
                seed_keyword="ai",
            ),
            GTRelatedQuery(
                title="ai security",
                value=80,
                query_type="top",
                seed_keyword="security",
            ),
        ]
        mock = MockGoogleTrendsClient(related=related)
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["ai", "security"],
            country="united_states",
            max_results=30,
        )
        assert len(result.topics) == 1


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        trending: list[GTTrendingSearch] = [
            GTTrendingSearch(title="cybersecurity breach"),
            GTTrendingSearch(title="cooking show"),
        ]
        related: list[GTRelatedQuery] = [
            GTRelatedQuery(
                title="cyber attack 2026",
                value=300,
                query_type="rising",
                seed_keyword="cyber",
            ),
        ]
        mock = MockGoogleTrendsClient(
            trending=trending,
            related=related,
        )
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            country="united_states",
            max_results=30,
        )
        assert result.total_trending == 2
        assert result.total_related == 1
        # "cooking show" filtered out
        assert result.total_after_filter == 2
        assert len(result.topics) == 2

    async def test_empty_results(self) -> None:
        mock = MockGoogleTrendsClient()
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            country="united_states",
            max_results=30,
        )
        assert result.total_trending == 0
        assert result.total_related == 0
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_max_results_caps_output(self) -> None:
        trending: list[GTTrendingSearch] = [
            GTTrendingSearch(title=f"cyber topic {i}") for i in range(10)
        ]
        mock = MockGoogleTrendsClient(trending=trending)
        service = GoogleTrendsService(client=mock)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            country="united_states",
            max_results=3,
        )
        assert len(result.topics) == 3
        assert result.total_after_filter == 10
