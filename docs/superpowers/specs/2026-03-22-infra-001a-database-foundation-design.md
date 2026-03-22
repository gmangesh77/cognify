# INFRA-001a: Database Foundation — Design Specification

> **Date**: 2026-03-22
> **Status**: Draft
> **Ticket**: INFRA-001 (part a)
> **Epic**: 9 — Infrastructure & Integration

---

## 1. Overview

Replace all in-memory repository stubs with PostgreSQL-backed implementations. Introduces SQLAlchemy async models, Alembic migrations, Docker Compose for local dev, and PostgreSQL repository classes that implement the existing protocol interfaces. No changes to Pydantic domain models or service layer — only the storage layer changes.

**Scope:** 4 domain repositories (topics, research sessions, agent steps, article drafts, canonical articles). Auth repositories (users, refresh tokens) deferred to a separate ticket.

---

## 2. Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Async driver | `asyncpg` | Fastest async PG driver, established choice for FastAPI + SQLAlchemy async |
| Nested model storage | Hybrid — relational for top-level entities, JSONB for nested sub-documents | Top-level entities have clear FK relationships; nested structures (outline, section_drafts, seo, citations) are document-like and change together |
| Auth tables | Deferred | Auth works fine in-memory for dev; different concern (security). Focus on content pipeline data. |
| Table models location | Single file `src/db/tables.py` | 5 tables, ~150 lines total. Split later if needed. |
| Repository location | Single file `src/db/repositories.py` | 5 repo classes, ~180 lines total. Split later if needed. |
| Test strategy | Real PostgreSQL via testcontainers for repo tests; existing unit tests unchanged (keep in-memory fixtures) | Integration-level confidence for persistence; no disruption to existing test suite |

---

## 3. Dependencies

Add to `pyproject.toml`:

```
"sqlalchemy[asyncio]>=2.0",
"asyncpg>=0.29",
"alembic>=1.13",
```

Dev dependency:

```
"testcontainers[postgres]>=4.0",
```

---

## 4. Docker Compose

