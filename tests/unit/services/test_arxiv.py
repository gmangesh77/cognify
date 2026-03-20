from datetime import UTC, datetime

from src.api.schemas.topics import RawTopic
from src.services.arxiv import ArxivService
from src.services.trends.arxiv_client import ArxivPaper
from tests.unit.services.conftest import MockArxivClient


def _paper(**overrides: object) -> ArxivPaper:
    base: ArxivPaper = {
        "arxiv_id": "2603.12345v1",
        "title": "Adversarial Attacks on Neural Networks",
        "abstract": "We study adversarial attacks on deep neural nets.",
        "authors": ["Alice Smith", "Bob Jones"],
        "published": "2026-03-15T12:00:00Z",
        "updated": "2026-03-15T12:00:00Z",
        "pdf_url": "http://arxiv.org/pdf/2603.12345v1",
        "abs_url": "http://arxiv.org/abs/2603.12345v1",
        "primary_category": "cs.CR",
        "categories": ["cs.CR", "cs.AI"],
    }
    result: dict[str, object] = {**base, **overrides}
    return result  # type: ignore[return-value]


class TestScoreCalculation:
    def test_fresh_paper_high_score(self) -> None:
        score = ArxivService.calculate_score(0.0, 2, 200)
        assert score > 70.0

    def test_week_old_paper_moderate(self) -> None:
        score = ArxivService.calculate_score(7.0, 2, 200)
        assert 30.0 < score < 70.0

    def test_old_paper_low_score(self) -> None:
        score = ArxivService.calculate_score(30.0, 1, 50)
        assert score < 25.0

    def test_many_categories_boosts_score(self) -> None:
        score_1 = ArxivService.calculate_score(1.0, 1, 200)
        score_4 = ArxivService.calculate_score(1.0, 4, 200)
        assert score_4 > score_1

    def test_longer_abstract_boosts_score(self) -> None:
        score_short = ArxivService.calculate_score(1.0, 2, 50)
        score_long = ArxivService.calculate_score(1.0, 2, 500)
        assert score_long > score_short

    def test_score_capped_at_100(self) -> None:
        score = ArxivService.calculate_score(0.0, 10, 1500)
        assert score <= 100.0

    def test_category_contribution_capped(self) -> None:
        score_4 = ArxivService.calculate_score(0.0, 4, 200)
        score_8 = ArxivService.calculate_score(0.0, 8, 200)
        assert score_4 == score_8

    def test_abstract_contribution_capped(self) -> None:
        score_1k = ArxivService.calculate_score(0.0, 2, 1000)
        score_2k = ArxivService.calculate_score(0.0, 2, 2000)
        assert score_1k == score_2k


class TestVelocityCalculation:
    def test_fresh_paper(self) -> None:
        vel = ArxivService.calculate_velocity(0.5)
        assert vel == 1.0

    def test_one_day_old(self) -> None:
        vel = ArxivService.calculate_velocity(1.0)
        assert vel == 1.0

    def test_seven_days_old(self) -> None:
        vel = ArxivService.calculate_velocity(7.0)
        assert round(vel, 4) == round(1.0 / 7.0, 4)


