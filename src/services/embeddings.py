import time
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: Any = None

    def _load_model(self) -> None:
        from sentence_transformers import SentenceTransformer

        start = time.monotonic()
        self._model = SentenceTransformer(self._model_name)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "embedding_model_loaded",
            model_name=self._model_name,
            load_duration_ms=round(duration_ms),
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._load_model()
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()  # type: ignore[no-any-return]

    def cosine_similarity_matrix(
        self,
        embeddings: list[list[float]],
    ) -> list[list[float]]:
        arr = np.array(embeddings)
        similarity = (arr @ arr.T).tolist()
        return similarity  # type: ignore[no-any-return]
