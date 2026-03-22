# INFRA-001a: Database Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all in-memory repository stubs with PostgreSQL-backed implementations using SQLAlchemy async, Alembic migrations, and Docker Compose.

**Architecture:** SQLAlchemy async models mirror existing Pydantic domain models. Hybrid storage: relational for top-level entities, JSONB for nested sub-documents. Repository classes implement existing protocol interfaces — no changes to Pydantic models or service layer. Fallback to in-memory repos when `database_url` is empty (tests without Docker).

**Tech Stack:** SQLAlchemy 2.0 (async), asyncpg, Alembic, PostgreSQL 16, Docker Compose, testcontainers

**Spec:** `docs/superpowers/specs/2026-03-22-infra-001a-database-foundation-design.md`

**Worktree:** `D:/Workbench/github/cognify-infra-001` on branch `feature/INFRA-001-postgresql-persistence`

---

## File Structure

### New Files

| File | Responsibility | ~Lines |
|------|---------------|--------|
| `docker-compose.yml` | PostgreSQL 16 service for local dev | ~20 |
| `src/db/__init__.py` | Package init | ~1 |
| `src/db/engine.py` | Async engine + session factory | ~35 |
| `src/db/base.py` | DeclarativeBase + UUID/Timestamp mixins | ~30 |
| `src/db/tables.py` | 5 SQLAlchemy table models | ~160 |
| `src/db/repositories.py` | 5 PG repository implementations | ~200 |
| `alembic.ini` | Alembic configuration | ~15 |
| `alembic/env.py` | Async migration environment | ~40 |
| `alembic/script.py.mako` | Migration template | ~15 |
| `alembic/versions/` | Auto-generated initial migration | ~80 |
| `tests/integration/db/__init__.py` | Test package init | ~1 |
| `tests/integration/db/test_pg_repositories.py` | Repository integration tests | ~150 |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add sqlalchemy, asyncpg, alembic, testcontainers deps |
| `src/config/settings.py` | Add `database_url` setting |
| `src/api/main.py` | Add lifespan handler, conditional repo swap |

---

## Task 1: Dependencies, Settings, Docker Compose

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/config/settings.py`
- Create: `docker-compose.yml`

- [ ] **Step 1: Add dependencies to pyproject.toml**

Add to `dependencies`:
```
"sqlalchemy[asyncio]>=2.0",
"asyncpg>=0.29",
"alembic>=1.13",
```

Add to `[dependency-groups]` dev section:
```
"testcontainers[postgres]>=4.0",
```

- [ ] **Step 2: Add database_url to Settings**

In `src/config/settings.py`, after `embedding_version` (line 83), add:

```python
    # Database (empty = in-memory repos; set via COGNIFY_DATABASE_URL)
    database_url: str = ""
```

- [ ] **Step 3: Create docker-compose.yml**

Create `docker-compose.yml` at project root:

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

- [ ] **Step 4: Create .env with database URL**

Create `.env` at project root (if not exists, append if exists):

```
COGNIFY_DATABASE_URL=postgresql+asyncpg://cognify:cognify@localhost:5432/cognify
```

Verify `.env` is in `.gitignore`.

- [ ] **Step 5: Install dependencies**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv sync --dev`

- [ ] **Step 6: Verify imports**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv run python -c "import sqlalchemy; import asyncpg; import alembic; print('OK')"`

- [ ] **Step 7: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001
git add pyproject.toml uv.lock src/config/settings.py docker-compose.yml
git commit -m "chore(infra-001): add SQLAlchemy, asyncpg, Alembic deps and Docker Compose"
```

---

## Task 2: Database Engine and Base

**Files:**
- Create: `src/db/__init__.py`
- Create: `src/db/engine.py`
- Create: `src/db/base.py`

- [ ] **Step 1: Create package init**

Create `src/db/__init__.py`:

```python
"""Database layer — SQLAlchemy async engine, table models, repositories."""
```

- [ ] **Step 2: Create engine.py**

Create `src/db/engine.py`:

