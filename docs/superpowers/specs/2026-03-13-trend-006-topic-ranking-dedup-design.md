# Design Spec: TREND-006 — Topic Ranking & Deduplication

**Ticket**: TREND-006
**Date**: 2026-03-13
**Status**: Approved
**Branch**: `feature/TREND-006-topic-ranking-dedup`

---

## 1. Overview

Build a stateless topic ranking and semantic deduplication service. It accepts raw topics from any trend source, filters by domain relevance, removes near-duplicates using embedding cosine similarity, computes a weighted composite score, and returns the top N ranked topics.

**Scope**: Pure algorithm + API endpoint. No database persistence, no Milvus, no cron scheduling. Those integrate when TREND-001–005 and RESEARCH-003 land.

**Approach**: Single service class (Approach A) with an injected `EmbeddingService` for semantic dedup. Lightweight `sentence-transformers` model runs in-memory — no vector DB required at this stage.

---

## 2. Pydantic Schemas

### RawTopic (input)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | `str` | required | Topic headline |
| `description` | `str` | `""` | Optional longer text |
| `source` | `str` | required | Origin: `"google_trends"`, `"reddit"`, `"hackernews"`, etc. |
| `external_url` | `str` | `""` | Link to source |
| `trend_score` | `float` Field(ge=0, le=100) | required | Normalized score from source |
| `discovered_at` | `datetime` | required | When the source reported it |
| `velocity` | `float` Field(ge=0) | `0` | Rate of score change (points/hour) |
| `domain_keywords` | `list[str]` | `[]` | Tags from the source |

### RankedTopic (output)

All `RawTopic` fields, plus:

| Field | Type | Description |
|-------|------|-------------|
| `composite_score` | `float` | Weighted composite score (0–100) |
| `rank` | `int` | 1-based position |
| `source_count` | `int` | Number of distinct sources in this topic's dedup group |

### RankTopicsRequest

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `topics` | `list[RawTopic]` | required (min 1, max 500) | Raw topics to rank |
| `domain` | `str` | required | e.g., `"cybersecurity"` |
| `domain_keywords` | `list[str]` | `[]` | Keywords for relevance filtering |
| `top_n` | `int` (1–100) | `10` | Number of results to return |

### RankTopicsResponse

| Field | Type | Description |
|-------|------|-------------|
| `ranked_topics` | `list[RankedTopic]` | Sorted by composite_score descending |
| `duplicates_removed` | `list[DuplicateInfo]` | Topics removed during dedup, with `title` and `duplicate_of` fields |
| `total_input` | `int` | Count of topics received |
| `total_after_dedup` | `int` | Count after deduplication |
| `total_returned` | `int` | Final count returned (top_n or less) |

### DuplicateInfo

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | Title of the removed duplicate |
| `source` | `str` | Source of the removed duplicate |
| `duplicate_of` | `str` | Title of the surviving topic it matched |
| `similarity` | `float` | Cosine similarity score with the surviving topic |

---

## 3. Composite Scoring Algorithm

Four dimensions, weighted sum. Weights configurable via `COGNIFY_` environment variables with these defaults:

| Dimension | Weight | Input | Calculation |
|-----------|--------|-------|-------------|
| Relevance | 0.4 | `domain_keywords` match against title + description + tags | Jaccard similarity: `\|intersection\| / \|union\|` of keyword tokens, scaled to 0–100. If either token set is empty, score = 0. |
| Recency | 0.3 | `discovered_at` | Exponential decay: `100 * exp(-λ * hours_ago)`. λ = ln(2)/24 ≈ 0.02888 (24h = 50, 72h ≈ 12). If `discovered_at` is in the future (clock skew), clamp `hours_ago` to 0 (score = 100). |
| Velocity | 0.2 | `velocity` field | Min-max normalization across batch to 0–100. When all values are equal (min == max, including all zeros), score = 50 (neutral). |
| Source diversity | 0.1 | Distinct source count per dedup group | 3+ sources = 100, 2 = 66, 1 = 33. |

**Formula**: `composite = (relevance * w_r) + (recency * w_c) + (velocity * w_v) + (diversity * w_d)`

All individual scores normalized to 0–100. Composite is 0–100 only if weights sum to 1.0.

**Weight validation**: On service initialization, validate that `w_r + w_c + w_v + w_d == 1.0` (within float tolerance of 0.001). Raise `ValueError` on startup if not.

### Edge Cases

- Empty `domain_keywords` on request → relevance scores 50 for all (neutral)
- Single topic in batch → velocity = 50, diversity = 33
- All topics from same source → diversity = 33 for all
- All topics filtered out by domain → return empty `ranked_topics` with `total_after_dedup=0`, `total_returned=0` (no error)
- All topics are duplicates of each other → single surviving topic gets `source_count` = count of distinct sources across the merged group
- Topic with empty title and description → Jaccard relevance = 0 (empty token set)

