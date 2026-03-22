# INFRA-001b: Topic Persistence & Cross-Scan Dedup — Design Specification

> **Date**: 2026-03-22
> **Status**: Approved
> **Ticket**: INFRA-001 (part b)
> **Depends on**: INFRA-001a (Database Foundation — Done, PR #32)

---

## 1. Overview

Wire the trend scan flow to persist topics in PostgreSQL and implement cross-scan deduplication. After a scan, new topics are inserted and existing matches are updated (upsert-by-similarity). Add a `GET /topics` endpoint for retrieving persisted topics.

---

## 2. Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Persistence point | After `/topics/rank` returns ranked results | Topics are already deduped and scored at this point |
| Cross-scan dedup | Embed new topic titles, compare against existing DB topics using cosine similarity (0.85 threshold) | Reuses existing `EmbeddingService` + `dedup_similarity_threshold` from settings |
| Upsert behavior | Match found → update `trend_score`, `velocity`, `discovered_at`, increment `source_count`. No match → insert new row. | Keeps topic identity stable across scans while refreshing data |
| Where dedup runs | New `TopicPersistenceService` in `src/services/topic_persistence.py` | Keeps persistence logic out of the API router; testable in isolation |
| GET /topics endpoint | New endpoint returning paginated `PersistedTopic[]` from DB | Frontend needs to list persisted topics (for INFRA-002) |

---

## 3. Data Flow

```
POST /trends/fetch → RawTopic[] (unchanged)
POST /topics/rank → RankedTopic[] (unchanged)

NEW: POST /topics/persist (or called automatically after rank)
  1. For each RankedTopic, embed title via EmbeddingService
  2. Fetch existing topics from DB for same domain
  3. Embed existing topic titles
  4. Compute cosine similarity between new and existing
  5. If similarity >= 0.85: UPDATE existing row (trend_score, velocity, discovered_at, source_count++)
  6. If no match: INSERT new row with generated UUID
  7. Return persisted topic count (new + updated)

GET /topics?domain=X&page=1&size=20
  → Query TopicRow by domain, order by composite_score DESC
  → Return paginated PersistedTopic[]
```

---

## 4. New Types

### `PersistedTopic` (API response schema)

Add to `src/api/schemas/topics.py`:

```python
class PersistedTopic(BaseModel):
    id: UUID
    title: str
    description: str
    source: str
    external_url: str
    trend_score: float
    velocity: float
    domain: str
    discovered_at: datetime
    composite_score: float | None
    rank: int | None
    source_count: int
    created_at: datetime
    updated_at: datetime
```

### `PersistTopicsRequest` / `PersistTopicsResponse`

```python
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

---

## 5. Components

### 5.1 `src/services/topic_persistence.py` (~80 lines)

```python
class TopicPersistenceService:
    def __init__(self, session_factory, embedding_service, threshold):
        ...

    async def persist_ranked_topics(
        self, topics: list[RankedTopic], domain: str
    ) -> PersistResult:
        """Persist ranked topics with cross-scan dedup."""
```

Logic:
1. Fetch existing topics for domain from DB
2. Embed new topic titles + existing topic titles
3. For each new topic, find best match among existing (cosine similarity)
4. If >= threshold: update existing row
5. If < threshold: insert new row
6. Return counts (new, updated)

### 5.2 Extend `PgTopicRepository`

Add methods to `src/db/repositories.py`:

- `async create_from_ranked(topic: RankedTopic, domain: str) -> UUID` — insert new TopicRow
- `async update_from_scan(topic_id: UUID, topic: RankedTopic) -> None` — update trend_score, velocity, discovered_at, increment source_count
- `async list_by_domain(domain: str, page: int, size: int) -> tuple[list[TopicRow], int]` — paginated query

### 5.3 New API Endpoints

Add to `src/api/routers/topics.py`:

- `POST /topics/persist` — calls `TopicPersistenceService.persist_ranked_topics()`
- `GET /topics` — paginated list of persisted topics by domain

### 5.4 Frontend Integration

Update `frontend/src/hooks/use-scan-topics.ts`:
- After `rankTopics()` call, add `persistTopics()` call to save results to DB
- Add `fetchPersistedTopics()` to load topics on page mount (not just after scan)

---

## 6. Testing

- `test_topic_persistence.py` — unit tests for `TopicPersistenceService`:
  - New topics inserted when no matches
  - Existing topics updated when similarity >= 0.85
  - Mixed: some new, some updated
  - Empty input → no changes
- `test_topics_router.py` — update existing tests, add GET /topics test
- Integration test: full scan → persist → re-scan → verify dedup

---

## 7. File Summary

| File | Type | ~Lines |
|------|------|--------|
| `src/services/topic_persistence.py` | New — service | ~80 |
| `src/api/schemas/topics.py` | Modified — add schemas | +30 |
| `src/db/repositories.py` | Modified — extend PgTopicRepository | +40 |
| `src/api/routers/topics.py` | Modified — add 2 endpoints | +40 |
| `frontend/src/hooks/use-scan-topics.ts` | Modified — add persist call | +10 |
| `frontend/src/lib/api/trends.ts` | Modified — add persist/list functions | +20 |
| Tests | New + modified | ~120 |
| **Total** | | **~340** |