**New file: `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: cognify
      POSTGRES_PASSWORD: cognify
      POSTGRES_DB: cognify
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cognify"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

Minimal — just PostgreSQL. Milvus and Redis can be added later.

---

## 5. Settings Update

Add to `src/config/settings.py`:

```python
# Database (empty = in-memory repos for dev/test; set via COGNIFY_DATABASE_URL in .env)
database_url: str = ""
```

For local dev with Docker Compose, add to `.env`:
```
COGNIFY_DATABASE_URL=postgresql+asyncpg://cognify:cognify@localhost:5432/cognify
```

---

## 6. Database Module

### 6.1 `src/db/__init__.py`

Empty init file.

### 6.2 `src/db/engine.py` (~30 lines)

- `create_async_engine(database_url)` — returns SQLAlchemy `AsyncEngine`
- `get_session_factory(engine)` — returns `async_sessionmaker[AsyncSession]`
- Both are thin wrappers over SQLAlchemy's async API

### 6.3 `src/db/base.py` (~20 lines)

- `Base` — SQLAlchemy `DeclarativeBase`
- `UUIDMixin` — mixin with `id: Mapped[UUID]` primary key (server-default `gen_random_uuid()`)
- `TimestampMixin` — mixin with `created_at: Mapped[datetime]`, `updated_at: Mapped[datetime]` (server-default `now()`, on-update `now()`)

---

## 7. SQLAlchemy Table Models

### 7.1 `src/db/tables.py` (~150 lines)

5 tables, all using `UUIDMixin` + `TimestampMixin`:

#### `TopicRow`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| title | String(500) | NOT NULL |
| description | Text | default "" |
| source | String(50) | NOT NULL (e.g., "hackernews") |
| external_url | String(2000) | default "" |
| trend_score | Float | NOT NULL, 0-100 |
| velocity | Float | default 0 |
| domain | String(100) | NOT NULL |
| discovered_at | DateTime(tz) | NOT NULL |
| domain_keywords | JSONB | list[str] |
| composite_score | Float | nullable, set after ranking |
| rank | Integer | nullable |
| source_count | Integer | default 1 |

#### `ResearchSessionRow`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| topic_id | UUID | FK → topics.id, nullable |
| status | String(20) | NOT NULL |
| round_count | Integer | default 0 |
| findings_count | Integer | default 0 |
| indexed_count | Integer | default 0 |
| topic_title | String(500) | NOT NULL |
| topic_description | Text | default "" |
| topic_domain | String(100) | default "" |
| duration_seconds | Float | nullable |
| started_at | DateTime(tz) | NOT NULL |
| completed_at | DateTime(tz) | nullable |
| agent_plan | JSONB | nullable |
| findings_data | JSONB | nullable |

**Relationship:** `steps` → `AgentStepRow` (one-to-many)

#### `AgentStepRow`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| session_id | UUID | FK → research_sessions.id, NOT NULL |
| step_name | String(100) | NOT NULL |
| status | String(20) | NOT NULL |
| duration_ms | Integer | nullable |
| started_at | DateTime(tz) | NOT NULL |
| completed_at | DateTime(tz) | nullable |
| input_data | JSONB | default {} |
| output_data | JSONB | default {} |

#### `ArticleDraftRow`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| session_id | UUID | FK → research_sessions.id, NOT NULL |
| topic_id | UUID | FK → topics.id, NOT NULL |
| status | String(30) | NOT NULL (DraftStatus enum value) |
| total_word_count | Integer | default 0 |
| references_markdown | Text | default "" |
| completed_at | DateTime(tz) | nullable |
| article_id | UUID | FK → canonical_articles.id, nullable |
| outline | JSONB | nullable (serialized ArticleOutline) |
| section_drafts | JSONB | default [] (serialized list[SectionDraft]) |
| citations | JSONB | default [] (serialized list[CitationRef]) |
| seo_result | JSONB | nullable (serialized SEOResult) |
| global_citations | JSONB | default [] |
| visuals | JSONB | default [] (serialized list[ImageAsset]) |

#### `CanonicalArticleRow`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| title | String(500) | NOT NULL |
| subtitle | String(500) | nullable |
| body_markdown | Text | NOT NULL |
| summary | String(500) | NOT NULL |
| content_type | String(20) | NOT NULL |
| domain | String(100) | NOT NULL |
| ai_generated | Boolean | default True |
| generated_at | DateTime(tz) | NOT NULL |
| key_claims | JSONB | default [] |
| seo | JSONB | NOT NULL (serialized SEOMetadata) |
| citations | JSONB | default [] (serialized list[Citation]) |
| visuals | JSONB | default [] (serialized list[ImageAsset]) |
| provenance | JSONB | NOT NULL (serialized Provenance) |
| authors | JSONB | default [] (list[str]) |

---

## 8. PostgreSQL Repository Implementations

### 8.1 `src/db/repositories.py` (~180 lines)

Each class implements the corresponding protocol from `src/services/research.py` or `src/services/content_repositories.py`. Each takes `async_sessionmaker` as constructor arg.

**Conversion pattern:**
- `_row_to_model(row: TableRow) -> PydanticModel` — constructs Pydantic model from row columns, deserializing JSONB fields
- `_model_to_dict(model: PydanticModel) -> dict` — serializes Pydantic model to column dict, converting nested models to dicts for JSONB

#### `PgTopicRepository` (implements `TopicRepository`)
- `exists(topic_id)` — `SELECT 1 FROM topics WHERE id = ?`
- `get(topic_id)` — `SELECT * FROM topics WHERE id = ?`, returns `TopicInput` (matching current protocol)
- `seed(topic)` — alias for create (backward compat with in-memory `seed()` method, not part of protocol)
- `create(topic)` — INSERT (not part of current protocol — extra method, protocols allow this)

**Note on TopicRepository protocol:** The current protocol only defines `exists()` and `get()`, returning `TopicInput` (4 fields: id, title, description, domain). The `PgTopicRepository` stores more columns (trend_score, velocity, source, etc.) from the full `TopicRow`, but `get()` returns the subset as `TopicInput` to satisfy the protocol. The `create()` method accepts a dict or extended model — the exact input type will be defined when INFRA-001b wires the scan-to-persist flow. For now, `seed()` takes `TopicInput` for backward compat with tests.

#### `PgResearchSessionRepository` (implements `ResearchSessionRepository`)
- `create(session)` — INSERT
- `get(session_id)` — SELECT by id
- `update(session)` — UPDATE by id
- `list(status, page, size)` — SELECT with optional status filter, LIMIT/OFFSET, returns `(list, total_count)`

#### `PgAgentStepRepository` (implements `AgentStepRepository`)
- `create(step)` — INSERT
- `update(step)` — UPDATE by id
- `list_by_session(session_id)` — SELECT WHERE session_id = ? ORDER BY started_at

#### `PgArticleDraftRepository` (implements `ArticleDraftRepository`)
- `create(draft)` — INSERT
- `get(draft_id)` — SELECT by id
- `update(draft)` — UPDATE by id (full row replace)

#### `PgArticleRepository` (implements `ArticleRepository`)
- `create(article)` — INSERT
- `get(article_id)` — SELECT by id

---

## 9. App Startup Wiring

### 9.1 Modified: `src/api/main.py`

**Lifespan handler** — create async engine on startup, dispose on shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(app.state.settings.database_url)
    app.state.engine = engine
    app.state.async_session = get_session_factory(engine)
    yield
    await engine.dispose()
```

