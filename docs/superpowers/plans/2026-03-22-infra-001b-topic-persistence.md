# INFRA-001b: Topic Persistence & Cross-Scan Dedup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the trend scan flow to persist topics in PostgreSQL with cross-scan deduplication, and add a GET /topics endpoint for listing persisted topics.

**Architecture:** New `TopicPersistenceService` handles dedup logic using `EmbeddingService` for cosine similarity. Extended `PgTopicRepository` with create/update/list methods. Two new API endpoints: `POST /topics/persist` and `GET /topics`. Frontend scan hook calls persist after ranking.

**Tech Stack:** SQLAlchemy async, asyncpg, sentence-transformers (EmbeddingService), FastAPI

**Spec:** `docs/superpowers/specs/2026-03-22-infra-001b-topic-persistence-design.md`

**Worktree:** `D:/Workbench/github/cognify-infra-001b` on branch `feature/INFRA-001b-topic-persistence`

---

## File Structure

### New Files

| File | Responsibility | ~Lines |
|------|---------------|--------|
| `src/services/topic_persistence.py` | Dedup + persist logic | ~80 |
| `tests/unit/services/test_topic_persistence.py` | Persistence service tests | ~100 |

### Modified Files

| File | Change |
|------|--------|
| `src/api/schemas/topics.py` | Add `PersistedTopic`, `PersistTopicsRequest`, `PersistTopicsResponse`, `PaginatedTopics` |
| `src/db/repositories.py` | Extend `PgTopicRepository` with `create_from_ranked`, `update_from_scan`, `list_by_domain` |
| `src/api/routers/topics.py` | Add `POST /topics/persist` and `GET /topics` endpoints |
| `src/api/main.py` | Initialize `TopicPersistenceService` on app state |
| `frontend/src/hooks/use-scan-topics.ts` | Call persist after rank, load persisted topics on mount |
| `frontend/src/lib/api/trends.ts` | Add `persistTopics()` and `fetchTopics()` API functions |

---

## Task 1: Extend Schemas and Repository

**Files:**
- Modify: `src/api/schemas/topics.py`
- Modify: `src/db/repositories.py`

- [ ] **Step 1: Add new schemas to topics.py**

Add to `src/api/schemas/topics.py`:

```python
from uuid import UUID

class PersistedTopic(BaseModel):
    """Topic persisted in the database with cross-scan metadata."""

    id: UUID
    title: str
    description: str
    source: str
    external_url: str
    trend_score: float
    velocity: float
    domain: str
    discovered_at: datetime
    composite_score: float | None = None
    rank: int | None = None
    source_count: int = 1
    created_at: datetime
    updated_at: datetime


class PersistTopicsRequest(BaseModel):
    ranked_topics: list[RankedTopic]
    domain: str


class PersistTopicsResponse(BaseModel):
    new_count: int
    updated_count: int
    total_persisted: int


class PaginatedTopics(BaseModel):
    items: list[PersistedTopic]
    total: int
    page: int
    size: int
```

- [ ] **Step 2: Extend PgTopicRepository**

Add 3 methods to `PgTopicRepository` in `src/db/repositories.py`:

```python
async def create_from_ranked(
    self, topic: RankedTopic, domain: str,
) -> UUID:
    """Insert a new topic from a ranked scan result."""
    topic_id = uuid4()
    async with self._session_factory() as session:
        row = TopicRow(
            id=topic_id,
            title=topic.title,
            description=topic.description,
            source=topic.source,
            external_url=topic.external_url,
            trend_score=topic.trend_score,
            velocity=topic.velocity,
            domain=domain,
            discovered_at=topic.discovered_at,
            domain_keywords=topic.domain_keywords,
            composite_score=topic.composite_score,
            rank=topic.rank,
            source_count=topic.source_count,
        )
        session.add(row)
        await session.commit()
    return topic_id


async def update_from_scan(
    self, topic_id: UUID, topic: RankedTopic,
) -> None:
    """Update an existing topic with fresh scan data."""
    async with self._session_factory() as session:
        row = await session.get(TopicRow, topic_id)
        if row is None:
            return
        row.trend_score = topic.trend_score
        row.velocity = topic.velocity
        row.discovered_at = topic.discovered_at
        row.composite_score = topic.composite_score
        row.rank = topic.rank
        row.source_count = row.source_count + 1
        await session.commit()


async def list_by_domain(
    self, domain: str, page: int = 1, size: int = 20,
) -> tuple[list[PersistedTopic], int]:
    """List topics by domain, ordered by composite_score."""
    from src.api.schemas.topics import PersistedTopic
    async with self._session_factory() as session:
        count_q = (
            select(func.count())
            .select_from(TopicRow)
            .where(TopicRow.domain == domain)
        )
        total = (await session.execute(count_q)).scalar_one()
        q = (
            select(TopicRow)
            .where(TopicRow.domain == domain)
            .order_by(TopicRow.composite_score.desc().nulls_last())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await session.execute(q)).scalars().all()
        items = [
            PersistedTopic(
                id=r.id, title=r.title,
                description=r.description,
                source=r.source,
                external_url=r.external_url,
                trend_score=r.trend_score,
                velocity=r.velocity,
                domain=r.domain,
                discovered_at=r.discovered_at,
                composite_score=r.composite_score,
                rank=r.rank,
                source_count=r.source_count,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
        return items, total
```

