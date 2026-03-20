from datetime import UTC, datetime

from src.api.schemas.topics import RawTopic
from src.services.newsapi import NewsAPIService
from src.services.trends.newsapi_client import NewsAPIArticle
from tests.unit.services.conftest import MockNewsAPIClient


def _article(**overrides: object) -> NewsAPIArticle:
    base: NewsAPIArticle = {
        "title": "Test Article",
        "description": "A test description.",
        "url": "https://example.com/article",
        "urlToImage": "https://example.com/img.jpg",
        "publishedAt": "2026-03-15T10:00:00Z",
        "source": {"id": "test", "name": "Test Source"},
        "author": "Author",
        "content": "Full content here.",
    }
    result: dict[str, object] = {**base, **overrides}
    return result  # type: ignore[return-value]


class TestScoreCalculation:
    def test_first_position_fresh_article(self) -> None:
        score = NewsAPIService.calculate_score(0, 20, 1.0, 2)
        assert round(score, 1) == 86.7

    def test_middle_position_old_article(self) -> None:
        score = NewsAPIService.calculate_score(10, 20, 12.0, 1)
        assert round(score, 1) == 37.5

    def test_last_position_very_old(self) -> None:
        score = NewsAPIService.calculate_score(19, 20, 48.0, 1)
        assert round(score, 1) == 7.6

    def test_score_capped_at_100(self) -> None:
        score = NewsAPIService.calculate_score(0, 1, 0.0, 10)
        assert score == 100.0

    def test_zero_total_returns_zero(self) -> None:
        score = NewsAPIService.calculate_score(0, 0, 1.0, 1)
        assert score == 0.0

    def test_many_keywords_bonus_capped(self) -> None:
        score_4 = NewsAPIService.calculate_score(5, 10, 6.0, 4)
        score_8 = NewsAPIService.calculate_score(5, 10, 6.0, 8)
        assert score_4 == score_8


class TestVelocityCalculation:
    def test_fresh_article(self) -> None:
        vel = NewsAPIService.calculate_velocity(0.5)
        assert vel == 1.0

    def test_one_hour_old(self) -> None:
        vel = NewsAPIService.calculate_velocity(1.0)
        assert vel == 1.0

    def test_ten_hours_old(self) -> None:
        vel = NewsAPIService.calculate_velocity(10.0)
        assert vel == 0.1

    def test_very_old(self) -> None:
        vel = NewsAPIService.calculate_velocity(100.0)
        assert vel == 0.01


class TestDomainFiltering:
    def test_matches_title(self) -> None:
        article = _article(title="Cybersecurity breach report")
        matched = NewsAPIService.filter_by_domain([article], ["cyber"])
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_matches_description(self) -> None:
        article = _article(title="Normal", description="Cybersecurity trends")
        matched = NewsAPIService.filter_by_domain([article], ["cyber"])
        assert len(matched) == 1

    def test_matches_source_name(self) -> None:
        article = _article(
            title="Normal",
            description="Normal",
            source={"id": "cd", "name": "Cybersecurity Dive"},
        )
        matched = NewsAPIService.filter_by_domain([article], ["cyber"])
        assert len(matched) == 1

    def test_matches_content(self) -> None:
        article = _article(
            title="Normal",
            description="Normal",
            content="Deep dive into cybersecurity",
        )
        matched = NewsAPIService.filter_by_domain([article], ["cyber"])
        assert len(matched) == 1

    def test_case_insensitive(self) -> None:
        article = _article(title="CYBERSECURITY NEWS")
        matched = NewsAPIService.filter_by_domain([article], ["cyber"])
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        article = _article(title="Cooking recipes")
        matched = NewsAPIService.filter_by_domain([article], ["cyber"])
        assert len(matched) == 0

    def test_multiple_keywords(self) -> None:
        article = _article(title="New AI model released")
        matched = NewsAPIService.filter_by_domain([article], ["cyber", "AI"])
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]

    def test_none_description_handled(self) -> None:
        article = _article(title="Cyber topic", description=None)
        matched = NewsAPIService.filter_by_domain([article], ["cyber"])
        assert len(matched) == 1

    def test_none_content_handled(self) -> None:
        article = _article(title="Cyber topic", content=None)
        matched = NewsAPIService.filter_by_domain([article], ["cyber"])
        assert len(matched) == 1