---

## 4. Semantic Deduplication

### Process

1. Concatenate `title + " " + description` for each topic
2. Embed all texts using `sentence-transformers/all-MiniLM-L6-v2` (384-dim vectors)
3. Compute pairwise cosine similarity
4. Group topics with similarity >= 0.85 (configurable threshold)
5. Per group: keep the topic with highest `trend_score`. Record `source_count` = number of distinct sources in the group. Build `DuplicateInfo` entries for removed topics.

### Performance

- Batch sizes: ~50–200 topics per scan cycle
- Pairwise on 200 topics = 19,900 comparisons — trivial in-memory with numpy
- Model cold start: ~2–3s (lazy-loaded on first request)

### Future Migration

When RESEARCH-003 adds Milvus, embeddings can optionally be stored there and dedup performed via ANN search. The `EmbeddingService` interface stays the same.

---

## 5. EmbeddingService

```python
class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = None  # Lazy-loaded

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of 384-dim vectors."""

    def cosine_similarity_matrix(self, embeddings: list[list[float]]) -> list[list[float]]:
        """Pairwise cosine similarity matrix."""
```

- **Lazy loading**: Model loads on first `embed()` call, not at app startup
- **Singleton**: One instance on `app.state`, reused across requests
- **Testability**: Tests inject `MockEmbeddingService` with deterministic vectors

---

## 6. TopicRankingService

```python
class TopicRankingService:
    def __init__(
        self,
        settings: Settings,
        embedding_service: EmbeddingService,
    ):
        ...

    async def rank_and_deduplicate(
        self,
        request: RankTopicsRequest,
    ) -> RankTopicsResponse:
        """Main entry point. Orchestrates filter → dedup → score → rank."""

    def filter_by_domain(
        self,
        topics: list[RawTopic],
        domain_keywords: list[str],
    ) -> list[RawTopic]:
        """Remove topics with no keyword overlap. Uses simple keyword presence
        check (any keyword found in title/description/tags), NOT Jaccard score.
        If domain_keywords is empty, all topics pass through."""

    def deduplicate(
        self,
        topics: list[RawTopic],
    ) -> tuple[list[RawTopic], dict[str, int], list[DuplicateInfo]]:
        """Group by embedding similarity, keep highest trend_score per group.
        Returns (deduped_topics, source_counts_per_topic, duplicate_info_list).
        source_counts maps surviving topic title -> distinct source count in its group."""

    def calculate_scores(
        self,
        topics: list[RawTopic],
        domain_keywords: list[str],
        source_counts: dict[str, int],
    ) -> list[RankedTopic]:
        """Compute composite scores for all topics."""
```

Private methods for each scoring dimension: `_score_relevance()`, `_score_recency()`, `_score_velocity()`, `_score_diversity()`.

---

## 7. API Endpoint

```
POST /api/v1/topics/rank
Auth: editor or admin (via require_role dependency)
Rate limit: 10/minute
```

**Request**: `RankTopicsRequest` (JSON body)
**Response**: `RankTopicsResponse`

**Error responses**:
- 422: Pydantic validation (empty topics list, invalid types, batch > 500)
- 401/403: Auth/RBAC failures
- 503: Embedding model failed to load — uses new `ServiceUnavailableError(code="embedding_service_unavailable")`

### Router wiring

`TopicRankingService` is instantiated per-request (stateless, cheap). `EmbeddingService` (which holds the heavy model) is a singleton on `app.state`.

```python
@topics_router.post("/topics/rank", response_model=RankTopicsResponse)
@limiter.limit("10/minute")
async def rank_topics(
    request: Request,
    body: RankTopicsRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> RankTopicsResponse:
    service = _get_ranking_service(request)
    return await service.rank_and_deduplicate(body)

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
```

### Structured Logging

The service logs these events via structlog:

| Event | Level | Fields | When |
|-------|-------|--------|------|
| `topics_ranked` | INFO | `input_count`, `dedup_count`, `returned_count`, `duration_ms` | After successful ranking |
| `topics_filtered` | DEBUG | `before_count`, `after_count`, `domain` | After domain filtering |
| `duplicates_removed` | DEBUG | `removed_count`, `groups_count` | After dedup |
| `embedding_model_loaded` | INFO | `model_name`, `load_duration_ms` | On first model load |
| `embedding_model_failed` | ERROR | `model_name`, `error` | If model fails to load |

---