```python
"""Async SQLAlchemy engine and session factory."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_engine,
)


def create_async_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    return _create_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )


def get_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the engine."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
```

- [ ] **Step 3: Create base.py**

Create `src/db/base.py`:

```python
"""SQLAlchemy declarative base with common mixins."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class UUIDMixin:
    """Mixin adding a UUID primary key."""

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )


class TimestampMixin:
    """Mixin adding created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 4: Verify imports**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv run python -c "from src.db.engine import create_async_engine, get_session_factory; from src.db.base import Base, UUIDMixin, TimestampMixin; print('OK')"`

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001
git add src/db/
git commit -m "feat(infra-001): add async engine, session factory, and base mixins"
```

---

## Task 3: SQLAlchemy Table Models

**Files:**
- Create: `src/db/tables.py`

- [ ] **Step 1: Create tables.py with all 5 table models**

Create `src/db/tables.py`:

```python
"""SQLAlchemy table models for PostgreSQL persistence."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin


class TopicRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "topics"

    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(50))
    external_url: Mapped[str] = mapped_column(String(2000), default="")
    trend_score: Mapped[float] = mapped_column(Float)
    velocity: Mapped[float] = mapped_column(Float, default=0.0)
    domain: Mapped[str] = mapped_column(String(100), index=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )
    domain_keywords: Mapped[dict] = mapped_column(JSONB, default=list)
    composite_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, default=1)


class ResearchSessionRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "research_sessions"

    topic_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("topics.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="planning", index=True,
    )
    round_count: Mapped[int] = mapped_column(Integer, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_count: Mapped[int] = mapped_column(Integer, default=0)
    topic_title: Mapped[str] = mapped_column(String(500))
    topic_description: Mapped[str] = mapped_column(Text, default="")
    topic_domain: Mapped[str] = mapped_column(String(100), default="")
    duration_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    agent_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    findings_data: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    steps: Mapped[list["AgentStepRow"]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
    )


class AgentStepRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_steps"

    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("research_sessions.id"),
        index=True,
    )
    step_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    session: Mapped["ResearchSessionRow"] = relationship(
        back_populates="steps",
    )


class ArticleDraftRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "article_drafts"

    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("research_sessions.id"),
        index=True,
    )
    topic_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("topics.id"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30))
    total_word_count: Mapped[int] = mapped_column(Integer, default=0)
    references_markdown: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    article_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_articles.id"),
        nullable=True,
    )
    outline: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    section_drafts: Mapped[list] = mapped_column(JSONB, default=list)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    seo_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    global_citations: Mapped[list] = mapped_column(JSONB, default=list)
    visuals: Mapped[list] = mapped_column(JSONB, default=list)


class CanonicalArticleRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "canonical_articles"

    title: Mapped[str] = mapped_column(String(500))
    subtitle: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    body_markdown: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(20))
    domain: Mapped[str] = mapped_column(String(100))
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )
    key_claims: Mapped[list] = mapped_column(JSONB, default=list)
    seo: Mapped[dict] = mapped_column(JSONB)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    visuals: Mapped[list] = mapped_column(JSONB, default=list)
    provenance: Mapped[dict] = mapped_column(JSONB)
    authors: Mapped[list] = mapped_column(JSONB, default=list)
```

- [ ] **Step 2: Verify models import and metadata**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv run python -c "from src.db.tables import TopicRow, ResearchSessionRow, AgentStepRow, ArticleDraftRow, CanonicalArticleRow; from src.db.base import Base; print(f'{len(Base.metadata.tables)} tables: {list(Base.metadata.tables.keys())}')"`

Expected: `5 tables: ['topics', 'research_sessions', 'agent_steps', 'article_drafts', 'canonical_articles']`

- [ ] **Step 3: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001
git add src/db/tables.py
git commit -m "feat(infra-001): add SQLAlchemy table models for all 5 entities"
```

---

## Task 4: Alembic Setup and Initial Migration

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/` (auto-generated)

- [ ] **Step 1: Initialize Alembic**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv run alembic init alembic`

This creates `alembic.ini` and `alembic/` directory.

- [ ] **Step 2: Configure alembic.ini**

In `alembic.ini`, set:
```ini
sqlalchemy.url = postgresql+asyncpg://cognify:cognify@localhost:5432/cognify
```

Note: This is the default. Production uses env var override.

- [ ] **Step 3: Replace alembic/env.py with async version**

Replace `alembic/env.py` with:

```python
"""Alembic async migration environment."""

import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import all models so metadata is populated
from src.db.base import Base
from src.db import tables  # noqa: F401

target_metadata = Base.metadata


def get_url() -> str:
    return os.environ.get(
        "COGNIFY_DATABASE_URL",
        "postgresql+asyncpg://cognify:cognify@localhost:5432/cognify",
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(get_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Generate initial migration**

Start PostgreSQL first:
```bash
cd D:/Workbench/github/cognify-infra-001 && docker compose up -d postgres
```

Wait for healthy, then generate:
```bash
cd D:/Workbench/github/cognify-infra-001 && uv run alembic revision --autogenerate -m "initial tables"
```

- [ ] **Step 5: Run the migration**

```bash
cd D:/Workbench/github/cognify-infra-001 && uv run alembic upgrade head
```

Verify tables created:
```bash
docker exec -it $(docker compose ps -q postgres) psql -U cognify -c "\dt"
```

Expected: 5 tables + alembic_version.

- [ ] **Step 6: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001
git add alembic.ini alembic/
git commit -m "feat(infra-001): add Alembic async setup with initial migration"
```

---

## Task 5: PostgreSQL Repository Implementations

**Files:**
- Create: `src/db/repositories.py`

- [ ] **Step 1: Create repositories.py**

Create `src/db/repositories.py`:

```python
"""PostgreSQL repository implementations.

