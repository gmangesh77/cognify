# Comprehensive Code Review: Cognify

**Date**: 2026-03-25
**Reviewer**: Claude Code (Automated)
**Scope**: Full codebase — database queries, security, API design, architecture, performance, code quality

---

## Executive Summary

The Cognify codebase is well-structured with a clean repository pattern, proper SQLAlchemy parameterization (zero SQL injection risks), and good test coverage (~764 backend + 237 frontend tests). However, several issues need attention before production readiness, particularly around **slow query patterns**, **missing authentication on endpoints**, **input validation gaps**, and **significant coding standard violations**.

| Severity | Count | Category |
|----------|-------|----------|
| Critical | 5 | Query perf, file size, auth gaps |
| High | 10 | Input validation, caching, error handling |
| Medium | 12 | Type safety, async issues, duplication |
| Low | 8 | Minor optimizations, style |

---

## 1. Database & Query Performance (SLOW QUERY FOCUS)

### 1.1 CRITICAL: Missing `pool_pre_ping` — Stale Connection Crashes

**File**: `src/db/engine.py:13-20`

```python
return _create_engine(
    database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    # MISSING: pool_pre_ping=True
    # MISSING: pool_recycle=3600
)
```

**Impact**: If PostgreSQL closes idle connections (default 10min timeout), SQLAlchemy will attempt to use dead connections, causing `OperationalError` on next query. Under low-traffic conditions, every first request after idle period will fail.

**Fix**: Add `pool_pre_ping=True` and `pool_recycle=3600`.

---

### 1.2 CRITICAL: O(n) Individual INSERT/UPDATE Per Topic (No Batching)

**File**: `src/services/topic_persistence.py:62-71`

```python
for i, topic in enumerate(topics):
    match_id = matches.get(i)
    if match_id is not None:
        await self._repo.update_from_scan(match_id, topic)  # 1 UPDATE per topic
    else:
        new_id = await self._repo.create_from_ranked(topic, domain)  # 1 INSERT per topic
```

**Impact**: Persisting 100 topics = 100 individual DB round-trips. At ~2ms per query, this adds 200ms+ to every scan persist operation.

**Fix**: Use `session.add_all()` for inserts and batch UPDATE with `executemany()` for updates.

---

### 1.3 HIGH: O(n*m) In-Memory Cosine Similarity for Topic Dedup

**File**: `src/services/topic_persistence.py:104-114`

```python
for i, new_emb in enumerate(new_embs):      # n new topics
    for j, ex_emb in enumerate(existing_embs):  # m existing topics (up to 500)
        sim = self._cosine_sim(new_emb, ex_emb)
```

**Impact**: With 50 new topics and 500 existing = 25,000 cosine similarity computations per scan. CPU-bound, blocks async event loop.

**Fix**: Use numpy vectorized operations (`np.dot(new_matrix, existing_matrix.T)`) or offload to pgvector/Milvus for similarity search.

---

### 1.4 HIGH: Dual COUNT + SELECT Queries on Every List Endpoint

**Files**:
- `src/db/repositories.py:105-126` — ResearchSession list
- `src/db/repositories.py:304-314` — Topic list_by_domain
- `src/db/repositories.py:506-516` — Article list

```python
# Query 1: COUNT (scans all matching rows)
count_q = select(func.count()).select_from(ResearchSessionRow)
total = (await db.execute(count_q)).scalar_one()

# Query 2: SELECT with LIMIT/OFFSET
result = await db.execute(query.offset(offset).limit(size))
```

**Impact**: Every paginated list endpoint fires 2 queries. The COUNT query scans all matching rows even when you only need 20 items. As tables grow, COUNT becomes the bottleneck.

**Fix**: Use window functions (`SELECT *, COUNT(*) OVER() AS total FROM ...`) to combine into a single query, or cache total counts with short TTL.

---

### 1.5 HIGH: Hardcoded size=500 Loads All Domain Topics Into Memory

**File**: `src/services/topic_persistence.py:54-56`

```python
existing, _ = await self._repo.list_by_domain(
    domain, page=1, size=500,
)
```

**Impact**: Every topic persist operation loads up to 500 topic rows + their embeddings into memory. As domains grow, this becomes a memory and query performance issue.

**Fix**: Use cursor-based pagination or move dedup to the database layer.

---

### 1.6 MEDIUM: Missing Eager Loading — N+1 Risk on Session Detail

**File**: `src/services/research.py:151-156`

