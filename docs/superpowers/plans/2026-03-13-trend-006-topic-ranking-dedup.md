# TREND-006: Topic Ranking & Deduplication — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stateless topic ranking service with semantic deduplication that accepts raw topics, filters by domain, removes near-duplicates via embedding cosine similarity, computes weighted composite scores, and returns the top N ranked topics.

**Architecture:** Single `TopicRankingService` class with injected `EmbeddingService` (lazy-loaded sentence-transformers model). Exposed via `POST /api/v1/topics/rank`. No database — pure algorithm + API endpoint.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, sentence-transformers (all-MiniLM-L6-v2), numpy, structlog, pytest

**Spec:** [`docs/superpowers/specs/2026-03-13-trend-006-topic-ranking-dedup-design.md`](../specs/2026-03-13-trend-006-topic-ranking-dedup-design.md)

**Test runner:** `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest ...`

---

## Chunk 1: Foundation — Schemas, Settings, Error Class

### Task 1: Add dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [x] **Step 1: Add sentence-transformers and numpy to dependencies**

```toml
# In [project] dependencies, add after "email-validator":
    "sentence-transformers>=3.0.0",
    "numpy>=1.26.0",
```

- [x] **Step 2: Install updated dependencies**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pip install -e ".[dev]"`

- [x] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add sentence-transformers and numpy dependencies"
```

---

### Task 2: Add Settings fields for ranking configuration

**Files:**
- Modify: `src/config/settings.py`
- Test: `tests/unit/api/test_app.py` (existing — verify app still starts)

- [x] **Step 1: Write failing test for new settings fields**

Create `tests/unit/config/__init__.py` (empty file).

Create `tests/unit/config/test_settings.py`:

```python
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/config/test_settings.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'relevance_weight'`

- [x] **Step 3: Add settings fields**

Add to `src/config/settings.py` class `Settings`, after line 18 (`jwt_refresh_token_expire_days`):

```python
    # Topic ranking weights (must sum to 1.0)
    relevance_weight: float = 0.4
    recency_weight: float = 0.3
    velocity_weight: float = 0.2
    diversity_weight: float = 0.1
    # Embedding / dedup
    embedding_model: str = "all-MiniLM-L6-v2"
    dedup_similarity_threshold: float = 0.85
```

- [x] **Step 4: Run test to verify it passes**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/config/test_settings.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/config/settings.py tests/unit/config/test_settings.py
git commit -m "feat: add topic ranking settings (weights, embedding model, dedup threshold)"
```

---

### Task 3: Add ServiceUnavailableError and rename weaviate→milvus in health

**Files:**
- Modify: `src/api/errors.py`
- Modify: `src/api/routers/health.py`
- Test: `tests/unit/api/test_errors.py` (existing)
- Test: `tests/unit/api/test_health.py` (existing)

- [x] **Step 1: Write failing test for ServiceUnavailableError**

Add to `tests/unit/api/test_errors.py`:

```python
from src.api.errors import ServiceUnavailableError


class TestServiceUnavailableError:
    def test_status_code_503(self) -> None:
        err = ServiceUnavailableError(
            message="Model unavailable",
        )
        assert err.status_code == 503
        assert err.code == "service_unavailable"

    def test_custom_code(self) -> None:
        err = ServiceUnavailableError(
            code="embedding_service_unavailable",
            message="Embedding model failed",
        )
        assert err.code == "embedding_service_unavailable"
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_errors.py::TestServiceUnavailableError -v`
Expected: FAIL — `ImportError: cannot import name 'ServiceUnavailableError'`

- [x] **Step 3: Add ServiceUnavailableError to errors.py**

Add to `src/api/errors.py`, after `AuthorizationError` class. Also add `HTTP_503_SERVICE_UNAVAILABLE` to the starlette imports:

```python
# Add to imports at top:
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

# Add after AuthorizationError class:
class ServiceUnavailableError(CognifyError):
    def __init__(
        self,
        code: str = "service_unavailable",
        message: str = "Service temporarily unavailable",
    ) -> None:
        super().__init__(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            code=code,
            message=message,
        )
```

- [x] **Step 4: Run test to verify it passes**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_errors.py -v`
Expected: PASS

- [x] **Step 5: Rename weaviate→milvus in health.py**

In `src/api/routers/health.py` line 16, change:
```python
    weaviate: CheckStatus = "unavailable"
```
to:
```python
    milvus: CheckStatus = "unavailable"
```

- [x] **Step 6: Fix health test for milvus rename**

In `tests/unit/api/test_health.py` line 59, change:
```python
        expected_keys = {"database", "redis", "weaviate", "celery"}
```
to:
```python
        expected_keys = {"database", "redis", "milvus", "celery"}
```

- [x] **Step 7: Run existing health tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_health.py -v`
Expected: PASS

- [x] **Step 8: Commit**

```bash
git add src/api/errors.py src/api/routers/health.py tests/unit/api/test_errors.py tests/unit/api/test_health.py
git commit -m "feat: add ServiceUnavailableError (503), rename weaviate to milvus in health"
```

---

### Task 4: Create Pydantic schemas

**Files:**
- Create: `src/api/schemas/__init__.py`
- Create: `src/api/schemas/topics.py`
- Create: `tests/unit/api/test_topic_schemas.py`

- [x] **Step 1: Write failing tests for schemas**

Create `tests/unit/api/test_topic_schemas.py`:

```python
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.api.schemas.topics import (
    DuplicateInfo,
    RankedTopic,
    RankTopicsRequest,
    RankTopicsResponse,
    RawTopic,
)