Each class implements an existing protocol from src/services/ and
converts between SQLAlchemy rows and Pydantic domain models.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables import (
    AgentStepRow,
    ArticleDraftRow,
    CanonicalArticleRow,
    ResearchSessionRow,
    TopicRow,
)
from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft
from src.models.research import TopicInput
from src.models.research_db import AgentStep, ResearchSession


class PgTopicRepository:
    """PostgreSQL implementation of TopicRepository protocol."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def exists(self, topic_id: UUID) -> bool:
        async with self._session_factory() as session:
            row = await session.get(TopicRow, topic_id)
            return row is not None

    async def get(self, topic_id: UUID) -> TopicInput | None:
        async with self._session_factory() as session:
            row = await session.get(TopicRow, topic_id)
            if row is None:
                return None
            return TopicInput(
                id=row.id,
                title=row.title,
                description=row.description,
                domain=row.domain,
            )

    def seed(self, topic: TopicInput) -> None:
        """Sync seed for backward compat with tests. No-op for PG (use _seed_async)."""
        # PG seed requires async context; tests should use _seed_async directly
        pass

    async def _seed_async(self, topic: TopicInput) -> None:
        """Async seed for integration tests."""
        from datetime import UTC, datetime as dt
        async with self._session_factory() as session:
            row = TopicRow(
                id=topic.id,
                title=topic.title,
                description=topic.description,
                source="seed",
                domain=topic.domain,
                trend_score=0.0,
                discovered_at=dt.now(UTC),
            )
            session.add(row)
            await session.commit()


class PgResearchSessionRepository:
    """PostgreSQL implementation of ResearchSessionRepository."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, s: ResearchSession) -> ResearchSession:
        async with self._sf() as session:
            row = ResearchSessionRow(
                id=s.id, topic_id=s.topic_id, status=s.status,
                round_count=s.round_count, findings_count=s.findings_count,
                indexed_count=s.indexed_count, topic_title=s.topic_title,
                topic_description=s.topic_description,
                topic_domain=s.topic_domain,
                duration_seconds=s.duration_seconds,
                started_at=s.started_at, completed_at=s.completed_at,
                agent_plan=s.agent_plan, findings_data=s.findings_data,
            )
            session.add(row)
            await session.commit()
            return s

    async def get(self, session_id: UUID) -> ResearchSession | None:
        async with self._sf() as session:
            row = await session.get(ResearchSessionRow, session_id)
            if row is None:
                return None
            return self._to_model(row)

    async def update(self, s: ResearchSession) -> ResearchSession:
        async with self._sf() as session:
            row = await session.get(ResearchSessionRow, s.id)
            if row is None:
                return s
            for field in (
                "status", "round_count", "findings_count",
                "indexed_count", "duration_seconds", "completed_at",
                "agent_plan", "findings_data",
                "topic_title", "topic_description", "topic_domain",
            ):
                setattr(row, field, getattr(s, field))
            await session.commit()
            return s

    async def list(
        self, status: str | None, page: int, size: int,
    ) -> tuple[list[ResearchSession], int]:
        async with self._sf() as session:
            q = select(ResearchSessionRow)
            count_q = select(func.count()).select_from(
                ResearchSessionRow,
            )
            if status:
                q = q.where(ResearchSessionRow.status == status)
                count_q = count_q.where(
                    ResearchSessionRow.status == status,
                )
            total = (await session.execute(count_q)).scalar_one()
            q = q.offset((page - 1) * size).limit(size)
            rows = (await session.execute(q)).scalars().all()
            return [self._to_model(r) for r in rows], total

    @staticmethod
    def _to_model(row: ResearchSessionRow) -> ResearchSession:
        return ResearchSession(
            id=row.id, topic_id=row.topic_id, status=row.status,
            round_count=row.round_count,
            findings_count=row.findings_count,
            indexed_count=row.indexed_count,
            topic_title=row.topic_title,
            topic_description=row.topic_description,
            topic_domain=row.topic_domain,
            duration_seconds=row.duration_seconds,
            started_at=row.started_at,
            completed_at=row.completed_at,
            agent_plan=row.agent_plan or {},
            findings_data=row.findings_data or [],
        )