**Repository swap:**

```python
# Research repos
session_factory = app.state.async_session
repos = ResearchRepositories(
    sessions=PgResearchSessionRepository(session_factory),
    steps=PgAgentStepRepository(session_factory),
    topics=PgTopicRepository(session_factory),
)

# Content repos
content_repos = ContentRepositories(
    drafts=PgArticleDraftRepository(session_factory),
    research=PgResearchSessionRepository(session_factory),  # implements ResearchSessionReader too
    articles=PgArticleRepository(session_factory),
)
```

**Fallback:** If `database_url` is empty string, fall back to in-memory repos. The default `database_url` in Settings is `""` (empty) — only set to a real PostgreSQL URL via `.env` or environment variable. This keeps `uv run pytest` working without Docker, since `Settings()` with no env vars produces empty `database_url` → in-memory repos.

**Note:** `PgResearchSessionRepository` also satisfies `ResearchSessionReader` (from content_repositories.py) since `ResearchSessionReader` only requires `get()`, which is a subset.

---

## 10. Alembic Setup

- `alembic/` directory with `env.py` configured for async (uses `run_async`)
- `alembic.ini` reads `database_url` from environment
- Initial migration auto-generated from `Base.metadata`
- Migration creates all 5 tables with indexes on: `topics.domain`, `research_sessions.status`, `research_sessions.topic_id`, `agent_steps.session_id`, `article_drafts.session_id`

---

## 11. Testing

### 11.1 New Repository Tests

**`tests/integration/db/test_pg_repositories.py`** (~120 lines)

Uses `testcontainers` to spin up a PostgreSQL instance. Tests:
- Topic CRUD: create, get, exists, list
- Research session CRUD: create, get, update, list with status filter, pagination
- Agent step CRUD: create, update, list_by_session
- Article draft CRUD: create, get, update (with JSONB fields round-tripping correctly)
- Canonical article CRUD: create, get (with all JSONB fields)
- Foreign key relationships: session → topic, step → session, draft → session

### 11.2 Existing Tests Unchanged

All existing unit tests continue to use in-memory repos. The fallback logic in `create_app` ensures tests without Docker still work.

### 11.3 Coverage Target

≥80% on new `src/db/` files.

---

## 12. File Summary

| File | Type | ~Lines |
|------|------|--------|
| `docker-compose.yml` | New — Docker config | ~20 |
| `src/db/__init__.py` | New — package init | ~1 |
| `src/db/engine.py` | New — async engine setup | ~30 |
| `src/db/base.py` | New — DeclarativeBase + mixins | ~20 |
| `src/db/tables.py` | New — 5 SQLAlchemy table models | ~150 |
| `src/db/repositories.py` | New — 5 PG repository classes | ~180 |
| `src/config/settings.py` | Modified — add database_url | +2 |
| `src/api/main.py` | Modified — lifespan + repo swap | +30 |
| `alembic/` | New — migration config + initial migration | ~50 |
| `pyproject.toml` | Modified — add deps | +4 |
| `tests/integration/db/test_pg_repositories.py` | New — integration tests | ~120 |
| **Total** | | **~610** |

---

## 13. Backlog AC Split

INFRA-001 was split into 001a (this spec) and 001b. The backlog acceptance criteria are distributed:

| Backlog AC | Covered In |
|-----------|-----------|
| SQLAlchemy models for all entities | **001a** (this spec) |
| PostgreSQL-backed repository implementations | **001a** (this spec) |
| Alembic migrations | **001a** (this spec) |
| Docker Compose with PostgreSQL 16 | **001a** (this spec) |
| All existing tests continue to pass | **001a** (this spec) |
| TopicRepository persists from scan flow | 001b |
| Cross-scan dedup (upsert-by-similarity) | 001b |
| Replace MemorySaver with PostgresSaver | N/A — exploration found MemorySaver is not used; steps tracked via AgentStepRepository |

Both 001a and 001b must be complete to fully satisfy the INFRA-001 backlog entry.

---

## 14. What This Does NOT Cover

| Item | Covered In |
|------|-----------|
| Topic persistence from scan flow (wire `/trends/fetch` → save) | INFRA-001b |
| Cross-scan dedup (upsert-by-similarity) | INFRA-001b |
| `GET /topics` list endpoint | INFRA-001b |
| Auth tables (users, refresh_tokens) | Separate ticket |
| Settings/domain config tables | Separate ticket |
| Frontend-backend integration | INFRA-002 |