## 8. Configuration (Settings additions)

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| `embedding_model` | `COGNIFY_EMBEDDING_MODEL` | `"all-MiniLM-L6-v2"` | Sentence-transformers model |
| `dedup_similarity_threshold` | `COGNIFY_DEDUP_SIMILARITY_THRESHOLD` | `0.85` | Cosine similarity threshold |
| `relevance_weight` | `COGNIFY_RELEVANCE_WEIGHT` | `0.4` | Relevance scoring weight |
| `recency_weight` | `COGNIFY_RECENCY_WEIGHT` | `0.3` | Recency scoring weight |
| `velocity_weight` | `COGNIFY_VELOCITY_WEIGHT` | `0.2` | Velocity scoring weight |
| `diversity_weight` | `COGNIFY_DIVERSITY_WEIGHT` | `0.1` | Source diversity weight |

---

## 9. File Layout

### New files

```
src/api/schemas/__init__.py
src/api/schemas/topics.py          — RawTopic, RankedTopic, RankTopicsRequest, RankTopicsResponse
src/services/__init__.py           — (already exists as placeholder)
src/services/topic_ranking.py      — TopicRankingService
src/services/embeddings.py         — EmbeddingService
src/api/routers/topics.py          — POST /api/v1/topics/rank
tests/unit/services/conftest.py    — MockEmbeddingService fixture
tests/unit/services/test_topic_ranking.py
tests/unit/services/test_embeddings.py
tests/unit/api/test_topic_endpoints.py
```

### Modified files

```
src/api/main.py                    — register topics router
src/api/errors.py                  — add ServiceUnavailableError (503)
src/api/routers/health.py          — rename weaviate → milvus in DependencyChecks
src/config/settings.py             — add ranking/embedding settings
pyproject.toml                     — add sentence-transformers, numpy
```

`src/api/schemas/__init__.py` re-exports all schema classes for clean imports.

---

## 10. Testing Strategy

### MockEmbeddingService

Deterministic mock for unit tests:
- Texts containing "duplicate-A" return the same fixed vector (e.g., `[1, 0, 0, ...]`)
- Texts containing "duplicate-B" return another identical vector (e.g., `[0, 1, 0, ...]`)
- All other texts return unique orthogonal vectors based on hash of input text
- This produces cosine similarity = 1.0 within each duplicate group and ~0.0 between groups

### Unit tests

- **Scoring**: Feed topics where only one dimension varies, assert correct ordering
- **Relevance**: Topics with matching keywords score higher
- **Recency**: Recent topics score higher than old ones; future `discovered_at` clamped to score 100
- **Velocity**: High-velocity topics score higher; all-equal velocities → all score 50
- **Diversity**: Multi-source topics score higher
- **Dedup**: 5 topics with 2 near-duplicates → 4 returned, correct `DuplicateInfo` in response
- **Filtering**: Topics with no domain relevance removed; empty keywords → all pass
- **Edge cases**: Single topic, all duplicates, empty keywords, all same source, all zero velocity, empty title/description (Jaccard = 0)
- **Weight validation**: Weights not summing to 1.0 → `ValueError`
- **Batch limit**: 501 topics → 422 validation error

### Endpoint tests

- Auth required (401 without token)
- Role required (403 for viewer)
- Validation (422 for empty topics, 422 for batch > 500)
- Success path (200 with correct response shape)
- Embedding failure (503)
- Empty result after filtering (200 with empty ranked_topics)

### Coverage targets

| File | Target |
|------|--------|
| `topic_ranking.py` | 80%+ |
| `topics.py` router | 90%+ |
| `embeddings.py` | 80%+ |
| `schemas/topics.py` | 80%+ |

---

## 11. Future Integration Points

This design is intentionally stateless. The following integrations happen in later tickets:

| Integration | Ticket | What changes |
|-------------|--------|-------------|
| **Trend source adapters** | TREND-001–005 | Each adapter produces `list[RawTopic]`. Batched and passed to `TopicRankingService.rank_and_deduplicate()`. Primary consumer of this service. |
| **Database persistence** | TREND-001–005 or DASH-001 | Add SQLAlchemy models mirroring Pydantic schemas. Add repository layer. Service interface unchanged. |
| **Milvus for dedup** | RESEARCH-003 | Move embeddings from in-memory to Milvus ANN search. `EmbeddingService` interface unchanged. |
| **Cron scheduling** | TREND-001–005 | Ranking runs automatically after each trend scan. Service called from Celery task. |
| **WebSocket updates** | DASH-001 | Push new rankings to dashboard via WebSocket after ranking completes. |
| **Per-domain weights** | Future enhancement | Move weights from Settings to `DomainConfig` JSON. Service reads from config parameter instead of settings. |

---

## 12. Dependencies (pyproject.toml additions)

```toml
[project]
dependencies = [
    # ... existing ...
    "sentence-transformers>=3.0.0",
    "numpy>=1.26.0",
]
```
