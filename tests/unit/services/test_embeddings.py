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


# ---------------------------------------------------------------------------
# INFRA-008 — background warm-up + try_embed
# ---------------------------------------------------------------------------
import threading  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import numpy as np  # noqa: E402
import structlog.testing  # noqa: E402


def _service_with_fake_loader(
    gate: threading.Event | None = None,
) -> EmbeddingService:
    """EmbeddingService whose loader never touches sentence-transformers."""
    svc = EmbeddingService(model_name="fake-model")

    def fake_load() -> None:
        if gate is not None:
            gate.wait(timeout=5)
        model = MagicMock()
        model.encode.return_value = np.array([[0.1, 0.2]])
        svc._model = model

    svc._load_model = fake_load  # type: ignore[method-assign]
    return svc


class TestEmbeddingWarmUp:
    def test_not_ready_and_not_warming_at_init(self) -> None:
        svc = EmbeddingService(model_name="fake-model")
        assert svc.is_ready is False
        assert svc.is_warming is False

    def test_try_embed_returns_none_while_warming(self) -> None:
        gate = threading.Event()
        svc = _service_with_fake_loader(gate)
        thread = svc.warm_up_in_background()
        assert thread is not None
        assert svc.is_warming is True
        assert svc.try_embed(["x"]) is None
        gate.set()
        thread.join(timeout=5)
        assert svc.is_ready is True
        assert svc.is_warming is False
        assert svc.try_embed(["x"]) == [[0.1, 0.2]]

    def test_try_embed_loads_synchronously_when_no_warmup(self) -> None:
        # Worker path: nobody called warm_up_in_background → same as embed().
        svc = _service_with_fake_loader()
        assert svc.try_embed(["x"]) == [[0.1, 0.2]]
        assert svc.is_ready is True

    def test_warm_up_is_idempotent(self) -> None:
        gate = threading.Event()
        svc = _service_with_fake_loader(gate)
        first = svc.warm_up_in_background()
        second = svc.warm_up_in_background()
        assert first is second
        gate.set()
        assert first is not None
        first.join(timeout=5)
        assert svc.warm_up_in_background() is None

    def test_warm_up_failure_is_logged_not_raised(self) -> None:
        svc = EmbeddingService(model_name="fake-model")

        def boom() -> None:
            raise RuntimeError("no network")

        svc._load_model = boom  # type: ignore[method-assign]
        with structlog.testing.capture_logs() as logs:
            thread = svc.warm_up_in_background()
            assert thread is not None
            thread.join(timeout=5)
        assert any(log["event"] == "embedding_warmup_failed" for log in logs)
        assert svc.is_ready is False
        assert svc.is_warming is False

    def test_load_model_is_noop_when_already_loaded(self) -> None:
        svc = EmbeddingService(model_name="fake-model")
        sentinel = MagicMock()
        svc._model = sentinel
        svc._load_model()  # must not import sentence_transformers
        assert svc._model is sentinel