def _raw_topic(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Test Topic",
        "source": "hackernews",
        "trend_score": 75.0,
        "discovered_at": datetime.now(UTC).isoformat(),
    }
    base.update(overrides)
    return base


class TestRawTopic:
    def test_valid_topic(self) -> None:
        t = RawTopic(**_raw_topic())
        assert t.title == "Test Topic"
        assert t.velocity == 0
        assert t.domain_keywords == []

    def test_trend_score_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            RawTopic(**_raw_topic(trend_score=101))

    def test_negative_velocity(self) -> None:
        with pytest.raises(ValidationError):
            RawTopic(**_raw_topic(velocity=-1))


class TestRankTopicsRequest:
    def test_empty_topics_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankTopicsRequest(topics=[], domain="test")

    def test_over_500_topics_rejected(self) -> None:
        topics = [_raw_topic(title=f"Topic {i}") for i in range(501)]
        with pytest.raises(ValidationError):
            RankTopicsRequest(
                topics=topics,  # type: ignore[arg-type]
                domain="test",
            )

    def test_default_top_n(self) -> None:
        req = RankTopicsRequest(
            topics=[RawTopic(**_raw_topic())],
            domain="test",
        )
        assert req.top_n == 10


class TestRankedTopic:
    def test_includes_composite_score(self) -> None:
        t = RankedTopic(
            **_raw_topic(),
            composite_score=85.5,
            rank=1,
            source_count=2,
        )
        assert t.composite_score == 85.5
        assert t.rank == 1


class TestDuplicateInfo:
    def test_fields(self) -> None:
        d = DuplicateInfo(
            title="Dup",
            source="reddit",
            duplicate_of="Original",
            similarity=0.92,
        )
        assert d.duplicate_of == "Original"


class TestRankTopicsRequestBoundary:
    def test_top_n_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankTopicsRequest(
                topics=[RawTopic(**_raw_topic())],
                domain="test",
                top_n=0,
            )

    def test_top_n_over_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankTopicsRequest(
                topics=[RawTopic(**_raw_topic())],
                domain="test",
                top_n=101,
            )


class TestRankTopicsResponse:
    def test_response_shape(self) -> None:
        resp = RankTopicsResponse(
            ranked_topics=[],
            duplicates_removed=[],
            total_input=0,
            total_after_dedup=0,
            total_returned=0,
        )
        assert resp.total_input == 0
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_topic_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.schemas'`

- [x] **Step 3: Create schema files**

Create `src/api/schemas/__init__.py`:

```python
from src.api.schemas.topics import (
    DuplicateInfo,
    RankedTopic,
    RankTopicsRequest,
    RankTopicsResponse,
    RawTopic,
)

__all__ = [
    "DuplicateInfo",
    "RankedTopic",
    "RankTopicsRequest",
    "RankTopicsResponse",
    "RawTopic",
]
```

Create `src/api/schemas/topics.py`:

```python
from datetime import datetime

from pydantic import BaseModel, Field


class RawTopic(BaseModel):
    title: str
    description: str = ""
    source: str
    external_url: str = ""
    trend_score: float = Field(ge=0, le=100)
    discovered_at: datetime
    velocity: float = Field(ge=0, default=0)
    domain_keywords: list[str] = Field(default_factory=list)


class RankedTopic(RawTopic):
    composite_score: float
    rank: int
    source_count: int


class DuplicateInfo(BaseModel):
    title: str
    source: str
    duplicate_of: str
    similarity: float


class RankTopicsRequest(BaseModel):
    topics: list[RawTopic] = Field(min_length=1, max_length=500)
    domain: str
    domain_keywords: list[str] = Field(default_factory=list)
    top_n: int = Field(default=10, ge=1, le=100)


class RankTopicsResponse(BaseModel):
    ranked_topics: list[RankedTopic]
    duplicates_removed: list[DuplicateInfo]
    total_input: int
    total_after_dedup: int
    total_returned: int
```

- [x] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_topic_schemas.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/api/schemas/ tests/unit/api/test_topic_schemas.py
git commit -m "feat: add Pydantic schemas for topic ranking (RawTopic, RankedTopic, etc.)"
```

---

## Chunk 2: EmbeddingService

### Task 5: Create EmbeddingService with lazy-loaded model

**Files:**
- Create: `src/services/embeddings.py`
- Create: `tests/unit/services/__init__.py`
- Create: `tests/unit/services/conftest.py`
- Create: `tests/unit/services/test_embeddings.py`

- [x] **Step 1: Write failing tests for EmbeddingService**

Create `tests/unit/services/__init__.py` (empty file).

Create `tests/unit/services/conftest.py`:

```python
import hashlib

from src.services.embeddings import EmbeddingService

VECTOR_DIM = 384


class MockEmbeddingService(EmbeddingService):
    """Deterministic mock: texts with 'duplicate-A' get the same vector,
    texts with 'duplicate-B' get another, all others get unique vectors."""

    def __init__(self) -> None:
        super().__init__(model_name="mock")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            if "duplicate-A" in text:
                vec = [0.0] * VECTOR_DIM
                vec[0] = 1.0
            elif "duplicate-B" in text:
                vec = [0.0] * VECTOR_DIM
                vec[1] = 1.0
            else:
                h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
                idx = h % VECTOR_DIM
                vec = [0.0] * VECTOR_DIM
                vec[idx] = 1.0
            vectors.append(vec)
        return vectors