class TestDomainFiltering:
    def test_matches_title(self) -> None:
        paper = _paper(title="Cybersecurity attack model")
        matched = ArxivService.filter_by_domain(
            [paper],
            ["cyber"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["cyber"]

    def test_matches_abstract(self) -> None:
        paper = _paper(
            title="Normal title",
            abstract="A study on cybersecurity threats.",
        )
        matched = ArxivService.filter_by_domain(
            [paper],
            ["cyber"],
        )
        assert len(matched) == 1

    def test_matches_categories(self) -> None:
        paper = _paper(
            title="Normal",
            abstract="Normal",
            categories=["cs.CR"],
        )
        matched = ArxivService.filter_by_domain(
            [paper],
            ["cs.CR"],
        )
        assert len(matched) == 1

    def test_matches_author(self) -> None:
        paper = _paper(
            title="Normal",
            abstract="Normal",
            authors=["Cyber Expert"],
        )
        matched = ArxivService.filter_by_domain(
            [paper],
            ["cyber"],
        )
        assert len(matched) == 1

    def test_case_insensitive(self) -> None:
        paper = _paper(title="CYBERSECURITY Analysis")
        matched = ArxivService.filter_by_domain(
            [paper],
            ["cyber"],
        )
        assert len(matched) == 1

    def test_no_match_excluded(self) -> None:
        paper = _paper(title="Cooking with AI")
        matched = ArxivService.filter_by_domain(
            [paper],
            ["cyber"],
        )
        assert len(matched) == 0

    def test_multiple_keywords(self) -> None:
        paper = _paper(title="New AI model for attacks")
        matched = ArxivService.filter_by_domain(
            [paper],
            ["cyber", "AI"],
        )
        assert len(matched) == 1
        assert matched[0][1] == ["AI"]


class TestTopicMapping:
    def test_full_mapping(self) -> None:
        paper = _paper(
            title="Cyber Alert Paper",
            abstract="A major finding about threats.",
            abs_url="http://arxiv.org/abs/2603.99999v1",
        )
        topic = ArxivService.map_to_raw_topic(
            paper,
            score=75.0,
            velocity=0.5,
            matched_keywords=["cyber"],
        )
        assert topic.title == "Cyber Alert Paper"
        assert topic.source == "arxiv"
        assert topic.external_url == "http://arxiv.org/abs/2603.99999v1"
        assert topic.trend_score == 75.0
        assert topic.velocity == 0.5
        assert topic.domain_keywords == ["cyber"]

    def test_long_abstract_truncated(self) -> None:
        paper = _paper(abstract="x" * 500)
        topic = ArxivService.map_to_raw_topic(
            paper,
            50.0,
            0.5,
            ["test"],
        )
        assert len(topic.description) == 200


class TestDeduplication:
    def test_duplicate_ids_keep_higher_score(self) -> None:
        t1 = RawTopic(
            title="Paper A",
            source="arxiv",
            external_url="http://arxiv.org/abs/2603.11111v1",
            trend_score=30.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="Paper A (v2)",
            source="arxiv",
            external_url="http://arxiv.org/abs/2603.11111v1",
            trend_score=70.0,
            discovered_at=datetime.now(UTC),
        )
        result = ArxivService._deduplicate([t1, t2])
        assert len(result) == 1
        assert result[0].trend_score == 70.0

    def test_different_ids_kept(self) -> None:
        t1 = RawTopic(
            title="Paper A",
            source="arxiv",
            external_url="http://arxiv.org/abs/2603.11111v1",
            trend_score=50.0,
            discovered_at=datetime.now(UTC),
        )
        t2 = RawTopic(
            title="Paper B",
            source="arxiv",
            external_url="http://arxiv.org/abs/2603.22222v1",
            trend_score=60.0,
            discovered_at=datetime.now(UTC),
        )
        result = ArxivService._deduplicate([t1, t2])
        assert len(result) == 2

    def test_empty_input(self) -> None:
        result = ArxivService._deduplicate([])
        assert result == []


class TestFetchAndNormalize:
    async def test_full_pipeline(self) -> None:
        papers: list[ArxivPaper] = [
            _paper(
                title="Cybersecurity attack model",
                arxiv_id="2603.11111v1",
                abs_url="http://arxiv.org/abs/2603.11111v1",
            ),
            _paper(
                title="Cooking with algorithms",
                arxiv_id="2603.22222v1",
                abs_url="http://arxiv.org/abs/2603.22222v1",
            ),
        ]
        mock_client = MockArxivClient(papers=papers)
        service = ArxivService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            categories=["cs.CR"],
            max_results=30,
        )
        assert result.total_fetched == 2
        assert result.total_after_filter == 1
        assert len(result.topics) == 1
        assert result.topics[0].title == "Cybersecurity attack model"

    async def test_empty_papers(self) -> None:
        mock_client = MockArxivClient(papers=[])
        service = ArxivService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            categories=["cs.CR"],
            max_results=30,
        )
        assert result.total_fetched == 0
        assert result.total_after_filter == 0
        assert result.topics == []

    async def test_no_matches(self) -> None:
        papers = [_paper(title="Cooking blog paper")]
        mock_client = MockArxivClient(papers=papers)
        service = ArxivService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            categories=["cs.CR"],
            max_results=30,
        )
        assert result.total_fetched == 1
        assert result.total_after_filter == 0

    async def test_max_results_caps_fetch(self) -> None:
        papers = [
            _paper(
                title=f"Cyber paper {i}",
                arxiv_id=f"2603.{i:05d}v1",
                abs_url=f"http://arxiv.org/abs/2603.{i:05d}v1",
            )
            for i in range(10)
        ]
        mock_client = MockArxivClient(papers=papers)
        service = ArxivService(client=mock_client)
        result = await service.fetch_and_normalize(
            domain_keywords=["cyber"],
            categories=["cs.CR"],
            max_results=3,
        )
        assert result.total_fetched == 3