class PgAgentStepRepository:
    """PostgreSQL implementation of AgentStepRepository."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, step: AgentStep) -> AgentStep:
        async with self._sf() as session:
            row = AgentStepRow(
                id=step.id, session_id=step.session_id,
                step_name=step.step_name, status=step.status,
                duration_ms=step.duration_ms,
                started_at=step.started_at,
                completed_at=step.completed_at,
                input_data=step.input_data,
                output_data=step.output_data,
            )
            session.add(row)
            await session.commit()
            return step

    async def update(self, step: AgentStep) -> AgentStep:
        async with self._sf() as session:
            row = await session.get(AgentStepRow, step.id)
            if row is None:
                return step
            for field in (
                "status", "duration_ms", "completed_at",
                "output_data",
            ):
                setattr(row, field, getattr(step, field))
            await session.commit()
            return step

    async def list_by_session(
        self, session_id: UUID,
    ) -> list[AgentStep]:
        async with self._sf() as session:
            q = (
                select(AgentStepRow)
                .where(AgentStepRow.session_id == session_id)
                .order_by(AgentStepRow.started_at)
            )
            rows = (await session.execute(q)).scalars().all()
            return [
                AgentStep(
                    id=r.id, session_id=r.session_id,
                    step_name=r.step_name, status=r.status,
                    duration_ms=r.duration_ms,
                    started_at=r.started_at,
                    completed_at=r.completed_at,
                    input_data=r.input_data or {},
                    output_data=r.output_data or {},
                )
                for r in rows
            ]


class PgArticleDraftRepository:
    """PostgreSQL implementation of ArticleDraftRepository."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, draft: ArticleDraft) -> ArticleDraft:
        async with self._sf() as session:
            row = ArticleDraftRow(
                id=draft.id, session_id=draft.session_id,
                topic_id=draft.topic_id,
                status=draft.status.value,
                total_word_count=draft.total_word_count,
                references_markdown=draft.references_markdown,
                completed_at=draft.completed_at,
                article_id=draft.article_id,
                outline=draft.outline.model_dump() if draft.outline else None,
                section_drafts=[s.model_dump() for s in draft.section_drafts],
                citations=[c.model_dump() for c in draft.citations],
                seo_result=draft.seo_result.model_dump() if draft.seo_result else None,
                global_citations=draft.global_citations,
                visuals=[v.model_dump() for v in draft.visuals],
            )
            session.add(row)
            await session.commit()
            return draft

    async def get(self, draft_id: UUID) -> ArticleDraft | None:
        async with self._sf() as session:
            row = await session.get(ArticleDraftRow, draft_id)
            if row is None:
                return None
            return self._to_model(row)

    async def update(self, draft: ArticleDraft) -> ArticleDraft:
        async with self._sf() as session:
            row = await session.get(ArticleDraftRow, draft.id)
            if row is None:
                return draft
            row.status = draft.status.value
            row.total_word_count = draft.total_word_count
            row.references_markdown = draft.references_markdown
            row.completed_at = draft.completed_at
            row.article_id = draft.article_id
            row.outline = draft.outline.model_dump() if draft.outline else None
            row.section_drafts = [s.model_dump() for s in draft.section_drafts]
            row.citations = [c.model_dump() for c in draft.citations]
            row.seo_result = draft.seo_result.model_dump() if draft.seo_result else None
            row.global_citations = draft.global_citations
            row.visuals = [v.model_dump() for v in draft.visuals]
            await session.commit()
            return draft

    @staticmethod
    def _to_model(row: ArticleDraftRow) -> ArticleDraft:
        from src.models.content_pipeline import (
            ArticleOutline,
            DraftStatus,
            SectionDraft,
            CitationRef,
            SEOResult,
        )
        from src.models.content import ImageAsset
        return ArticleDraft(
            id=row.id, session_id=row.session_id,
            topic_id=row.topic_id,
            status=DraftStatus(row.status),
            created_at=row.created_at,
            completed_at=row.completed_at,
            total_word_count=row.total_word_count,
            references_markdown=row.references_markdown,
            article_id=row.article_id,
            outline=ArticleOutline.model_validate(row.outline) if row.outline else None,
            section_drafts=[SectionDraft.model_validate(s) for s in (row.section_drafts or [])],
            citations=[CitationRef.model_validate(c) for c in (row.citations or [])],
            seo_result=SEOResult.model_validate(row.seo_result) if row.seo_result else None,
            global_citations=row.global_citations or [],
            visuals=[ImageAsset.model_validate(v) for v in (row.visuals or [])],
        )