Add needed imports: `from src.api.schemas.topics import RankedTopic, PersistedTopic`

- [ ] **Step 3: Verify imports compile**

Run: `cd D:/Workbench/github/cognify-infra-001b && uv run python -c "from src.db.repositories import PgTopicRepository; print('OK')"`

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001b
git add src/api/schemas/topics.py src/db/repositories.py
git commit -m "feat(infra-001b): extend topic schemas and PgTopicRepository with CRUD methods"
```

---

## Task 2: TopicPersistenceService

**Files:**
- Create: `tests/unit/services/test_topic_persistence.py`
- Create: `src/services/topic_persistence.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/services/test_topic_persistence.py`:

```python
"""Tests for topic persistence with cross-scan dedup."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.schemas.topics import RankedTopic
from src.services.topic_persistence import TopicPersistenceService


def _make_ranked(title: str, score: float) -> RankedTopic:
    return RankedTopic(
        title=title,
        description=f"About {title}",
        source="hackernews",
        external_url="https://example.com",
        trend_score=score,
        discovered_at=datetime.now(UTC),
        velocity=10.0,
        domain_keywords=["tech"],
        composite_score=score,
        rank=1,
        source_count=1,
    )


class TestTopicPersistenceService:
    @pytest.mark.asyncio
    async def test_inserts_new_topics(self) -> None:
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([], 0)
        repo.create_from_ranked.return_value = "new-id"
        embedding = MagicMock()
        embedding.embed.return_value = [[0.1, 0.2, 0.3]]

        svc = TopicPersistenceService(
            repo=repo, embedding_service=embedding, threshold=0.85,
        )
        result = await svc.persist_ranked_topics(
            [_make_ranked("New Topic", 80)], "tech",
        )
        assert result.new_count == 1
        assert result.updated_count == 0
        repo.create_from_ranked.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_on_match(self) -> None:
        from src.api.schemas.topics import PersistedTopic
        from uuid import uuid4

        existing_id = uuid4()
        existing = PersistedTopic(
            id=existing_id, title="AI Trends",
            description="About AI", source="reddit",
            external_url="", trend_score=70, velocity=5,
            domain="tech", discovered_at=datetime.now(UTC),
            composite_score=70, rank=1, source_count=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([existing], 1)
        embedding = MagicMock()
        # Return similar embeddings (cosine sim ~1.0)
        embedding.embed.return_value = [[1.0, 0.0, 0.0]]

        svc = TopicPersistenceService(
            repo=repo, embedding_service=embedding, threshold=0.85,
        )
        result = await svc.persist_ranked_topics(
            [_make_ranked("AI Trends 2026", 85)], "tech",
        )
        assert result.new_count == 0
        assert result.updated_count == 1
        repo.update_from_scan.assert_called_once()

    @pytest.mark.asyncio
    async def test_mixed_new_and_updated(self) -> None:
        from src.api.schemas.topics import PersistedTopic
        from uuid import uuid4

        existing = PersistedTopic(
            id=uuid4(), title="Existing Topic",
            description="", source="reddit",
            external_url="", trend_score=60, velocity=0,
            domain="tech", discovered_at=datetime.now(UTC),
            composite_score=60, rank=1, source_count=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        repo = AsyncMock()
        repo.list_by_domain.return_value = ([existing], 1)
        repo.create_from_ranked.return_value = "new-id"
        embedding = MagicMock()
        # First call: embed new topics (2 topics)
        # Second call: embed existing topics (1 topic)
        # Similar for first, different for second
        embedding.embed.side_effect = [
            [[1.0, 0.0], [0.0, 1.0]],  # new topics
            [[1.0, 0.0]],  # existing topics
        ]

        svc = TopicPersistenceService(
            repo=repo, embedding_service=embedding, threshold=0.85,
        )
        result = await svc.persist_ranked_topics(
            [
                _make_ranked("Existing Topic Refreshed", 70),
                _make_ranked("Brand New Topic", 50),
            ],
            "tech",
        )
        assert result.new_count == 1
        assert result.updated_count == 1

    @pytest.mark.asyncio
    async def test_empty_input(self) -> None:
        repo = AsyncMock()
        embedding = MagicMock()
        svc = TopicPersistenceService(
            repo=repo, embedding_service=embedding, threshold=0.85,
        )
        result = await svc.persist_ranked_topics([], "tech")
        assert result.new_count == 0
        assert result.updated_count == 0
        assert result.total_persisted == 0
```

- [ ] **Step 2: Implement TopicPersistenceService**

Create `src/services/topic_persistence.py`:

```python
"""Topic persistence with cross-scan deduplication.

