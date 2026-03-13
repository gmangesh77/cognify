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
