import threading
import time
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: Any = None
        self._lock = threading.Lock()
        self._warmup_thread: threading.Thread | None = None

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def is_warming(self) -> bool:
        thread = self._warmup_thread
        return thread is not None and thread.is_alive()

    def _load_model(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            from sentence_transformers import SentenceTransformer

            start = time.monotonic()
            self._model = SentenceTransformer(self._model_name)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "embedding_model_loaded",
                model_name=self._model_name,
                load_duration_ms=round(duration_ms),
            )

    def _warm_up(self) -> None:
        try:
            self._load_model()
        except Exception as exc:  # noqa: BLE001 — warm-up must never take the app down
            logger.warning(
                "embedding_warmup_failed",
                model_name=self._model_name,
                error=str(exc),
            )

    def warm_up_in_background(self) -> threading.Thread | None:
        """INFRA-008: load the model on a daemon thread. Idempotent.

        Returns the running thread, or None when the model is already loaded.
        """
        if self.is_ready:
            return None
        if self.is_warming:
            return self._warmup_thread
        thread = threading.Thread(
            target=self._warm_up, name="embedding-warmup", daemon=True
        )
        self._warmup_thread = thread
        thread.start()
        logger.info("embedding_warmup_started", model_name=self._model_name)
        return thread

    def try_embed(self, texts: list[str]) -> list[list[float]] | None:
        """Embed, or return None while a background warm-up is still running.

        Without an in-flight warm-up this is exactly ``embed()`` (synchronous
        lazy load) so callers that never warm up — the Celery worker — keep
        today's behaviour.
        """
        if not self.is_ready and self.is_warming:
            return None
        return self.embed(texts)

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