```

Create `tests/unit/services/test_embeddings.py`:

```python
import numpy as np

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
```

- [x] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_embeddings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.embeddings'`

- [x] **Step 3: Implement EmbeddingService**

Create `src/services/embeddings.py`:

```python
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
```

- [x] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_embeddings.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/services/embeddings.py tests/unit/services/
git commit -m "feat: add EmbeddingService with lazy-loaded sentence-transformers model"
```

---

## Chunk 3: TopicRankingService — Scoring

### Task 6: Implement relevance scoring

**Files:**
- Create: `src/services/topic_ranking.py`
- Create: `tests/unit/services/test_topic_ranking.py`

- [x] **Step 1: Write failing tests for relevance scoring**

Create `tests/unit/services/test_topic_ranking.py`:

```python
from datetime import UTC, datetime

import pytest

from src.api.schemas.topics import RawTopic
from src.config.settings import Settings
from src.services.topic_ranking import TopicRankingService

from .conftest import MockEmbeddingService


def _make_topic(**overrides: object) -> RawTopic:
    defaults: dict[str, object] = {
        "title": "Test Topic",
        "source": "hackernews",
        "trend_score": 50.0,
        "discovered_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return RawTopic(**defaults)  # type: ignore[arg-type]


def _make_service(
    settings: Settings | None = None,
) -> TopicRankingService:
    return TopicRankingService(
        settings=settings or Settings(),
        embedding_service=MockEmbeddingService(),
    )


class TestRelevanceScoring:
    def test_matching_keywords_score_high(self) -> None:
        svc = _make_service()
        score = svc._score_relevance(
            _make_topic(
                title="cybersecurity breach detected",
                domain_keywords=["security"],
            ),
            ["cybersecurity", "breach", "security"],
        )
        assert score > 0

    def test_no_matching_keywords_score_zero(self) -> None:
        svc = _make_service()
        score = svc._score_relevance(
            _make_topic(
                title="cooking recipes for dinner",
                domain_keywords=["food"],
            ),
            ["cybersecurity", "hacking"],
        )
        assert score == 0

    def test_empty_domain_keywords_returns_50(self) -> None:
        svc = _make_service()
        score = svc._score_relevance(
            _make_topic(title="anything"),
            [],
        )
        assert score == 50

    def test_empty_topic_tokens_returns_zero(self) -> None:
        svc = _make_service()
        score = svc._score_relevance(
            _make_topic(title="", description="", domain_keywords=[]),
            ["cybersecurity"],
        )
        assert score == 0
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestRelevanceScoring -v`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Implement TopicRankingService skeleton with relevance scoring**

Create `src/services/topic_ranking.py`:

```python
import math
import time
from datetime import UTC, datetime

import structlog

from src.api.schemas.topics import (
    DuplicateInfo,
    RankedTopic,
    RankTopicsRequest,
    RankTopicsResponse,
    RawTopic,
)
from src.config.settings import Settings
from src.services.embeddings import EmbeddingService

logger = structlog.get_logger()

_NEUTRAL_SCORE = 50.0


class TopicRankingService:
    def __init__(
        self,
        settings: Settings,
        embedding_service: EmbeddingService,
    ) -> None:
        self._settings = settings
        self._embedding = embedding_service
        self._validate_weights()

    def _validate_weights(self) -> None:
        total = (
            self._settings.relevance_weight
            + self._settings.recency_weight
            + self._settings.velocity_weight
            + self._settings.diversity_weight
        )
        if abs(total - 1.0) > 0.001:
            msg = f"Scoring weights must sum to 1.0, got {total}"
            raise ValueError(msg)

    def _score_relevance(
        self,
        topic: RawTopic,
        domain_keywords: list[str],
    ) -> float:
        if not domain_keywords:
            return _NEUTRAL_SCORE

        topic_tokens = set()
        for text in [topic.title, topic.description]:
            topic_tokens.update(text.lower().split())
        for kw in topic.domain_keywords:
            topic_tokens.update(kw.lower().split())

        if not topic_tokens:
            return 0.0

        domain_tokens = {kw.lower() for kw in domain_keywords}
        intersection = topic_tokens & domain_tokens
        union = topic_tokens | domain_tokens

        if not union:
            return 0.0

        return (len(intersection) / len(union)) * 100
```

- [x] **Step 4: Run test to verify it passes**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestRelevanceScoring -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/services/topic_ranking.py tests/unit/services/test_topic_ranking.py
git commit -m "feat: add TopicRankingService skeleton with relevance scoring"
```

---

### Task 7: Implement recency scoring

**Files:**
- Modify: `src/services/topic_ranking.py`
- Modify: `tests/unit/services/test_topic_ranking.py`

- [x] **Step 1: Write failing tests for recency scoring**

Add to `tests/unit/services/test_topic_ranking.py`:

```python
from datetime import timedelta
from freezegun import freeze_time


class TestRecencyScoring:
    def test_just_now_scores_100(self) -> None:
        svc = _make_service()
        topic = _make_topic(discovered_at=datetime.now(UTC))
        score = svc._score_recency(topic)
        assert abs(score - 100.0) < 1.0

    def test_24h_ago_scores_about_50(self) -> None:
        svc = _make_service()
        topic = _make_topic(
            discovered_at=datetime.now(UTC) - timedelta(hours=24),
        )
        score = svc._score_recency(topic)
        assert 45 < score < 55

    def test_72h_ago_scores_about_12(self) -> None:
        svc = _make_service()
        topic = _make_topic(
            discovered_at=datetime.now(UTC) - timedelta(hours=72),
        )
        score = svc._score_recency(topic)
        assert 8 < score < 18

    def test_future_discovered_at_clamped_to_100(self) -> None:
        svc = _make_service()
        topic = _make_topic(
            discovered_at=datetime.now(UTC) + timedelta(hours=1),
        )
        score = svc._score_recency(topic)
        assert abs(score - 100.0) < 0.01
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestRecencyScoring -v`
Expected: FAIL — `AttributeError: '_score_recency'`

- [x] **Step 3: Implement recency scoring**

Add to `TopicRankingService` in `src/services/topic_ranking.py`:

```python
    # λ = ln(2)/24 — 24h gives score of 50
    _RECENCY_LAMBDA = math.log(2) / 24

    def _score_recency(self, topic: RawTopic) -> float:
        now = datetime.now(UTC)
        discovered = topic.discovered_at
        if discovered.tzinfo is None:
            discovered = discovered.replace(tzinfo=UTC)
        else:
            discovered = discovered.astimezone(UTC)
        hours_ago = max((now - discovered).total_seconds() / 3600, 0.0)
        return 100 * math.exp(-self._RECENCY_LAMBDA * hours_ago)
```

- [x] **Step 4: Run test to verify it passes**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestRecencyScoring -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/services/topic_ranking.py tests/unit/services/test_topic_ranking.py
git commit -m "feat: add recency scoring with exponential decay"
```

---

### Task 8: Implement velocity scoring

**Files:**
- Modify: `src/services/topic_ranking.py`
- Modify: `tests/unit/services/test_topic_ranking.py`

- [x] **Step 1: Write failing tests for velocity scoring**

Add to `tests/unit/services/test_topic_ranking.py`:

```python
class TestVelocityScoring:
    def test_highest_velocity_scores_100(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(velocity=10),
            _make_topic(velocity=50),
            _make_topic(velocity=100),
        ]
        scores = svc._score_velocity(topics)
        assert abs(scores[2] - 100.0) < 0.01

    def test_lowest_velocity_scores_0(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(velocity=10),
            _make_topic(velocity=50),
        ]
        scores = svc._score_velocity(topics)
        assert abs(scores[0]) < 0.01

    def test_all_equal_velocity_returns_50(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(velocity=5),
            _make_topic(velocity=5),
        ]
        scores = svc._score_velocity(topics)
        assert all(abs(s - 50.0) < 0.01 for s in scores)

    def test_all_zero_velocity_returns_50(self) -> None:
        svc = _make_service()
        topics = [_make_topic(velocity=0), _make_topic(velocity=0)]
        scores = svc._score_velocity(topics)
        assert all(abs(s - 50.0) < 0.01 for s in scores)

    def test_single_topic_returns_50(self) -> None:
        svc = _make_service()
        scores = svc._score_velocity([_make_topic(velocity=42)])
        assert abs(scores[0] - 50.0) < 0.01
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestVelocityScoring -v`
Expected: FAIL

- [x] **Step 3: Implement velocity scoring**

Add to `TopicRankingService`:

```python
    def _score_velocity(
        self,
        topics: list[RawTopic],
    ) -> list[float]:
        velocities = [t.velocity for t in topics]
        min_v = min(velocities)
        max_v = max(velocities)
        if max_v == min_v:
            return [_NEUTRAL_SCORE] * len(topics)
        return [
            ((v - min_v) / (max_v - min_v)) * 100
            for v in velocities
        ]
```

- [x] **Step 4: Run test to verify it passes**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestVelocityScoring -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/services/topic_ranking.py tests/unit/services/test_topic_ranking.py
git commit -m "feat: add velocity scoring with min-max normalization"
```

---

### Task 9: Implement diversity scoring

**Files:**
- Modify: `src/services/topic_ranking.py`
- Modify: `tests/unit/services/test_topic_ranking.py`

- [x] **Step 1: Write failing tests for diversity scoring**

Add to `tests/unit/services/test_topic_ranking.py`:

```python
class TestDiversityScoring:
    def test_single_source_scores_33(self) -> None:
        svc = _make_service()
        score = svc._score_diversity(1)
        assert abs(score - 33.0) < 1

    def test_two_sources_scores_66(self) -> None:
        svc = _make_service()
        score = svc._score_diversity(2)
        assert abs(score - 66.0) < 1

    def test_three_or_more_sources_scores_100(self) -> None:
        svc = _make_service()
        assert abs(svc._score_diversity(3) - 100.0) < 1
        assert abs(svc._score_diversity(5) - 100.0) < 1
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestDiversityScoring -v`
Expected: FAIL

- [x] **Step 3: Implement diversity scoring**

Add to `TopicRankingService`:

```python
    def _score_diversity(self, source_count: int) -> float:
        if source_count >= 3:
            return 100.0
        if source_count == 2:
            return 66.0
        return 33.0
```

- [x] **Step 4: Run test to verify it passes**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestDiversityScoring -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/services/topic_ranking.py tests/unit/services/test_topic_ranking.py
git commit -m "feat: add source diversity scoring"
```

---

### Task 10: Implement weight validation

**Files:**
- Modify: `tests/unit/services/test_topic_ranking.py`

- [x] **Step 1: Write test for weight validation**

Add to `tests/unit/services/test_topic_ranking.py`:

```python
class TestWeightValidation:
    def test_valid_weights_accepted(self) -> None:
        svc = _make_service()  # defaults sum to 1.0
        assert svc is not None

    def test_invalid_weights_raise_error(self) -> None:
        settings = Settings(
            relevance_weight=0.5,
            recency_weight=0.5,
            velocity_weight=0.5,
            diversity_weight=0.5,
        )
        with pytest.raises(ValueError, match="must sum to 1.0"):
            _make_service(settings=settings)
```

- [x] **Step 2: Run test to verify it passes** (already implemented in Task 6)

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestWeightValidation -v`
Expected: PASS

- [x] **Step 3: Commit**

```bash
git add tests/unit/services/test_topic_ranking.py
git commit -m "test: add weight validation test for TopicRankingService"
```

---

## Chunk 4: TopicRankingService — Filter, Dedup, Orchestration

### Task 11: Implement domain filtering

**Files:**
- Modify: `src/services/topic_ranking.py`
- Modify: `tests/unit/services/test_topic_ranking.py`

- [x] **Step 1: Write failing tests for domain filtering**

Add to `tests/unit/services/test_topic_ranking.py`:

```python
class TestDomainFiltering:
    def test_matching_topics_pass(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(title="cybersecurity breach"),
            _make_topic(title="cooking recipes"),
        ]
        result = svc.filter_by_domain(topics, "cyber", ["cybersecurity"])
        assert len(result) == 1
        assert result[0].title == "cybersecurity breach"

    def test_empty_keywords_passes_all(self) -> None:
        svc = _make_service()
        topics = [_make_topic(), _make_topic()]
        result = svc.filter_by_domain(topics, "cyber", [])
        assert len(result) == 2

    def test_matches_in_description(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="Big news",
                description="A cybersecurity vulnerability",
            ),
        ]
        result = svc.filter_by_domain(topics, "cyber", ["cybersecurity"])
        assert len(result) == 1

    def test_matches_in_domain_keywords(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="Generic",
                domain_keywords=["cybersecurity"],
            ),
        ]
        result = svc.filter_by_domain(topics, "cyber", ["cybersecurity"])
        assert len(result) == 1

    def test_case_insensitive(self) -> None:
        svc = _make_service()
        topics = [_make_topic(title="CyberSecurity Breach")]
        result = svc.filter_by_domain(topics, "cyber", ["cybersecurity"])
        assert len(result) == 1
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestDomainFiltering -v`
Expected: FAIL

- [x] **Step 3: Implement filter_by_domain**

Add to `TopicRankingService`:

```python
    def filter_by_domain(
        self,
        topics: list[RawTopic],
        domain: str,
        domain_keywords: list[str],
    ) -> list[RawTopic]:
        if not domain_keywords:
            return list(topics)

        kw_set = {kw.lower() for kw in domain_keywords}
        result: list[RawTopic] = []
        for topic in topics:
            tokens = set()
            for text in [topic.title, topic.description]:
                tokens.update(text.lower().split())
            for tag in topic.domain_keywords:
                tokens.update(tag.lower().split())
            if tokens & kw_set:
                result.append(topic)

        logger.debug(
            "topics_filtered",
            before_count=len(topics),
            after_count=len(result),
            domain=domain,
        )
        return result
```

- [x] **Step 4: Run test to verify it passes**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestDomainFiltering -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/services/topic_ranking.py tests/unit/services/test_topic_ranking.py
git commit -m "feat: add domain keyword filtering"
```

---

### Task 12: Implement semantic deduplication

**Files:**
- Modify: `src/services/topic_ranking.py`
- Modify: `tests/unit/services/test_topic_ranking.py`

- [x] **Step 1: Write failing tests for deduplication**

Add to `tests/unit/services/test_topic_ranking.py`:

```python
class TestDeduplication:
    def test_duplicates_removed(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="duplicate-A first",
                source="reddit",
                trend_score=80,
            ),
            _make_topic(
                title="duplicate-A second",
                source="hackernews",
                trend_score=60,
            ),
            _make_topic(title="unique topic", source="reddit"),
        ]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 2
        # Higher trend_score survives
        titles = [t.title for t in deduped]
        assert "duplicate-A first" in titles
        assert "duplicate-A second" not in titles

    def test_source_count_aggregated(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="duplicate-A v1",
                source="reddit",
                trend_score=90,
            ),
            _make_topic(
                title="duplicate-A v2",
                source="hackernews",
                trend_score=50,
            ),
        ]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 1
        assert counts[deduped[0].title] == 2

    def test_duplicate_info_populated(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="duplicate-A winner",
                source="reddit",
                trend_score=90,
            ),
            _make_topic(
                title="duplicate-A loser",
                source="hackernews",
                trend_score=50,
            ),
        ]
        _, _, dups = svc.deduplicate(topics)
        assert len(dups) == 1
        assert dups[0].title == "duplicate-A loser"
        assert dups[0].duplicate_of == "duplicate-A winner"
        assert dups[0].similarity == pytest.approx(1.0)

    def test_all_topics_are_duplicates(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(
                title="duplicate-A from reddit",
                source="reddit",
                trend_score=80,
            ),
            _make_topic(
                title="duplicate-A from hackernews",
                source="hackernews",
                trend_score=60,
            ),
            _make_topic(
                title="duplicate-A from google",
                source="google_trends",
                trend_score=40,
            ),
        ]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 1
        assert counts[deduped[0].title] == 3
        assert len(dups) == 2

    def test_no_duplicates_all_survive(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(title="unique one"),
            _make_topic(title="unique two"),
        ]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 2
        assert len(dups) == 0

    def test_single_topic(self) -> None:
        svc = _make_service()
        topics = [_make_topic(title="only one")]
        deduped, counts, dups = svc.deduplicate(topics)
        assert len(deduped) == 1
        assert counts[deduped[0].title] == 1
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestDeduplication -v`
Expected: FAIL

- [x] **Step 3: Implement deduplicate**

Add to `TopicRankingService`:

```python
    def deduplicate(
        self,
        topics: list[RawTopic],
    ) -> tuple[list[RawTopic], dict[str, int], list[DuplicateInfo]]:
        if len(topics) <= 1:
            counts = {t.title: 1 for t in topics}
            return list(topics), counts, []

        texts = [f"{t.title} {t.description}" for t in topics]
        embeddings = self._embedding.embed(texts)
        sim_matrix = self._embedding.cosine_similarity_matrix(embeddings)
        threshold = self._settings.dedup_similarity_threshold

        visited = [False] * len(topics)
        groups: list[list[int]] = []
        for i in range(len(topics)):
            if visited[i]:
                continue
            group = [i]
            visited[i] = True
            for j in range(i + 1, len(topics)):
                if not visited[j] and sim_matrix[i][j] >= threshold:
                    group.append(j)
                    visited[j] = True
            groups.append(group)

        deduped: list[RawTopic] = []
        source_counts: dict[str, int] = {}
        dup_info: list[DuplicateInfo] = []

        for group in groups:
            group_topics = [topics[idx] for idx in group]
            winner_idx_in_group = max(
                range(len(group)),
                key=lambda i: group_topics[i].trend_score,
            )
            winner = group_topics[winner_idx_in_group]
            winner_orig_idx = group[winner_idx_in_group]
            sources = {t.source for t in group_topics}
            source_counts[winner.title] = len(sources)
            deduped.append(winner)

            for i, orig_idx in enumerate(group):
                if i != winner_idx_in_group:
                    dup_info.append(
                        DuplicateInfo(
                            title=group_topics[i].title,
                            source=group_topics[i].source,
                            duplicate_of=winner.title,
                            similarity=sim_matrix[orig_idx][winner_orig_idx],
                        )
                    )

        logger.debug(
            "duplicates_removed",
            removed_count=len(dup_info),
            groups_count=len(groups),
        )
        return deduped, source_counts, dup_info