class TestTopicMapping:
    def test_full_mapping(self) -> None:
        article = _article(
            title="Cyber Alert",
            description="A major breach.",
            url="https://example.com/cyber",
        )
        topic = NewsAPIService.map_to_raw_topic(
            article,
            score=75.0,
            velocity=0.5,
            matched_keywords=["cyber"],
        )
        assert topic.title == "Cyber Alert"
        assert topic.source == "newsapi"
        assert topic.external_url == "https://example.com/cyber"
        assert topic.trend_score == 75.0
        assert topic.velocity == 0.5
        assert topic.domain_keywords == ["cyber"]
        assert topic.description == "A major breach."

    def test_none_description_empty_string(self) -> None:
        article = _article(description=None)
        topic = NewsAPIService.map_to_raw_topic(article, 50.0, 0.5, ["test"])
        assert topic.description == ""

    def test_long_description_truncated(self) -> None:
        article = _article(description="x" * 500)
        topic = NewsAPIService.map_to_raw_topic(article, 50.0, 0.5, ["test"])
        assert len(topic.description) == 200


class TestDeduplication:
    def test_duplicate_urls_keep_higher_score(self) -> None:
        t1 = RawTopic(
            title="Article A",
            source="newsapi",
            external_url="https://example.com/same",
            trend_score=30.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="Article B",
            source="newsapi",
            external_url="https://example.com/same",
            trend_score=70.0,
            discovered_at=datetime.now(UTC),
        )
        result = NewsAPIService._deduplicate([t1, t2])
        assert len(result) == 1
        assert result[0].trend_score == 70.0

    def test_fuzzy_title_dedup(self) -> None:
        t1 = RawTopic(
            title="Major Cybersecurity Breach Hits US Companies",
            source="newsapi",
            external_url="https://a.com/1",
            trend_score=60.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="Major Cybersecurity Breach Hits US Firms",
            source="newsapi",
            external_url="https://b.com/2",
            trend_score=80.0,
            discovered_at=datetime.now(UTC),
        )
        result = NewsAPIService._deduplicate([t1, t2])
        assert len(result) == 1
        assert result[0].trend_score == 80.0

    def test_different_titles_kept(self) -> None:
        t1 = RawTopic(
            title="Cybersecurity breach",
            source="newsapi",
            external_url="https://a.com/1",
            trend_score=50.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="New AI model released",
            source="newsapi",
            external_url="https://b.com/2",
            trend_score=60.0,
            discovered_at=datetime.now(UTC),
        )
        result = NewsAPIService._deduplicate([t1, t2])
        assert len(result) == 2

    def test_empty_input(self) -> None:
        result = NewsAPIService._deduplicate([])
        assert result == []


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        articles: list[NewsAPIArticle] = [
            _article(title="Cybersecurity breach", url="https://a.com/1"),
            _article(title="Cooking recipes", url="https://b.com/2"),
        ]
        mock_client = MockNewsAPIClient(articles=articles)
        service = NewsAPIService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            category="technology",
            country="us",
            max_results=30,
        )
        assert result.total_fetched == 2
        assert result.total_after_filter == 1
        assert len(result.topics) == 1
        assert result.topics[0].title == "Cybersecurity breach"

    async def test_empty_articles(self) -> None:
        mock_client = MockNewsAPIClient(articles=[])
        service = NewsAPIService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            category="technology",
            country="us",
            max_results=30,
        )
        assert result.total_fetched == 0
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_no_matches(self) -> None:
        articles = [_article(title="Cooking blog")]
        mock_client = MockNewsAPIClient(articles=articles)
        service = NewsAPIService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            category="technology",
            country="us",
            max_results=30,
        )
        assert result.total_fetched == 1
        assert result.total_after_filter == 0

    async def test_max_results_caps_fetch(self) -> None:
        articles = [
            _article(
                title=f"Cyber article {i}",
                url=f"https://example.com/{i}",
            )
            for i in range(10)
        ]
        mock_client = MockNewsAPIClient(articles=articles)
        service = NewsAPIService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            category="technology",
            country="us",
            max_results=3,
        )
        assert result.total_fetched == 3
