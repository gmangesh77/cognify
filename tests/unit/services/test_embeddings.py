from src.services.embeddings import EmbeddingService


class TestEmbeddingService:
    def test_cosine_similarity_identical_vectors(self) -> None:
        svc = EmbeddingService.__new__(EmbeddingService)
        vecs = [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        matrix = svc.cosine_similarity_matrix(vecs)
        assert abs(matrix[0][1] - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal_vectors(self) -> None:
        svc = EmbeddingService.__new__(EmbeddingService)
        vecs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        matrix = svc.cosine_similarity_matrix(vecs)
        assert abs(matrix[0][1]) < 1e-6

    def test_cosine_similarity_matrix_shape(self) -> None:
        svc = EmbeddingService.__new__(EmbeddingService)
        vecs = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        matrix = svc.cosine_similarity_matrix(vecs)
        assert len(matrix) == 3
        assert len(matrix[0]) == 3

    def test_lazy_load_model_not_loaded_at_init(self) -> None:
        svc = EmbeddingService(model_name="all-MiniLM-L6-v2")
        assert svc._model is None