```

- [x] **Step 4: Run test to verify it passes**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestDeduplication -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/services/topic_ranking.py tests/unit/services/test_topic_ranking.py
git commit -m "feat: add semantic deduplication using embedding cosine similarity"
```

---

### Task 13: Implement calculate_scores and rank_and_deduplicate orchestrator

**Files:**
- Modify: `src/services/topic_ranking.py`
- Modify: `tests/unit/services/test_topic_ranking.py`

- [x] **Step 1: Write failing tests for full orchestration**

Add to `tests/unit/services/test_topic_ranking.py`:

```python
class TestCalculateScores:
    def test_produces_ranked_topics(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(title="topic A", velocity=10),
            _make_topic(title="topic B", velocity=50),
        ]
        source_counts = {"topic A": 1, "topic B": 2}
        result = svc.calculate_scores(topics, ["test"], source_counts)
        assert len(result) == 2
        assert all(isinstance(t, RankedTopic) for t in result)
        # Higher velocity + diversity → higher composite
        assert result[0].composite_score >= result[1].composite_score

    def test_ranks_assigned_sequentially(self) -> None:
        svc = _make_service()
        topics = [_make_topic(title=f"t{i}") for i in range(3)]
        counts = {f"t{i}": 1 for i in range(3)}
        result = svc.calculate_scores(topics, [], counts)
        ranks = [t.rank for t in result]
        assert ranks == [1, 2, 3]


class TestRankAndDeduplicate:
    async def test_full_pipeline(self) -> None:
        svc = _make_service()
        request = RankTopicsRequest(
            topics=[
                RawTopic(**{
                    "title": "duplicate-A cyber breach",
                    "source": "reddit",
                    "trend_score": 80,
                    "discovered_at": datetime.now(UTC),
                    "velocity": 10,
                    "domain_keywords": ["cybersecurity"],
                }),
                RawTopic(**{
                    "title": "duplicate-A security incident",
                    "source": "hackernews",
                    "trend_score": 60,
                    "discovered_at": datetime.now(UTC),
                    "velocity": 5,
                    "domain_keywords": ["cybersecurity"],
                }),
                RawTopic(**{
                    "title": "cooking tips unique",
                    "source": "reddit",
                    "trend_score": 90,
                    "discovered_at": datetime.now(UTC),
                }),
            ],
            domain="cybersecurity",
            domain_keywords=["cybersecurity", "security"],
            top_n=10,
        )
        response = await svc.rank_and_deduplicate(request)
        # cooking tips filtered out (no keyword match)
        # Two duplicate-A topics deduped to one
        assert response.total_input == 3
        assert response.total_returned <= 2
        assert len(response.ranked_topics) == response.total_returned
        assert response.ranked_topics[0].rank == 1

    async def test_empty_after_filter_returns_empty(self) -> None:
        svc = _make_service()
        request = RankTopicsRequest(
            topics=[_make_topic(title="cooking recipes")],
            domain="cybersecurity",
            domain_keywords=["cybersecurity"],
        )
        response = await svc.rank_and_deduplicate(request)
        assert response.total_returned == 0
        assert response.ranked_topics == []

    async def test_top_n_limits_results(self) -> None:
        svc = _make_service()
        topics = [
            _make_topic(title=f"cyber topic {i}", domain_keywords=["cyber"])
            for i in range(10)
        ]
        request = RankTopicsRequest(
            topics=topics,
            domain="cyber",
            domain_keywords=["cyber"],
            top_n=3,
        )
        response = await svc.rank_and_deduplicate(request)
        assert response.total_returned == 3
        assert len(response.ranked_topics) == 3
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py::TestCalculateScores tests/unit/services/test_topic_ranking.py::TestRankAndDeduplicate -v`
Expected: FAIL