```python
session = await self._repos.sessions.get(session_id)   # Query 1
steps = await self._repos.steps.list_by_session(session_id)  # Query 2
```

**Impact**: 2 queries per session detail request. Not critical now, but if a "list sessions with steps" endpoint is added, this becomes N+1.

**Fix**: Use `joinedload(ResearchSessionRow.steps)` in the query.

---

### 1.7 MEDIUM: Singleton Config Queries Without Caching

**File**: `src/db/settings_singleton_repositories.py:23, 39, 73, 91, 131, 146`

```python
result = await db.execute(select(LlmConfigRow).limit(1))
```

**Impact**: Config values (LLM config, SEO defaults, general config) are queried from DB on every access. Multiple config reads per request = redundant identical queries.

**Fix**: Cache in per-request context or use Redis with 60s TTL.

---

### 1.8 LOW: Missing Indexes on Queried Columns

| Column | File | Queried At | Indexed |
|--------|------|------------|---------|
| `article_drafts.status` | `tables.py:105` | Content service filters | No |
| `canonical_articles.generated_at` | `tables.py:130` | `ORDER BY` in list query | No |
| `canonical_articles.domain` | `tables.py:130` | Potential future filter | No |

**Impact**: Low for current data volume, but will degrade with 10K+ articles.

---

### 1.9 MEDIUM: No Transaction Spanning for Multi-Step Operations

**Pattern**: Every repository method opens and commits its own session:

```python
async with self._sf() as db:
    db.add(row)
    await db.commit()
```

**Impact**: Multi-step operations (create topic + create session + create draft) are not atomic. If step 2 fails, step 1 is already committed — orphaned data.

**Fix**: Accept an optional session parameter or implement Unit of Work pattern.

---

## 2. Security Issues

### 2.1 CRITICAL: Unauthenticated `/topics` List Endpoint

**File**: `src/api/routers/topics.py:88-109`

```python
@topics_router.get("/topics", response_model=PaginatedTopics)
async def list_topics(
    request: Request,
    domain: str = "",
    page: int = 1,
    size: int = 20,
) -> PaginatedTopics:  # NO Depends(require_viewer_or_above)
```

**Impact**: Any unauthenticated user can enumerate all topics and domains. This exposes internal trend research data.

**Fix**: Add `user: TokenPayload = Depends(require_viewer_or_above)`.

---

### 2.2 HIGH: Missing Pagination Validation — DoS Risk

**Files**:
- `src/api/routers/topics.py:93-98` — `page: int = 1, size: int = 20` (no bounds)
- `src/api/routers/canonical_articles.py:48-62` — same issue

**Compare** with correct pattern in `src/api/routers/research.py:188-189`:
```python
page: int = Query(default=1, ge=1),
size: int = Query(default=20, ge=1, le=100),
```

**Impact**: Attacker can request `size=999999` to trigger full table scans and exhaust memory.

**Fix**: Use `Query(ge=1, le=100)` on all pagination parameters.

---

### 2.3 HIGH: UUID Parsing Raises 500 Instead of 400

**Files**: Multiple routers — `canonical_articles.py:79,97`, `articles.py:68,85`, `research.py:150`

```python
detail = await svc.get_session(UUID(session_id))  # ValueError on invalid UUID → 500
```

**Impact**: Invalid UUID input returns HTTP 500 "internal_error" instead of 400 "bad_request". Pollutes error monitoring.

**Fix**: Wrap in try/except ValueError → raise HTTPException(400).

---

### 2.4 MEDIUM: Bare `except Exception` Swallows Errors Silently

**Files**:
- `src/api/main.py:103,141,337,388` — Startup/init catches all exceptions
- `src/api/routers/topics.py:107-109` — Returns empty list on ANY error

```python
except Exception as exc:
    logger.error("list_topics_failed", error=str(exc))
    return PaginatedTopics(items=[], total=0, page=page, size=size)  # Masks bugs
```

**Impact**: Programming errors, type errors, and DB connection failures all silently return empty results. Makes debugging extremely difficult.

**Fix**: Catch specific exceptions (ConnectionError, TimeoutError). Let programming errors propagate.

---

### 2.5 MEDIUM: Inconsistent Rate Limiting

| Endpoint | Rate Limit | Auth Required |
|----------|-----------|---------------|
| `GET /topics` | **None** | **No** |
| `POST /topics/rank` | 10/min | Yes |
| `POST /topics/persist` | 5/min | Yes |
| `GET /research/sessions` | 30/min | Yes |
| `GET /articles` | **Not checked** | Yes |