class PgArticleRepository:
    """PostgreSQL implementation of ArticleRepository."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(
        self, article: CanonicalArticle,
    ) -> CanonicalArticle:
        async with self._sf() as session:
            row = CanonicalArticleRow(
                id=article.id,
                title=article.title,
                subtitle=article.subtitle,
                body_markdown=article.body_markdown,
                summary=article.summary,
                content_type=article.content_type.value,
                domain=article.domain,
                ai_generated=article.ai_generated,
                generated_at=article.generated_at,
                key_claims=article.key_claims,
                seo=article.seo.model_dump(),
                citations=[c.model_dump() for c in article.citations],
                visuals=[v.model_dump() for v in article.visuals],
                provenance=article.provenance.model_dump(),
                authors=article.authors,
            )
            session.add(row)
            await session.commit()
            return article

    async def get(
        self, article_id: UUID,
    ) -> CanonicalArticle | None:
        async with self._sf() as session:
            row = await session.get(CanonicalArticleRow, article_id)
            if row is None:
                return None
            return self._to_model(row)

    @staticmethod
    def _to_model(row: CanonicalArticleRow) -> CanonicalArticle:
        from src.models.content import (
            Citation,
            ContentType,
            ImageAsset,
            Provenance,
            SEOMetadata,
        )
        return CanonicalArticle(
            id=row.id, title=row.title,
            subtitle=row.subtitle,
            body_markdown=row.body_markdown,
            summary=row.summary,
            key_claims=row.key_claims or [],
            content_type=ContentType(row.content_type),
            seo=SEOMetadata.model_validate(row.seo),
            citations=[Citation.model_validate(c) for c in (row.citations or [])],
            visuals=[ImageAsset.model_validate(v) for v in (row.visuals or [])],
            authors=row.authors or [],
            domain=row.domain,
            generated_at=row.generated_at,
            provenance=Provenance.model_validate(row.provenance),
            ai_generated=row.ai_generated,
        )
```

- [ ] **Step 2: Verify imports**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv run python -c "from src.db.repositories import PgTopicRepository, PgResearchSessionRepository, PgAgentStepRepository, PgArticleDraftRepository, PgArticleRepository; print('OK')"`

- [ ] **Step 3: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001
git add src/db/repositories.py
git commit -m "feat(infra-001): add PostgreSQL repository implementations"
```

---

## Task 6: App Startup Wiring

**Files:**
- Modify: `src/api/main.py`

- [ ] **Step 1: Add lifespan handler and conditional repo swap**

In `src/api/main.py`, add imports:

```python
from contextlib import asynccontextmanager
from src.db.engine import create_async_engine as create_db_engine, get_session_factory
from src.db.repositories import (
    PgArticleDraftRepository,
    PgArticleRepository,
    PgAgentStepRepository,
    PgResearchSessionRepository,
    PgTopicRepository,
)
```

Add lifespan handler before `create_app`. **Critical:** Repository initialization must happen inside the lifespan, not in `create_app`, because the async engine can only be created in an async context.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage async engine lifecycle and initialize repos."""
    db_url = app.state.settings.database_url
    if db_url:
        engine = create_db_engine(db_url)
        app.state.db_engine = engine
        sf = get_session_factory(engine)
        # Swap research repos to PG
        repos = ResearchRepositories(
            sessions=PgResearchSessionRepository(sf),
            steps=PgAgentStepRepository(sf),
            topics=PgTopicRepository(sf),
        )
        app.state.research_service = ResearchService(repos, NoOpOrchestrator())
        # Swap content repos to PG
        pg_session_repo = PgResearchSessionRepository(sf)
        content_repos = ContentRepositories(
            drafts=PgArticleDraftRepository(sf),
            research=pg_session_repo,
            articles=PgArticleRepository(sf),
        )
        app.state.content_repos = content_repos
        logger.info("database_connected", url=db_url.split("@")[-1])
    yield
    if hasattr(app.state, "db_engine"):
        await app.state.db_engine.dispose()
        logger.info("database_disconnected")
