from src.config.settings import Settings


class TestRankingSettings:
    def test_default_weights(self) -> None:
        s = Settings()
        assert s.relevance_weight == 0.4
        assert s.recency_weight == 0.3
        assert s.velocity_weight == 0.2
        assert s.diversity_weight == 0.1

    def test_default_embedding_model(self) -> None:
        s = Settings()
        assert s.embedding_model == "all-MiniLM-L6-v2"

    def test_default_dedup_threshold(self) -> None:
        s = Settings()
        assert s.dedup_similarity_threshold == 0.85


class TestHackerNewsSettings:
    def test_hn_defaults(self) -> None:
        s = Settings()
        assert s.hn_api_base_url == "https://hn.algolia.com/api/v1"
        assert s.hn_default_max_results == 30
        assert s.hn_default_min_points == 10
        assert s.hn_points_cap == 300.0
        assert s.hn_request_timeout == 10.0