**Fix**: Apply consistent rate limiting to all public and list endpoints.

---

## 3. Architecture & Code Quality

### 3.1 CRITICAL: File Size Violations (CLAUDE.md: max 200 lines)

| File | Lines | Over By |
|------|-------|---------|
| `src/db/repositories.py` | 541 | 341 (2.7x) |
| `src/api/main.py` | 524 | 324 (2.6x) |
| `src/services/content.py` | 357 | 157 (1.8x) |
| `src/services/topic_ranking.py` | 278 | 78 (1.4x) |
| `src/services/milvus_service.py` | 268 | 68 (1.3x) |
| `src/services/research.py` | 239 | 39 (1.2x) |

**Impact**: Large files are harder to navigate, test, and review. `repositories.py` at 541 lines should be split by domain (TopicRepo, SessionRepo, ArticleRepo).

---

### 3.2 CRITICAL: Function Length Violations (CLAUDE.md: max 20 lines)

| Function | File:Line | Lines |
|----------|-----------|-------|
| `build_graph()` | `agents/research/orchestrator.py:178` | 162 |
| `generate_full_article()` | `services/content.py:94` | 123 |
| `_lifespan()` | `api/main.py:122` | 96 |
| `build_content_graph()` | `agents/content/pipeline.py:116` | 82 |
| `_build_real_orchestrator()` | `api/main.py:284` | 67 |
| `fetch_and_normalize()` | Multiple trend sources | 60-65 each |
| `deduplicate()` | `services/topic_ranking.py:121` | 59 |
| 30+ additional functions | Various | 20-50 |

**Impact**: Long functions are hard to test, understand, and maintain. `generate_full_article()` at 123 lines is doing too many things.

---

### 3.3 HIGH: Redis Not Implemented Despite Architecture Docs

**Architecture states**: "Cache trend signals in Redis (TTL: 15min)", "Cache LLM responses for identical prompts"

**Reality**: Only 2 Redis references found in codebase. No Redis client initialization, no caching layer.

**Impact**: Every trend scan hits external APIs directly. No response caching. No rate limit state persistence across restarts.

---

### 3.4 HIGH: `main.py` Is a God File (524 lines, Mixed Concerns)

**File**: `src/api/main.py` contains:
- Service initialization (lines 88-118)
- Repository setup (lines 144-200+)
- LLM builder functions (lines 273-350)
- Exception handlers (lines 399-452)
- Router registration (lines 474-510)
- Dev user seeding (lines 246-270)

**Fix**: Extract into `src/api/deps.py` (service wiring), `src/api/exceptions.py` (handlers), `src/api/startup.py` (lifespan).

---

### 3.5 MEDIUM: Trend Source Code Duplication

Five trend source files (141-191 lines each) duplicate identical patterns:
- `fetch_and_normalize()` structure
- `map_to_raw_topic()` mapping
- Score calculation logic
- Keyword filtering

**Fix**: Extract shared logic into base class or mixin leveraging the `TrendSource` protocol from ARCH-002.

---

### 3.6 MEDIUM: `type: ignore` Comments Accumulating

| File | Count | Example |
|------|-------|---------|
| `api/main.py` | 5+ | `# type: ignore[no-any-return]` |
| `api/routers/canonical_articles.py` | 2 | `# type: ignore[no-any-return]` |
| `api/routers/research.py` | 3 | `# type: ignore[union-attr]` |
| `agents/content/nodes.py` | 8 | `# noqa: ANN401` (Any type) |

**Impact**: Violates CLAUDE.md "no Any types" rule. Hides type-safety issues that could cause runtime errors.

---

## 4. Async & Performance Issues

### 4.1 HIGH: Synchronous JSON Parsing in Async Context

**Files**:
- `src/services/serpapi_client.py:71` — `resp.json()`
- `src/services/trends/hackernews_client.py:62` — `resp.json()`
- `src/services/trends/newsapi_client.py:74` — `resp.json()`
- `src/services/semantic_scholar.py:88` — `resp.json()`

**Note**: If using `httpx.AsyncClient`, `.json()` is actually synchronous CPU work (JSON parsing). For large responses, this blocks the event loop.

---

### 4.2 HIGH: Milvus Sync I/O in Async Service

**File**: `src/services/milvus_service.py:1-268`

pymilvus operations are synchronous but called from async service methods without `run_in_executor()`. Large vector operations block the event loop.

---