- [x] **Step 3: Implement calculate_scores and rank_and_deduplicate**

Add to `TopicRankingService`:

```python
    def calculate_scores(
        self,
        topics: list[RawTopic],
        domain_keywords: list[str],
        source_counts: dict[str, int],
    ) -> list[RankedTopic]:
        velocity_scores = self._score_velocity(topics)
        scored: list[tuple[float, RawTopic, int]] = []

        for i, topic in enumerate(topics):
            relevance = self._score_relevance(topic, domain_keywords)
            recency = self._score_recency(topic)
            velocity = velocity_scores[i]
            diversity = self._score_diversity(
                source_counts.get(topic.title, 1),
            )
            composite = (
                relevance * self._settings.relevance_weight
                + recency * self._settings.recency_weight
                + velocity * self._settings.velocity_weight
                + diversity * self._settings.diversity_weight
            )
            scored.append((composite, topic, source_counts.get(topic.title, 1)))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            RankedTopic(
                **topic.model_dump(),
                composite_score=round(composite, 2),
                rank=rank,
                source_count=sc,
            )
            for rank, (composite, topic, sc) in enumerate(scored, start=1)
        ]

    async def rank_and_deduplicate(
        self,
        request: RankTopicsRequest,
    ) -> RankTopicsResponse:
        start = time.monotonic()
        total_input = len(request.topics)

        filtered = self.filter_by_domain(
            request.topics,
            request.domain,
            request.domain_keywords,
        )

        if not filtered:
            return RankTopicsResponse(
                ranked_topics=[],
                duplicates_removed=[],
                total_input=total_input,
                total_after_dedup=0,
                total_returned=0,
            )

        deduped, source_counts, dup_info = self.deduplicate(filtered)
        total_after_dedup = len(deduped)

        ranked = self.calculate_scores(
            deduped,
            request.domain_keywords,
            source_counts,
        )

        top = ranked[: request.top_n]

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "topics_ranked",
            input_count=total_input,
            dedup_count=total_after_dedup,
            returned_count=len(top),
            duration_ms=round(duration_ms),
        )

        return RankTopicsResponse(
            ranked_topics=top,
            duplicates_removed=dup_info,
            total_input=total_input,
            total_after_dedup=total_after_dedup,
            total_returned=len(top),
        )
```