```

Modify `create_app` to pass `lifespan=lifespan` to `FastAPI(...)`:

```python
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)
```

Keep `_init_research_service` as-is (creates in-memory repos). The lifespan **overwrites** `app.state.research_service` with PG-backed repos when `database_url` is set. When it's empty, the in-memory repos from `_init_research_service` remain active.

**Note on ContentService:** `ContentService` is not currently initialized in `main.py`. The `content_repos` are stored on `app.state.content_repos` for use by the content API router (which creates `ContentService` per-request using `Depends`). If the content router doesn't exist yet, this line can be deferred — the important thing is that the pattern is in place.

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv run pytest tests/unit/ -q --tb=short 2>&1 | tail -5`

Expected: All existing tests pass (in-memory fallback active since `database_url` defaults to empty).

- [ ] **Step 3: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001
git add src/api/main.py
git commit -m "feat(infra-001): add lifespan handler and conditional PG/in-memory repo swap"
```

---

## Task 7: Integration Tests

**Files:**
- Create: `tests/integration/db/__init__.py`
- Create: `tests/integration/db/test_pg_repositories.py`

- [ ] **Step 1: Create test package**

Create `tests/integration/db/__init__.py` (empty file).

- [ ] **Step 2: Write repository integration tests**

Create `tests/integration/db/test_pg_repositories.py`:

```python
"""Integration tests for PostgreSQL repositories.

Requires Docker to be running. Uses testcontainers to spin up
a PostgreSQL 16 instance per test session.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.base import Base
from src.db.engine import create_async_engine, get_session_factory
from src.db.repositories import (
    PgAgentStepRepository,
    PgArticleDraftRepository,
    PgArticleRepository,
    PgResearchSessionRepository,
    PgTopicRepository,
)
from src.models.content import (
    CanonicalArticle,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
)
from src.models.content_pipeline import ArticleDraft, DraftStatus
from src.models.research import TopicInput
from src.models.research_db import AgentStep, ResearchSession

# Import tables so Base.metadata is populated
from src.db import tables  # noqa: F401


@pytest_asyncio.fixture(scope="module")
async def session_factory():
    """Create a test database using testcontainers."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url().replace(
            "psycopg2", "asyncpg",
        )
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sf = get_session_factory(engine)
        yield sf
        await engine.dispose()