### 4.3 MEDIUM: CPU-Bound Ranking in Main Thread

**File**: `src/services/topic_ranking.py:188-230`

`calculate_scores()` and `rank_and_deduplicate()` perform CPU-intensive operations (cosine similarity, sorting) directly in the async handler. Should be offloaded to a thread pool.

---

## 5. Frontend Issues

### 5.1 HIGH: No Error Boundaries

No `error.tsx` or ErrorBoundary components found in `frontend/src/`. Any React component crash takes down the entire page.

**Fix**: Add error boundaries at route and section level.

---

### 5.2 MEDIUM: Stale Data in Domain Selector

**File**: `frontend/src/hooks/use-topic-discovery.ts:17-27`

Domains loaded on mount with no refresh mechanism. If domains are added/removed in Settings, the Topics page shows stale data until full page reload.

---

### 5.3 MEDIUM: Missing Loading States

**File**: `frontend/src/hooks/use-topic-discovery.ts:20-27`

Domain fetching has no loading state or error feedback. User sees empty dropdown with no indication that data is loading.

---

### 5.4 LOW: Large Mock Data Files

**File**: `frontend/src/lib/mock/topics.ts` (389 lines)

Verify no production code imports from `@/lib/mock/*`. These should only be used in tests.

---

## 6. Dependency & Configuration

### 6.1 MEDIUM: Loose Version Pinning

**File**: `pyproject.toml:10-34`

Uses `>=` version specs throughout (e.g., `fastapi>=0.115.0`). A minor FastAPI update could introduce breaking changes.

**Fix**: Use `~=` (compatible release) or lock file for deterministic builds.

---

### 6.2 LOW: Unsafe `request.app.state` Access

**File**: `src/api/routers/canonical_articles.py:55`

```python
repo = request.app.state.article_repo  # AttributeError if not initialized
```

Some routers use `hasattr()` checks, others don't. Inconsistent pattern.

---

## 7. Recommendations (Priority Order)

### Immediate (Before Production)

| # | Issue | Files | Effort |
|---|-------|-------|--------|
| 1 | Add `pool_pre_ping=True` to engine | `src/db/engine.py` | 1 line |
| 2 | Add auth to `/topics` list endpoint | `src/api/routers/topics.py` | 1 line |
| 3 | Add pagination validation to `/topics` and `/articles` | 2 router files | 4 lines |
| 4 | Add UUID try/except in all routers | 5 router files | ~20 lines |
| 5 | Replace bare `except Exception` with specific types | `main.py`, `topics.py` | ~10 lines |

### Short-Term (Next Sprint)

| # | Issue | Files | Effort |
|---|-------|-------|--------|
| 6 | Batch topic persistence writes | `topic_persistence.py` | 1-2 hours |
| 7 | Vectorize cosine similarity | `topic_persistence.py` | 1 hour |
| 8 | Add eager loading for session+steps | `repositories.py` | 30 min |
| 9 | Split `repositories.py` (541 lines) | New domain repo files | 2-3 hours |
| 10 | Split `main.py` (524 lines) | New startup/deps files | 2-3 hours |
| 11 | Add frontend error boundaries | `frontend/src/app/` | 1 hour |

### Medium-Term (Next 2 Sprints)

| # | Issue | Files | Effort |
|---|-------|-------|--------|
| 12 | Implement Redis caching layer | New service + config | 1-2 days |
| 13 | Wrap Milvus calls in `run_in_executor` | `milvus_service.py` | 2-3 hours |
| 14 | Refactor long functions (30+) | Multiple agent/service files | 2-3 days |
| 15 | Eliminate `type: ignore` comments | Multiple files | 1-2 days |
| 16 | Extract trend source duplication | Trend source files + base class | 1 day |
| 17 | Add window function pagination | `repositories.py` | 2-3 hours |
| 18 | Pin dependency versions | `pyproject.toml` | 30 min |

---

## 8. Positive Observations

- **Zero SQL injection risks**: All queries use SQLAlchemy ORM with parameterized queries
- **Clean repository pattern**: Consistent abstraction layer between services and database
- **Good test coverage**: ~764 backend + 237 frontend tests, ~98% coverage
- **Proper async session config**: `expire_on_commit=False` correctly set
- **Good index coverage**: Most queried columns have indexes
- **Structured logging**: structlog used consistently with correlation IDs
- **Good pagination**: All list endpoints implement offset/limit (just need validation)
- **Auth infrastructure solid**: JWT + RBAC properly implemented on most endpoints