- [x] **Step 4: Run all service tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_topic_ranking.py -v`
Expected: ALL PASS

- [x] **Step 5: Commit**

```bash
git add src/services/topic_ranking.py tests/unit/services/test_topic_ranking.py
git commit -m "feat: add composite scoring and rank_and_deduplicate orchestrator"
```

---

## Chunk 5: API Endpoint & Integration

### Task 14: Create topics router

**Files:**
- Create: `src/api/routers/topics.py`
- Modify: `src/api/main.py`
- Create: `tests/unit/api/test_topic_endpoints.py`

- [x] **Step 1: Write failing endpoint tests**

Create `tests/unit/api/test_topic_endpoints.py`:

```python
from datetime import UTC, datetime
from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from tests.unit.services.conftest import MockEmbeddingService

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header


def _topic_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Test Topic",
        "source": "hackernews",
        "trend_score": 75.0,
        "discovered_at": datetime.now(UTC).isoformat(),
        "velocity": 5.0,
        "domain_keywords": ["cyber"],
    }
    base.update(overrides)
    return base


def _rank_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "topics": [_topic_payload()],
        "domain": "cybersecurity",
        "domain_keywords": ["cyber"],
        "top_n": 10,
    }
    base.update(overrides)
    return base


@pytest.fixture
def topic_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def topic_app(topic_settings: Settings) -> FastAPI:
    app = create_app(topic_settings)
    app.state.embedding_service = MockEmbeddingService()
    return app