Persists ranked topics to PostgreSQL, deduplicating against
existing topics using embedding cosine similarity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.api.schemas.topics import PersistedTopic, RankedTopic
    from src.db.repositories import PgTopicRepository
    from src.services.embeddings import EmbeddingService

logger = structlog.get_logger()


@dataclass(frozen=True)
class PersistResult:
    """Result of a topic persistence operation."""

    new_count: int
    updated_count: int
    total_persisted: int


class TopicPersistenceService:
    """Persists ranked topics with cross-scan dedup."""

    def __init__(
        self,
        repo: PgTopicRepository,
        embedding_service: EmbeddingService,
        threshold: float = 0.85,
    ) -> None:
        self._repo = repo
        self._embedding = embedding_service
        self._threshold = threshold

    async def persist_ranked_topics(
        self,
        topics: list[RankedTopic],
        domain: str,
    ) -> PersistResult:
        """Persist topics, deduping against existing DB topics."""
        if not topics:
            return PersistResult(0, 0, 0)

        existing, _ = await self._repo.list_by_domain(
            domain, page=1, size=500,
        )
        matches = self._find_matches(topics, existing)

        new_count = 0
        updated_count = 0
        for i, topic in enumerate(topics):
            match_id = matches.get(i)
            if match_id is not None:
                await self._repo.update_from_scan(match_id, topic)
                updated_count += 1
            else:
                await self._repo.create_from_ranked(topic, domain)
                new_count += 1

        logger.info(
            "topics_persisted",
            domain=domain,
            new=new_count,
            updated=updated_count,
        )
        return PersistResult(
            new_count=new_count,
            updated_count=updated_count,
            total_persisted=new_count + updated_count,
        )

    def _find_matches(
        self,
        new_topics: list[RankedTopic],
        existing: list[PersistedTopic],
    ) -> dict[int, str]:
        """Find which new topics match existing ones.

        Returns: {new_index: existing_topic_id}
        """
        if not existing:
            return {}

        new_titles = [t.title for t in new_topics]
        existing_titles = [t.title for t in existing]
        new_embs = self._embedding.embed(new_titles)
        existing_embs = self._embedding.embed(existing_titles)

        matches: dict[int, str] = {}
        for i, new_emb in enumerate(new_embs):
            best_sim = 0.0
            best_id = None
            for j, ex_emb in enumerate(existing_embs):
                sim = self._cosine_sim(new_emb, ex_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_id = existing[j].id
            if best_sim >= self._threshold and best_id is not None:
                matches[i] = best_id
        return matches

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
```

- [ ] **Step 3: Run tests**

Run: `cd D:/Workbench/github/cognify-infra-001b && uv run pytest tests/unit/services/test_topic_persistence.py -v 2>&1 | tail -15`

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001b
git add src/services/topic_persistence.py tests/unit/services/test_topic_persistence.py
git commit -m "feat(infra-001b): add TopicPersistenceService with cross-scan dedup"
```

---

## Task 3: API Endpoints and App Wiring

**Files:**
- Modify: `src/api/routers/topics.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: Add POST /topics/persist and GET /topics endpoints**

In `src/api/routers/topics.py`, add:

```python
from src.api.schemas.topics import (
    PaginatedTopics,
    PersistTopicsRequest,
    PersistTopicsResponse,
)


@limiter.limit("5/minute")
@topics_router.post(
    "/topics/persist",
    response_model=PersistTopicsResponse,
    summary="Persist ranked topics with cross-scan dedup",
)
async def persist_topics(
    request: Request,
    body: PersistTopicsRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> PersistTopicsResponse:
    svc = request.app.state.topic_persistence_service
    result = await svc.persist_ranked_topics(
        body.ranked_topics, body.domain,
    )
    return PersistTopicsResponse(
        new_count=result.new_count,
        updated_count=result.updated_count,
        total_persisted=result.total_persisted,
    )


@limiter.limit("30/minute")
@topics_router.get(
    "/topics",
    response_model=PaginatedTopics,
    summary="List persisted topics by domain",
)
async def list_topics(
    request: Request,
    domain: str,
    page: int = 1,
    size: int = 20,
    user: TokenPayload = Depends(require_role("admin", "editor", "viewer")),
) -> PaginatedTopics:
    repo = request.app.state.topic_repo
    items, total = await repo.list_by_domain(domain, page, size)
    return PaginatedTopics(
        items=items, total=total, page=page, size=size,
    )
```

- [ ] **Step 2: Wire services in main.py lifespan**

In the `_lifespan` function in `src/api/main.py`, inside the `if db_url:` block, after creating PG repos, add:

```python
        # Topic persistence service
        topic_repo = PgTopicRepository(sf)
        app.state.topic_repo = topic_repo
        app.state.topic_persistence_service = TopicPersistenceService(
            repo=topic_repo,
            embedding_service=_get_or_create_embedding_service(app),
            threshold=app.state.settings.dedup_similarity_threshold,
        )
```

Add import: `from src.services.topic_persistence import TopicPersistenceService`

Add helper (or reuse from topics router):
```python
def _get_or_create_embedding_service(app: FastAPI) -> EmbeddingService:
    if not hasattr(app.state, "embedding_service"):
        from src.services.embeddings import EmbeddingService
        app.state.embedding_service = EmbeddingService(
            model_name=app.state.settings.embedding_model,
        )
    return app.state.embedding_service
```

- [ ] **Step 3: Run existing tests**

Run: `cd D:/Workbench/github/cognify-infra-001b && uv run pytest tests/unit/ -q --tb=short 2>&1 | tail -5`

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001b
git add src/api/routers/topics.py src/api/main.py
git commit -m "feat(infra-001b): add POST /topics/persist and GET /topics endpoints"
```

---

## Task 4: Frontend Integration

**Files:**
- Modify: `frontend/src/lib/api/trends.ts`
- Modify: `frontend/src/hooks/use-scan-topics.ts`

- [ ] **Step 1: Add API functions**

In `frontend/src/lib/api/trends.ts`, add:

```typescript
export interface PersistTopicsRequest {
  ranked_topics: BackendRankedTopic[];
  domain: string;
}

export interface PersistTopicsResponse {
  new_count: number;
  updated_count: number;
  total_persisted: number;
}

export interface PersistedTopic {
  id: string;
  title: string;
  description: string;
  source: string;
  external_url: string;
  trend_score: number;
  velocity: number;
  domain: string;
  discovered_at: string;
  composite_score: number | null;
  rank: number | null;
  source_count: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedTopics {
  items: PersistedTopic[];
  total: number;
  page: number;
  size: number;
}

export async function persistTopics(req: PersistTopicsRequest): Promise<PersistTopicsResponse> {
  const { data } = await apiClient.post<PersistTopicsResponse>("/topics/persist", req);
  return data;
}

export async function fetchPersistedTopics(domain: string, page = 1, size = 20): Promise<PaginatedTopics> {
  const { data } = await apiClient.get<PaginatedTopics>("/topics", { params: { domain, page, size } });
  return data;
}
```

- [ ] **Step 2: Update useScanTopics to persist after rank**

In `frontend/src/hooks/use-scan-topics.ts`, after the `rankTopics()` call and before setting topics, add:

```typescript
      // Step 3: Persist to database (best-effort, don't block UI)
      try {
        await persistTopics({
          ranked_topics: rankResult.ranked_topics,
          domain,
        });
      } catch {
        console.warn("Topic persistence failed — results shown but not saved");
      }
```

Add import: `import { persistTopics } from "@/lib/api/trends";`

- [ ] **Step 3: Run frontend tests**

Run: `cd D:/Workbench/github/cognify-infra-001b/frontend && npm install && npx vitest run 2>&1 | tail -10`

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001b
git add frontend/src/lib/api/trends.ts frontend/src/hooks/use-scan-topics.ts
git commit -m "feat(infra-001b): wire frontend scan to persist topics after ranking"
```

---

## Task 5: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-infra-001b && uv run pytest tests/unit/ -q --tb=short 2>&1 | tail -5`

- [ ] **Step 2: Run lint**

Run: `cd D:/Workbench/github/cognify-infra-001b && uv tool run ruff check src/services/topic_persistence.py src/api/routers/topics.py src/db/repositories.py 2>&1`

- [ ] **Step 3: Run frontend tests**

Run: `cd D:/Workbench/github/cognify-infra-001b/frontend && npx vitest run 2>&1 | tail -5`

- [ ] **Step 4: Fix any issues and commit**