async def _seed_topic(sf: async_sessionmaker[AsyncSession]) -> TopicInput:
    """Helper: create a topic row for FK references."""
    repo = PgTopicRepository(sf)
    topic = TopicInput(id=uuid4(), title="FK Topic", description="", domain="tech")
    await repo._seed_async(topic)
    return topic


async def _seed_session(
    sf: async_sessionmaker[AsyncSession], topic_id: UUID,
) -> ResearchSession:
    """Helper: create a session row for FK references."""
    repo = PgResearchSessionRepository(sf)
    s = ResearchSession(
        id=uuid4(), topic_id=topic_id, status="planning",
        topic_title="FK Session", started_at=datetime.now(UTC),
    )
    await repo.create(s)
    return s


class TestPgTopicRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(
        self, session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        repo = PgTopicRepository(session_factory)
        topic = TopicInput(
            id=uuid4(), title="Test Topic",
            description="A test", domain="tech",
        )
        await repo._seed_async(topic)
        result = await repo.get(topic.id)
        assert result is not None
        assert result.title == "Test Topic"
        assert result.domain == "tech"

    @pytest.mark.asyncio
    async def test_exists(
        self, session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        repo = PgTopicRepository(session_factory)
        topic = TopicInput(
            id=uuid4(), title="Exists Test",
            description="", domain="tech",
        )
        assert not await repo.exists(topic.id)
        await repo._seed_async(topic)
        assert await repo.exists(topic.id)


class TestPgResearchSessionRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(
        self, session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        topic = await _seed_topic(session_factory)
        repo = PgResearchSessionRepository(session_factory)
        session = ResearchSession(
            id=uuid4(), topic_id=topic.id,
            status="planning", topic_title="Test",
            started_at=datetime.now(UTC),
        )
        await repo.create(session)
        result = await repo.get(session.id)
        assert result is not None
        assert result.status == "planning"

    @pytest.mark.asyncio
    async def test_update(
        self, session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        topic = await _seed_topic(session_factory)
        repo = PgResearchSessionRepository(session_factory)
        session = ResearchSession(
            id=uuid4(), topic_id=topic.id,
            status="planning", topic_title="Update Test",
            started_at=datetime.now(UTC),
        )
        await repo.create(session)
        updated = session.model_copy(
            update={"status": "complete", "findings_count": 5},
        )
        await repo.update(updated)
        result = await repo.get(session.id)
        assert result is not None
        assert result.status == "complete"
        assert result.findings_count == 5

    @pytest.mark.asyncio
    async def test_list_with_status_filter(
        self, session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        topic = await _seed_topic(session_factory)
        repo = PgResearchSessionRepository(session_factory)
        created_ids = []
        for status in ("complete", "complete", "failed"):
            s = ResearchSession(
                id=uuid4(), topic_id=topic.id,
                status=status, topic_title=f"List {status}",
                started_at=datetime.now(UTC),
            )
            await repo.create(s)
            created_ids.append(s.id)
        items, total = await repo.list("complete", 1, 100)
        # Filter to our test items only
        our_items = [i for i in items if i.id in created_ids]
        assert len(our_items) == 2
        assert all(s.status == "complete" for s in our_items)


class TestPgAgentStepRepository:
    @pytest.mark.asyncio
    async def test_create_and_list_by_session(
        self, session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgAgentStepRepository(session_factory)
        for name in ("plan", "search", "evaluate"):
            await repo.create(
                AgentStep(
                    session_id=session.id, step_name=name,
                    started_at=datetime.now(UTC),
                ),
            )
        steps = await repo.list_by_session(session.id)
        assert len(steps) == 3
        assert {s.step_name for s in steps} == {
            "plan", "search", "evaluate",
        }


class TestPgArticleDraftRepository:
    @pytest.mark.asyncio
    async def test_create_get_update_roundtrip(
        self, session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        repo = PgArticleDraftRepository(session_factory)
        draft = ArticleDraft(
            session_id=session.id,
            topic_id=topic.id,
            status=DraftStatus.OUTLINE_GENERATING,
            created_at=datetime.now(UTC),
        )
        await repo.create(draft)
        result = await repo.get(draft.id)
        assert result is not None
        assert result.status == DraftStatus.OUTLINE_GENERATING
        # Update with JSONB fields
        updated = result.model_copy(
            update={
                "status": DraftStatus.DRAFT_COMPLETE,
                "total_word_count": 1500,
                "global_citations": [{"url": "https://example.com", "title": "Test"}],
            },
        )
        await repo.update(updated)
        final = await repo.get(draft.id)
        assert final is not None
        assert final.status == DraftStatus.DRAFT_COMPLETE
        assert final.total_word_count == 1500
        assert len(final.global_citations) == 1


class TestPgArticleRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(
        self, session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        repo = PgArticleRepository(session_factory)
        article = CanonicalArticle(
            title="Test Article",
            body_markdown="## Intro\n\nContent here.\n\n" * 100,
            summary="A test article.",
            key_claims=["Claim 1 [1]", "Claim 2 [2]"],
            content_type=ContentType.ARTICLE,
            seo=SEOMetadata(
                title="Test Article SEO",
                description="SEO description for test.",
                keywords=["test"],
            ),
            citations=[],
            visuals=[],
            authors=["Test"],
            domain="tech",
            provenance=Provenance(
                research_session_id=uuid4(),
                primary_model="test",
                drafting_model="test",
                embedding_model="test",
                embedding_version="1.0",
            ),
            ai_generated=True,
        )
        await repo.create(article)
        result = await repo.get(article.id)
        assert result is not None
        assert result.title == "Test Article"
        assert result.domain == "tech"
        assert result.provenance.primary_model == "test"
```

- [ ] **Step 3: Run integration tests (Docker must be running)**

Run: `cd D:/Workbench/github/cognify-infra-001 && docker compose up -d postgres && uv run pytest tests/integration/db/ -v 2>&1 | tail -20`

Expected: All tests pass.

- [ ] **Step 4: Run full unit test suite to verify no regressions**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv run pytest tests/unit/ -q --tb=short 2>&1 | tail -5`

Expected: All existing unit tests still pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-infra-001
git add tests/integration/db/
git commit -m "test(infra-001): add PostgreSQL repository integration tests"
```

---

## Task 8: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv run pytest tests/ -q --tb=short 2>&1 | tail -10`

Expected: All tests pass.

- [ ] **Step 2: Run linter**

Run: `cd D:/Workbench/github/cognify-infra-001 && uv tool run ruff check src/db/ 2>&1`

Expected: No errors.

- [ ] **Step 3: Verify Docker Compose up/down cycle**

```bash
cd D:/Workbench/github/cognify-infra-001
docker compose down -v
docker compose up -d postgres
uv run alembic upgrade head
docker compose down
```

Expected: Clean up/down with migrations.

- [ ] **Step 4: Fix any issues and commit**

```bash
cd D:/Workbench/github/cognify-infra-001
git add -A && git commit -m "fix(infra-001): resolve lint and test issues"
```