@pytest.fixture
async def topic_client(
    topic_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=topic_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestTopicEndpointAuth:
    async def test_no_token_returns_401(
        self,
        topic_client: httpx.AsyncClient,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
            headers=make_auth_header("viewer", topic_settings),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
            headers=make_auth_header("editor", topic_settings),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
            headers=make_auth_header("admin", topic_settings),
        )
        assert resp.status_code == 200


class TestTopicEndpointValidation:
    async def test_empty_topics_returns_422(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(topics=[]),
            headers=make_auth_header("editor", topic_settings),
        )
        assert resp.status_code == 422


class TestTopicEndpointSuccess:
    async def test_response_shape(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
            headers=make_auth_header("editor", topic_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "ranked_topics" in data
        assert "duplicates_removed" in data
        assert "total_input" in data
        assert data["total_input"] == 1

    async def test_empty_after_filter(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(
                topics=[_topic_payload(
                    title="cooking recipe",
                    domain_keywords=["food"],
                )],
                domain_keywords=["cybersecurity"],
            ),
            headers=make_auth_header("editor", topic_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_returned"] == 0


class TestTopicEndpoint503:
    async def test_embedding_failure_returns_503(
        self,
        topic_settings: Settings,
    ) -> None:
        app = create_app(topic_settings)
        # Do NOT inject MockEmbeddingService — force lazy load to fail
        # Remove any pre-set embedding_service
        if hasattr(app.state, "embedding_service"):
            del app.state.embedding_service
        # Set a nonexistent model name to trigger OSError on load
        app.state.settings = Settings(
            jwt_private_key=topic_settings.jwt_private_key,
            jwt_public_key=topic_settings.jwt_public_key,
            embedding_model="nonexistent-model-xyz",
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/topics/rank",
                json=_rank_request(),
                headers=make_auth_header("editor", topic_settings),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "embedding_service_unavailable"
```

- [x] **Step 2: Run test to verify it fails**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_topic_endpoints.py -v`
Expected: FAIL — 404 (no route registered)

- [x] **Step 3: Create topics router**

Create `src/api/routers/topics.py`:

```python
import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.topics import RankTopicsRequest, RankTopicsResponse
from src.services.embeddings import EmbeddingService
from src.services.topic_ranking import TopicRankingService

logger = structlog.get_logger()

topics_router = APIRouter()


def _get_embedding_service(request: Request) -> EmbeddingService:
    if not hasattr(request.app.state, "embedding_service"):
        request.app.state.embedding_service = EmbeddingService(
            model_name=request.app.state.settings.embedding_model,
        )
    return request.app.state.embedding_service


def _get_ranking_service(request: Request) -> TopicRankingService:
    return TopicRankingService(
        settings=request.app.state.settings,
        embedding_service=_get_embedding_service(request),
    )


@limiter.limit("10/minute")  # type: ignore[untyped-decorator]
@topics_router.post(
    "/topics/rank",
    response_model=RankTopicsResponse,
    summary="Rank and deduplicate topics",
)
async def rank_topics(
    request: Request,
    body: RankTopicsRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> RankTopicsResponse:
    service = _get_ranking_service(request)
    try:
        return await service.rank_and_deduplicate(body)
    except OSError as exc:
        logger.error(
            "embedding_model_failed",
            model_name=request.app.state.settings.embedding_model,
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="embedding_service_unavailable",
            message="Embedding service is not available",
        ) from exc
```

- [x] **Step 4: Register router in main.py**

Add to `src/api/main.py`:

Import at top:
```python
from src.api.routers.topics import topics_router
```

Add in `_register_routers`, after the admin router block:
```python
    app.include_router(
        topics_router,
        prefix=settings.api_v1_prefix,
        tags=["topics"],
    )
```

- [x] **Step 5: Run endpoint tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_topic_endpoints.py -v`
Expected: ALL PASS

- [x] **Step 6: Run full test suite**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v --tb=short`
Expected: ALL PASS

- [x] **Step 7: Commit**

```bash
git add src/api/routers/topics.py src/api/main.py tests/unit/api/test_topic_endpoints.py
git commit -m "feat: add POST /api/v1/topics/rank endpoint with auth and rate limiting"
```

---

### Task 15: Run linting and type checking

**Files:**
- Potentially fix: any files with lint/type issues

- [x] **Step 1: Run ruff check**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/ tests/`

- [x] **Step 2: Fix any lint issues**

- [x] **Step 3: Run mypy**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/services/ src/api/schemas/ src/api/routers/topics.py`

- [x] **Step 4: Fix any type issues**

- [x] **Step 5: Run full test suite with coverage**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ --cov=src --cov-report=term-missing -v`

- [x] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve lint and type checking issues"
```

---

### Task 16: Update progress tracking

**Files:**
- Modify: `project-management/PROGRESS.md`
- Modify: `project-management/BACKLOG.md`

- [x] **Step 1: Update PROGRESS.md**

In the `Epic 1: Trend Discovery Engine` table, change TREND-006 row from:
```
| TREND-006 | Topic Ranking & Dedup     | Backlog | —      | —    | —    |
```
to:
```
| TREND-006 | Topic Ranking & Dedup     | Done | `feature/TREND-006-topic-ranking-dedup` | [plan](../docs/superpowers/plans/2026-03-13-trend-006-topic-ranking-dedup.md) | [spec](../docs/superpowers/specs/2026-03-13-trend-006-topic-ranking-dedup-design.md) |
```

- [x] **Step 2: Update BACKLOG.md**

Add `— DONE` suffix to TREND-006 heading and add status/plan/spec fields.

- [x] **Step 3: Commit**

```bash
git add project-management/PROGRESS.md project-management/BACKLOG.md
git commit -m "docs: mark TREND-006 as Done in progress tracking"
```
