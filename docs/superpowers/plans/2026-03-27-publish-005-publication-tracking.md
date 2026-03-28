# PUBLISH-005: Publication Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist every publish attempt, expose publication list/retry/summary endpoints, and build a frontend dashboard replacing the publishing placeholder page.

**Architecture:** New `publications` table with JSONB event history. `PublishingService` gains a `PgPublicationRepository` dependency to persist results after each publish. Four new API endpoints serve the frontend. Frontend gets a full publishing page with platform summary cards, filterable table, and retry capability.

**Tech Stack:** SQLAlchemy (async), Alembic, FastAPI, Pydantic, React/TypeScript, TanStack Query, Tailwind CSS

**Spec:** [`docs/superpowers/specs/2026-03-27-publish-005-publication-tracking-design.md`](../specs/2026-03-27-publish-005-publication-tracking-design.md)

---

## File Structure

### Backend (create)
- `src/db/tables.py` — add `PublicationRow` class
- `alembic/versions/xxxx_add_publications_table.py` — migration
- `src/models/publishing.py` — add `Publication`, `PublicationEvent`, `PlatformSummary` models
- `src/api/schemas/publishing.py` — add response schemas
- `tests/unit/models/test_publication_models.py` — model tests
- `tests/unit/db/test_publication_repository.py` — repository tests
- `tests/unit/services/test_publication_tracking.py` — service tests
- `tests/unit/api/test_publication_endpoints.py` — API tests

### Backend (modify)
- `src/db/repositories.py` — add `PgPublicationRepository`
- `src/services/publishing/service.py` — add `pub_repo` dependency, persist after publish, `retry()`, `compute_seo_score()`
- `src/api/routers/publishing.py` — add 4 new endpoints
- `src/api/main.py` — inject `PgPublicationRepository` into `PublishingService`

### Frontend (create)
- `frontend/src/types/publishing.ts` — TypeScript types
- `frontend/src/lib/api/publications.ts` — API client functions
- `frontend/src/hooks/use-publications.ts` — React Query hooks
- `frontend/src/components/publishing/platform-summary-card.tsx` — summary card
- `frontend/src/components/publishing/publication-filters.tsx` — filter pills
- `frontend/src/components/publishing/publications-table.tsx` — main table
- `frontend/src/components/publishing/__tests__/publications-table.test.tsx` — table tests
- `frontend/src/components/publishing/__tests__/platform-summary-card.test.tsx` — card tests
- `frontend/src/components/publishing/__tests__/publication-filters.test.tsx` — filter tests

### Frontend (modify)
- `frontend/src/app/(dashboard)/publishing/page.tsx` — replace placeholder

---

## Task 1: Publication & PublicationEvent Pydantic Models

**Files:**
- Modify: `src/models/publishing.py`
- Create: `tests/unit/models/test_publication_models.py`

- [ ] **Step 1: Write failing tests for Publication and PublicationEvent models**

```python
# tests/unit/models/test_publication_models.py
"""Tests for Publication and PublicationEvent domain models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.publishing import (
    Publication,
    PublicationEvent,
    PublicationStatus,
    PlatformSummary,
)


class TestPublicationEvent:
    def test_valid_construction(self) -> None:
        event = PublicationEvent(
            timestamp=datetime.now(UTC),
            status=PublicationStatus.FAILED,
            error_message="Connection timeout",
        )
        assert event.status == PublicationStatus.FAILED
        assert event.error_message == "Connection timeout"

    def test_success_event_no_error(self) -> None:
        event = PublicationEvent(
            timestamp=datetime.now(UTC),
            status=PublicationStatus.SUCCESS,
        )
        assert event.error_message is None

    def test_frozen(self) -> None:
        event = PublicationEvent(
            timestamp=datetime.now(UTC),
            status=PublicationStatus.SUCCESS,
        )
        with pytest.raises(Exception):
            event.status = PublicationStatus.FAILED  # type: ignore[misc]


class TestPublication:
    def _make(self, **overrides) -> Publication:
        defaults = {
            "id": uuid4(),
            "article_id": uuid4(),
            "platform": "ghost",
            "status": PublicationStatus.SUCCESS,
            "view_count": 0,
            "seo_score": 80,
            "event_history": [],
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        defaults.update(overrides)
        return Publication(**defaults)

    def test_valid_construction(self) -> None:
        pub = self._make(external_id="abc123", external_url="https://blog.example.com/post")
        assert pub.platform == "ghost"
        assert pub.seo_score == 80

    def test_defaults(self) -> None:
        pub = self._make()
        assert pub.external_id is None
        assert pub.external_url is None
        assert pub.published_at is None
        assert pub.error_message is None
        assert pub.event_history == []

    def test_frozen(self) -> None:
        pub = self._make()
        with pytest.raises(Exception):
            pub.status = PublicationStatus.FAILED  # type: ignore[misc]

    def test_with_event_history(self) -> None:
        events = [
            PublicationEvent(
                timestamp=datetime.now(UTC),
                status=PublicationStatus.FAILED,
                error_message="Timeout",
            ),
            PublicationEvent(
                timestamp=datetime.now(UTC),
                status=PublicationStatus.SUCCESS,
            ),
        ]
        pub = self._make(event_history=events)
        assert len(pub.event_history) == 2
        assert pub.event_history[0].status == PublicationStatus.FAILED

    def test_json_serialization(self) -> None:
        pub = self._make(
            event_history=[
                PublicationEvent(
                    timestamp=datetime.now(UTC),
                    status=PublicationStatus.SUCCESS,
                ),
            ],
        )
        data = pub.model_dump(mode="json")
        assert isinstance(data["event_history"], list)
        assert data["event_history"][0]["status"] == "success"


class TestPlatformSummary:
    def test_valid_construction(self) -> None:
        summary = PlatformSummary(
            platform="ghost", total=10, success=8, failed=1, scheduled=1,
        )
        assert summary.total == 10
        assert summary.success == 8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/models/test_publication_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'Publication'`

- [ ] **Step 3: Add models to src/models/publishing.py**

Add after the `PublicationResult` class (after line 46):

```python
class PublicationEvent(BaseModel, frozen=True):
    """Single event in the publication attempt history."""

    timestamp: datetime
    status: PublicationStatus
    error_message: str | None = None


class Publication(BaseModel, frozen=True):
    """Persisted publication record with event history."""

    id: UUID
    article_id: UUID
    platform: str
    status: PublicationStatus
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    view_count: int = 0
    seo_score: int = 0
    error_message: str | None = None
    event_history: list[PublicationEvent] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PlatformSummary(BaseModel, frozen=True):
    """Aggregated stats for a single platform."""

    platform: str
    total: int
    success: int
    failed: int
    scheduled: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/models/test_publication_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/models/publishing.py tests/unit/models/test_publication_models.py
git commit -m "feat: add Publication, PublicationEvent, PlatformSummary models"
```

---

## Task 2: PublicationRow SQLAlchemy Table + Migration

**Files:**
- Modify: `src/db/tables.py`
- Create: Alembic migration

- [ ] **Step 1: Add PublicationRow to src/db/tables.py**

Add `"PublicationRow"` to the `__all__` list (after `"GeneralConfigRow"`).

Add at the end of the file (after `GeneralConfigRow`):

```python
class PublicationRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "publications"

    article_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_articles.id"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seo_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_history: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    __table_args__ = (
        UniqueConstraint("article_id", "platform", name="uq_publication_article_platform"),
    )
```

Add `import uuid` at the top of `tables.py` (after the existing `from datetime import datetime`). Add `UniqueConstraint` to the SQLAlchemy imports:

```python
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
```

- [ ] **Step 2: Generate Alembic migration**

Run: `uv run alembic revision --autogenerate -m "add publications table"`
Expected: New migration file created in `alembic/versions/`

- [ ] **Step 3: Verify migration file has correct columns**

Open the generated migration and confirm it creates the `publications` table with all columns, the unique constraint, and the two indexes.

- [ ] **Step 4: Commit**

```bash
git add src/db/tables.py alembic/versions/*add_publications*.py
git commit -m "feat: add publications table and migration"
```

---

## Task 3: PgPublicationRepository

**Files:**
- Modify: `src/db/repositories.py`
- Create: `tests/unit/db/test_publication_repository.py`

- [ ] **Step 1: Write failing tests for PgPublicationRepository**

```python
# tests/unit/db/test_publication_repository.py
"""Unit tests for PgPublicationRepository using mocked sessions."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.publishing import (
    Publication,
    PublicationEvent,
    PublicationStatus,
)


@pytest.fixture
def article_id():
    return uuid4()


@pytest.fixture
def _success_publication(article_id):
    return Publication(
        id=uuid4(),
        article_id=article_id,
        platform="ghost",
        status=PublicationStatus.SUCCESS,
        external_id="ghost-123",
        external_url="https://blog.example.com/post",
        published_at=datetime.now(UTC),
        view_count=0,
        seo_score=80,
        error_message=None,
        event_history=[
            PublicationEvent(
                timestamp=datetime.now(UTC),
                status=PublicationStatus.SUCCESS,
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class TestPgPublicationRepository:
    """Tests verify repository method signatures and row conversion logic."""

    def test_to_model_converts_row(self, article_id) -> None:
        """Verify _to_model converts a row-like object to Publication."""
        from src.db.repositories import PgPublicationRepository

        row = MagicMock()
        row.id = uuid4()
        row.article_id = article_id
        row.platform = "ghost"
        row.status = "success"
        row.external_id = "g-123"
        row.external_url = "https://blog.example.com/post"
        row.published_at = datetime.now(UTC)
        row.view_count = 42
        row.seo_score = 80
        row.error_message = None
        row.event_history = [
            {"timestamp": "2026-03-27T10:00:00+00:00", "status": "success", "error_message": None},
        ]
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        pub = PgPublicationRepository._to_model(row)
        assert pub.platform == "ghost"
        assert pub.status == PublicationStatus.SUCCESS
        assert pub.view_count == 42
        assert len(pub.event_history) == 1

    def test_to_model_empty_event_history(self, article_id) -> None:
        from src.db.repositories import PgPublicationRepository

        row = MagicMock()
        row.id = uuid4()
        row.article_id = article_id
        row.platform = "medium"
        row.status = "failed"
        row.external_id = None
        row.external_url = None
        row.published_at = None
        row.view_count = 0
        row.seo_score = 60
        row.error_message = "API error"
        row.event_history = []
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        pub = PgPublicationRepository._to_model(row)
        assert pub.status == PublicationStatus.FAILED
        assert pub.event_history == []
        assert pub.error_message == "API error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/db/test_publication_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'PgPublicationRepository'`

- [ ] **Step 3: Implement PgPublicationRepository**

Add to the imports at the top of `src/db/repositories.py`:

```python
from src.db.tables import (
    AgentStepRow,
    ArticleDraftRow,
    CanonicalArticleRow,
    PublicationRow,
    ResearchSessionRow,
    TopicRow,
)
```

Add to the imports from models:

```python
from src.models.publishing import (
    Publication,
    PublicationEvent,
    PublicationStatus,
    PlatformSummary,
)
```

Add the class at the end of `src/db/repositories.py`:

```python
class PgPublicationRepository:
    """PostgreSQL-backed publication tracking repository."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, pub: Publication) -> Publication:
        async with self._sf() as db:
            row = PublicationRow(
                id=pub.id,
                article_id=pub.article_id,
                platform=pub.platform,
                status=pub.status.value,
                external_id=pub.external_id,
                external_url=pub.external_url,
                published_at=pub.published_at,
                view_count=pub.view_count,
                seo_score=pub.seo_score,
                error_message=pub.error_message,
                event_history=[e.model_dump(mode="json") for e in pub.event_history],
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    async def get(self, publication_id: UUID) -> Publication | None:
        async with self._sf() as db:
            row = await db.get(PublicationRow, publication_id)
            if row is None:
                return None
            return self._to_model(row)

    async def get_by_article_platform(
        self, article_id: UUID, platform: str,
    ) -> Publication | None:
        async with self._sf() as db:
            q = select(PublicationRow).where(
                PublicationRow.article_id == article_id,
                PublicationRow.platform == platform,
            )
            row = (await db.execute(q)).scalar_one_or_none()
            if row is None:
                return None
            return self._to_model(row)

    async def list(
        self,
        page: int = 1,
        size: int = 20,
        platform: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Publication], int]:
        async with self._sf() as db:
            base = select(PublicationRow)
            count_base = select(func.count()).select_from(PublicationRow)
            if platform:
                base = base.where(PublicationRow.platform == platform)
                count_base = count_base.where(PublicationRow.platform == platform)
            if status:
                base = base.where(PublicationRow.status == status)
                count_base = count_base.where(PublicationRow.status == status)
            total = (await db.execute(count_base)).scalar_one()
            q = base.order_by(PublicationRow.updated_at.desc()).offset(
                (page - 1) * size,
            ).limit(size)
            rows = (await db.execute(q)).scalars().all()
            return [self._to_model(r) for r in rows], total

    async def update(self, pub: Publication) -> Publication:
        async with self._sf() as db:
            row = await db.get(PublicationRow, pub.id)
            if row is None:
                msg = f"Publication {pub.id} not found"
                raise ValueError(msg)
            row.status = pub.status.value
            row.external_id = pub.external_id
            row.external_url = pub.external_url
            row.published_at = pub.published_at
            row.view_count = pub.view_count
            row.error_message = pub.error_message
            row.event_history = [e.model_dump(mode="json") for e in pub.event_history]
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    async def update_view_count(
        self, publication_id: UUID, count: int,
    ) -> None:
        async with self._sf() as db:
            row = await db.get(PublicationRow, publication_id)
            if row is not None:
                row.view_count = count
                await db.commit()

    async def get_platform_summaries(self) -> list[PlatformSummary]:
        async with self._sf() as db:
            q = select(
                PublicationRow.platform,
                func.count().label("total"),
                func.count().filter(
                    PublicationRow.status == "success",
                ).label("success"),
                func.count().filter(
                    PublicationRow.status == "failed",
                ).label("failed"),
                func.count().filter(
                    PublicationRow.status == "scheduled",
                ).label("scheduled"),
            ).group_by(PublicationRow.platform)
            rows = (await db.execute(q)).all()
            return [
                PlatformSummary(
                    platform=r.platform,
                    total=r.total,
                    success=r.success,
                    failed=r.failed,
                    scheduled=r.scheduled,
                )
                for r in rows
            ]

    @staticmethod
    def _to_model(row: PublicationRow) -> Publication:
        events = [
            PublicationEvent.model_validate(e)
            for e in (row.event_history or [])
        ]
        return Publication(
            id=row.id,
            article_id=row.article_id,
            platform=row.platform,
            status=PublicationStatus(row.status),
            external_id=row.external_id,
            external_url=row.external_url,
            published_at=row.published_at,
            view_count=row.view_count,
            seo_score=row.seo_score,
            error_message=row.error_message,
            event_history=events,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/db/test_publication_repository.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/repositories.py tests/unit/db/test_publication_repository.py
git commit -m "feat: add PgPublicationRepository with CRUD and summaries"
```

---

## Task 4: SEO Score Computation + PublishingService Persistence

**Files:**
- Modify: `src/services/publishing/service.py`
- Create: `tests/unit/services/test_publication_tracking.py`

- [ ] **Step 1: Write failing tests for compute_seo_score and service persistence**

```python
# tests/unit/services/test_publication_tracking.py
"""Tests for publication tracking in PublishingService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.content import SEOMetadata, StructuredDataLD, SchemaOrgAuthor
from src.models.publishing import PublicationStatus


class TestComputeSeoScore:
    def test_all_fields_present(self) -> None:
        from src.services.publishing.service import compute_seo_score

        seo = SEOMetadata(
            title="Test Title for SEO",
            description="A meta description for testing purposes.",
            keywords=["test", "seo"],
            canonical_url="https://example.com/article",
            structured_data=StructuredDataLD(
                context="https://schema.org",
                type="Article",
                headline="Test",
                author=SchemaOrgAuthor(),
                datePublished=datetime.now(UTC).isoformat(),
            ),
        )
        assert compute_seo_score(seo) == 100

    def test_no_optional_fields(self) -> None:
        from src.services.publishing.service import compute_seo_score

        seo = SEOMetadata(
            title="Test Title",
            description="Description",
            keywords=[],
            canonical_url=None,
            structured_data=None,
        )
        # title(20) + description(20) + no keywords(0) + no url(0) + no ld(0)
        assert compute_seo_score(seo) == 40

    def test_keywords_only(self) -> None:
        from src.services.publishing.service import compute_seo_score

        seo = SEOMetadata(
            title="T",
            description="D",
            keywords=["k1"],
        )
        # title(20) + description(20) + keywords(20) = 60
        assert compute_seo_score(seo) == 60

    def test_all_optional_fields(self) -> None:
        from src.services.publishing.service import compute_seo_score

        seo = SEOMetadata(
            title="T",
            description="D",
            keywords=["k1"],
            canonical_url="https://example.com",
            structured_data=StructuredDataLD(
                context="https://schema.org",
                type="Article",
                headline="Test",
                author=SchemaOrgAuthor(),
                datePublished=datetime.now(UTC).isoformat(),
            ),
        )
        assert compute_seo_score(seo) == 100


class TestPublishingServicePersistence:
    @pytest.fixture
    def article_repo(self):
        repo = AsyncMock()
        article = MagicMock()
        article.id = uuid4()
        article.seo = SEOMetadata(title="T", description="D", keywords=["k"])
        repo.get.return_value = article
        return repo

    @pytest.fixture
    def pub_repo(self):
        repo = AsyncMock()
        repo.get_by_article_platform.return_value = None
        repo.create.side_effect = lambda p: p
        repo.update.side_effect = lambda p: p
        return repo

    @pytest.fixture
    def adapter(self):
        from src.models.publishing import PublicationResult

        adapter = AsyncMock()
        adapter.publish.return_value = PublicationResult(
            article_id=uuid4(),
            platform="ghost",
            status=PublicationStatus.SUCCESS,
            external_id="g-1",
            external_url="https://blog.example.com/post",
            published_at=datetime.now(UTC),
        )
        return adapter

    @pytest.fixture
    def transformer(self):
        t = MagicMock()
        t.transform.return_value = MagicMock(platform="ghost")
        return t

    @pytest.fixture
    def service(self, article_repo, pub_repo, transformer, adapter):
        from src.services.publishing.service import PlatformPair, PublishingService

        svc = PublishingService(article_repo, pub_repo)
        svc.register("ghost", PlatformPair(transformer=transformer, adapter=adapter))
        return svc

    @pytest.mark.asyncio
    async def test_publish_creates_publication_record(
        self, service, pub_repo, article_repo,
    ) -> None:
        result = await service.publish(article_repo.get.return_value.id, "ghost")
        assert result.status == PublicationStatus.SUCCESS
        pub_repo.create.assert_called_once()
        created = pub_repo.create.call_args[0][0]
        assert created.platform == "ghost"
        assert created.seo_score == 60  # title + desc + keywords
        assert len(created.event_history) == 1

    @pytest.mark.asyncio
    async def test_publish_updates_existing_record(
        self, service, pub_repo, article_repo,
    ) -> None:
        from src.models.publishing import Publication

        existing = Publication(
            id=uuid4(),
            article_id=article_repo.get.return_value.id,
            platform="ghost",
            status=PublicationStatus.FAILED,
            seo_score=60,
            error_message="old error",
            event_history=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        pub_repo.get_by_article_platform.return_value = existing

        result = await service.publish(article_repo.get.return_value.id, "ghost")
        assert result.status == PublicationStatus.SUCCESS
        pub_repo.update.assert_called_once()
        pub_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_republishes_failed(
        self, service, pub_repo, article_repo,
    ) -> None:
        from src.models.publishing import Publication

        pub_id = uuid4()
        failed = Publication(
            id=pub_id,
            article_id=article_repo.get.return_value.id,
            platform="ghost",
            status=PublicationStatus.FAILED,
            seo_score=60,
            error_message="Timeout",
            event_history=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        pub_repo.get.return_value = failed

        result = await service.retry(pub_id)
        assert result.status == PublicationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_retry_rejects_non_failed(
        self, service, pub_repo, article_repo,
    ) -> None:
        from src.models.publishing import Publication

        pub_id = uuid4()
        success = Publication(
            id=pub_id,
            article_id=article_repo.get.return_value.id,
            platform="ghost",
            status=PublicationStatus.SUCCESS,
            seo_score=80,
            event_history=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        pub_repo.get.return_value = success

        with pytest.raises(ValueError, match="Only failed publications"):
            await service.retry(pub_id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/services/test_publication_tracking.py -v`
Expected: FAIL — `TypeError` or `ImportError` (service doesn't accept `pub_repo` yet)

- [ ] **Step 3: Implement compute_seo_score and update PublishingService**

Replace the full content of `src/services/publishing/service.py`:

```python
"""PublishingService — platform-agnostic orchestrator with retry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from src.models.publishing import (
    Publication,
    PublicationEvent,
    PublicationResult,
    PublicationStatus,
    Transformer,
)

if TYPE_CHECKING:
    from src.models.content import SEOMetadata
    from src.models.publishing import Adapter

logger = structlog.get_logger()

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds


@dataclass(frozen=True)
class PlatformPair:
    """A transformer + adapter pair for a single platform."""

    transformer: Transformer
    adapter: Adapter


def compute_seo_score(seo: SEOMetadata) -> int:
    """Compute 0-100 SEO completeness score from article metadata."""
    score = 0
    if seo.title:
        score += 20
    if seo.description:
        score += 20
    if seo.keywords:
        score += 20
    if seo.canonical_url:
        score += 15
    if seo.structured_data is not None:
        score += 25
    return score


class PublishingService:
    """Orchestrates publishing: load, transform, publish with retry."""

    def __init__(
        self,
        article_repo: object,
        pub_repo: object | None = None,
    ) -> None:
        self._article_repo = article_repo
        self._pub_repo = pub_repo
        self._platforms: dict[str, PlatformPair] = {}

    def register(self, platform: str, pair: PlatformPair) -> None:
        self._platforms[platform] = pair
        logger.info("platform_registered", platform=platform)

    async def publish(
        self,
        article_id: UUID,
        platform: str,
        schedule_at: datetime | None = None,
    ) -> PublicationResult:
        logger.info(
            "publish_started",
            article_id=str(article_id),
            platform=platform,
        )
        article = await self._article_repo.get(article_id)
        if article is None:
            return _failed(article_id, platform, "Article not found")

        pair = self._platforms.get(platform)
        if pair is None:
            return _failed(article_id, platform, f"Unknown platform: {platform}")

        payload = pair.transformer.transform(article)
        result = await _with_retry(
            pair.adapter, payload, schedule_at, article_id, platform,
        )

        if self._pub_repo is not None:
            await self._persist_result(result, article)

        return result

    async def retry(self, publication_id: UUID) -> PublicationResult:
        """Re-publish a failed publication."""
        if self._pub_repo is None:
            msg = "Publication repository not configured"
            raise ValueError(msg)

        pub = await self._pub_repo.get(publication_id)
        if pub is None:
            msg = f"Publication {publication_id} not found"
            raise ValueError(msg)
        if pub.status != PublicationStatus.FAILED:
            msg = "Only failed publications can be retried"
            raise ValueError(msg)

        return await self.publish(pub.article_id, pub.platform)

    async def _persist_result(
        self, result: PublicationResult, article: object,
    ) -> None:
        """Create or update publication record after publish attempt."""
        now = datetime.now(UTC)
        event = PublicationEvent(
            timestamp=now,
            status=result.status,
            error_message=result.error_message,
        )
        seo_score = compute_seo_score(article.seo)

        existing = await self._pub_repo.get_by_article_platform(
            result.article_id, result.platform,
        )
        if existing is not None:
            updated = Publication(
                id=existing.id,
                article_id=existing.article_id,
                platform=existing.platform,
                status=result.status,
                external_id=result.external_id or existing.external_id,
                external_url=result.external_url or existing.external_url,
                published_at=result.published_at or existing.published_at,
                view_count=existing.view_count,
                seo_score=seo_score,
                error_message=result.error_message,
                event_history=[*existing.event_history, event],
                created_at=existing.created_at,
                updated_at=now,
            )
            await self._pub_repo.update(updated)
        else:
            new_pub = Publication(
                id=uuid4(),
                article_id=result.article_id,
                platform=result.platform,
                status=result.status,
                external_id=result.external_id,
                external_url=result.external_url,
                published_at=result.published_at,
                view_count=0,
                seo_score=seo_score,
                error_message=result.error_message,
                event_history=[event],
                created_at=now,
                updated_at=now,
            )
            await self._pub_repo.create(new_pub)

        logger.info(
            "publication_persisted",
            article_id=str(result.article_id),
            platform=result.platform,
            status=result.status,
        )


async def _with_retry(
    adapter: Adapter,
    payload: object,
    schedule_at: datetime | None,
    article_id: UUID,
    platform: str,
) -> PublicationResult:
    """Retry on transient errors (exceptions), not permanent failures."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            result = await adapter.publish(payload, schedule_at)  # type: ignore[arg-type]
            _log_result(result, article_id, platform)
            return result
        except Exception as exc:
            last_error = exc
            wait = _BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "publish_retry",
                attempt=attempt + 1,
                platform=platform,
                error=str(exc),
            )
            await asyncio.sleep(wait)
    logger.error(
        "publish_exhausted_retries",
        article_id=str(article_id),
        platform=platform,
    )
    return _failed(article_id, platform, f"Retries exhausted: {last_error}")


def _log_result(
    result: PublicationResult, article_id: UUID, platform: str,
) -> None:
    if result.status == PublicationStatus.SUCCESS:
        logger.info(
            "publish_succeeded",
            article_id=str(article_id),
            platform=platform,
        )
    else:
        logger.warning(
            "publish_failed",
            article_id=str(article_id),
            platform=platform,
            error=result.error_message,
        )


def _failed(
    article_id: UUID, platform: str, message: str,
) -> PublicationResult:
    return PublicationResult(
        article_id=article_id,
        platform=platform,
        status=PublicationStatus.FAILED,
        error_message=message,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/services/test_publication_tracking.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run existing publishing tests to verify no regressions**

Run: `uv run pytest tests/unit/api/test_publishing.py tests/unit/models/test_publishing.py -v`
Expected: ALL PASS (the `pub_repo` param defaults to `None` so existing code works)

- [ ] **Step 6: Commit**

```bash
git add src/services/publishing/service.py tests/unit/services/test_publication_tracking.py
git commit -m "feat: add SEO score computation and publication persistence to PublishingService"
```

---

## Task 5: API Response Schemas + Publication Endpoints

**Files:**
- Modify: `src/api/schemas/publishing.py`
- Modify: `src/api/routers/publishing.py`
- Create: `tests/unit/api/test_publication_endpoints.py`

- [ ] **Step 1: Write failing tests for the new endpoints**

```python
# tests/unit/api/test_publication_endpoints.py
"""Tests for publication tracking API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.config.settings import Settings
from src.models.publishing import (
    PlatformSummary,
    Publication,
    PublicationEvent,
    PublicationStatus,
)

_EDITOR_TOKEN = {
    "sub": str(uuid4()),
    "role": "editor",
    "exp": 9999999999,
    "jti": str(uuid4()),
}


def _pub(*, platform: str = "ghost", status: PublicationStatus = PublicationStatus.SUCCESS) -> Publication:
    return Publication(
        id=uuid4(),
        article_id=uuid4(),
        platform=platform,
        status=status,
        external_id="ext-1",
        external_url="https://blog.example.com/post",
        published_at=datetime.now(UTC),
        view_count=42,
        seo_score=80,
        error_message=None if status == PublicationStatus.SUCCESS else "Error",
        event_history=[
            PublicationEvent(timestamp=datetime.now(UTC), status=status),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def pub_app():
    settings = Settings(
        cognify_secret_key="test-secret-key-for-jwt-tokens-1234567890",
        jwt_algorithm="HS256",
    )
    app = create_app(settings)
    app.state.publishing_service = MagicMock()
    pub_repo = AsyncMock()
    app.state.pub_repo = pub_repo
    return app


@pytest.fixture
async def pub_client(pub_app):
    transport = ASGITransport(app=pub_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestListPublications:
    @pytest.mark.asyncio
    async def test_requires_auth(self, pub_client) -> None:
        resp = await pub_client.get("/api/v1/publications")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    @patch("src.api.dependencies.decode_token")
    async def test_returns_paginated_list(self, mock_decode, pub_client, pub_app) -> None:
        mock_decode.return_value = _EDITOR_TOKEN
        pubs = [_pub(), _pub(platform="medium")]
        pub_app.state.pub_repo.list.return_value = (pubs, 2)
        # Provide article titles
        article_repo = AsyncMock()
        article_mock = MagicMock()
        article_mock.title = "Test Article"
        article_repo.get.return_value = article_mock
        pub_app.state.article_repo = article_repo

        resp = await pub_client.get(
            "/api/v1/publications",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2


class TestGetPublication:
    @pytest.mark.asyncio
    @patch("src.api.dependencies.decode_token")
    async def test_not_found(self, mock_decode, pub_client, pub_app) -> None:
        mock_decode.return_value = _EDITOR_TOKEN
        pub_app.state.pub_repo.get.return_value = None

        resp = await pub_client.get(
            f"/api/v1/publications/{uuid4()}",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 404


class TestRetryPublication:
    @pytest.mark.asyncio
    async def test_requires_auth(self, pub_client) -> None:
        resp = await pub_client.post(f"/api/v1/publications/{uuid4()}/retry")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    @patch("src.api.dependencies.decode_token")
    async def test_retry_success(self, mock_decode, pub_client, pub_app) -> None:
        mock_decode.return_value = _EDITOR_TOKEN
        pub_id = uuid4()
        failed_pub = _pub(status=PublicationStatus.FAILED)
        pub_app.state.pub_repo.get.return_value = failed_pub

        from src.models.publishing import PublicationResult

        pub_app.state.publishing_service.retry = AsyncMock(
            return_value=PublicationResult(
                article_id=failed_pub.article_id,
                platform="ghost",
                status=PublicationStatus.SUCCESS,
                external_id="g-retry",
                external_url="https://blog.example.com/retried",
                published_at=datetime.now(UTC),
            ),
        )

        resp = await pub_client.post(
            f"/api/v1/publications/{pub_id}/retry",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200


class TestPlatformSummaries:
    @pytest.mark.asyncio
    @patch("src.api.dependencies.decode_token")
    async def test_returns_summaries(self, mock_decode, pub_client, pub_app) -> None:
        mock_decode.return_value = _EDITOR_TOKEN
        pub_app.state.pub_repo.get_platform_summaries.return_value = [
            PlatformSummary(platform="ghost", total=10, success=8, failed=1, scheduled=1),
        ]

        resp = await pub_client.get(
            "/api/v1/publications/summaries",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["platform"] == "ghost"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/test_publication_endpoints.py -v`
Expected: FAIL — 404 (routes don't exist yet)

- [ ] **Step 3: Add API response schemas to src/api/schemas/publishing.py**

Replace the full content:

```python
"""Request/response schemas for the publishing API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PublishRequest(BaseModel):
    platform: str = Field(min_length=1)
    schedule_at: datetime | None = None


class PublishResponse(BaseModel):
    article_id: UUID
    platform: str
    status: str
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    error_message: str | None = None


class PublicationEventResponse(BaseModel):
    timestamp: datetime
    status: str
    error_message: str | None = None


class PublicationResponse(BaseModel):
    id: UUID
    article_id: UUID
    article_title: str
    platform: str
    status: str
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    view_count: int = 0
    seo_score: int = 0
    error_message: str | None = None
    event_history: list[PublicationEventResponse] = []
    created_at: datetime
    updated_at: datetime


class PublicationListResponse(BaseModel):
    items: list[PublicationResponse]
    total: int
    page: int
    size: int


class PlatformSummaryResponse(BaseModel):
    platform: str
    total: int
    success: int
    failed: int
    scheduled: int
```

- [ ] **Step 4: Add new endpoints to src/api/routers/publishing.py**

Replace the full content:

```python
"""Publishing router — publish articles to external platforms."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.rate_limiter import limiter
from src.api.schemas.publishing import (
    PlatformSummaryResponse,
    PublicationListResponse,
    PublicationResponse,
    PublishRequest,
    PublishResponse,
)

logger = structlog.get_logger()

publishing_router = APIRouter()


@limiter.limit("5/minute")
@publishing_router.post(
    "/articles/{article_id}/publish",
    response_model=PublishResponse,
    status_code=HTTP_201_CREATED,
)
async def publish_article(
    request: Request,
    article_id: UUID,
    body: PublishRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PublishResponse:
    svc = request.app.state.publishing_service
    result = await svc.publish(article_id, body.platform, body.schedule_at)
    logger.info(
        "publish_endpoint_called",
        article_id=str(article_id),
        platform=body.platform,
        status=result.status,
    )
    return PublishResponse(
        article_id=result.article_id,
        platform=result.platform,
        status=result.status,
        external_id=result.external_id,
        external_url=result.external_url,
        published_at=result.published_at,
        error_message=result.error_message,
    )


@limiter.limit("30/minute")
@publishing_router.get(
    "/publications",
    response_model=PublicationListResponse,
)
async def list_publications(
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    platform: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: TokenPayload = Depends(require_viewer_or_above),
) -> PublicationListResponse:
    pub_repo = request.app.state.pub_repo
    article_repo = request.app.state.article_repo
    pubs, total = await pub_repo.list(page=page, size=size, platform=platform, status=status)

    items = []
    for pub in pubs:
        article = await article_repo.get(pub.article_id)
        title = article.title if article else "Unknown"
        items.append(
            PublicationResponse(
                id=pub.id,
                article_id=pub.article_id,
                article_title=title,
                platform=pub.platform,
                status=pub.status.value,
                external_id=pub.external_id,
                external_url=pub.external_url,
                published_at=pub.published_at,
                view_count=pub.view_count,
                seo_score=pub.seo_score,
                error_message=pub.error_message,
                event_history=[
                    {"timestamp": e.timestamp, "status": e.status.value, "error_message": e.error_message}
                    for e in pub.event_history
                ],
                created_at=pub.created_at,
                updated_at=pub.updated_at,
            ),
        )
    return PublicationListResponse(items=items, total=total, page=page, size=size)


@limiter.limit("30/minute")
@publishing_router.get(
    "/publications/summaries",
    response_model=list[PlatformSummaryResponse],
)
async def get_platform_summaries(
    request: Request,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> list[PlatformSummaryResponse]:
    pub_repo = request.app.state.pub_repo
    summaries = await pub_repo.get_platform_summaries()
    return [
        PlatformSummaryResponse(
            platform=s.platform,
            total=s.total,
            success=s.success,
            failed=s.failed,
            scheduled=s.scheduled,
        )
        for s in summaries
    ]


@limiter.limit("30/minute")
@publishing_router.get(
    "/publications/{publication_id}",
    response_model=PublicationResponse,
)
async def get_publication(
    request: Request,
    publication_id: UUID,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> PublicationResponse:
    pub_repo = request.app.state.pub_repo
    article_repo = request.app.state.article_repo
    pub = await pub_repo.get(publication_id)
    if pub is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    article = await article_repo.get(pub.article_id)
    title = article.title if article else "Unknown"
    return PublicationResponse(
        id=pub.id,
        article_id=pub.article_id,
        article_title=title,
        platform=pub.platform,
        status=pub.status.value,
        external_id=pub.external_id,
        external_url=pub.external_url,
        published_at=pub.published_at,
        view_count=pub.view_count,
        seo_score=pub.seo_score,
        error_message=pub.error_message,
        event_history=[
            {"timestamp": e.timestamp, "status": e.status.value, "error_message": e.error_message}
            for e in pub.event_history
        ],
        created_at=pub.created_at,
        updated_at=pub.updated_at,
    )


@limiter.limit("5/minute")
@publishing_router.post(
    "/publications/{publication_id}/retry",
    response_model=PublishResponse,
)
async def retry_publication(
    request: Request,
    publication_id: UUID,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PublishResponse:
    svc = request.app.state.publishing_service
    try:
        result = await svc.retry(publication_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PublishResponse(
        article_id=result.article_id,
        platform=result.platform,
        status=result.status,
        external_id=result.external_id,
        external_url=result.external_url,
        published_at=result.published_at,
        error_message=result.error_message,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/test_publication_endpoints.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run all existing backend tests for regressions**

Run: `uv run pytest tests/unit/ -q`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/schemas/publishing.py src/api/routers/publishing.py tests/unit/api/test_publication_endpoints.py
git commit -m "feat: add publication list, detail, retry, and summary API endpoints"
```

---

## Task 6: Wire PgPublicationRepository in App Startup

**Files:**
- Modify: `src/api/main.py`

- [ ] **Step 1: Update _init_publishing_service to accept and pass pub_repo**

In `src/api/main.py`, update the `_init_publishing_service` function signature and body:

```python
def _init_publishing_service(
    app: FastAPI, settings: Settings, article_repo: object,
    pub_repo: object | None = None,
) -> None:
    """Initialize publishing service with available platform adapters."""
    from src.services.publishing.service import PlatformPair, PublishingService

    svc = PublishingService(article_repo, pub_repo)
    if settings.ghost_api_url and settings.ghost_admin_api_key:
        from src.services.publishing.ghost.adapter import GhostAdapter
        from src.services.publishing.ghost.transformer import GhostTransformer

        api_base = "http://localhost:8000"
        pair = PlatformPair(
            transformer=GhostTransformer(api_base_url=api_base),
            adapter=GhostAdapter(settings.ghost_api_url, settings.ghost_admin_api_key),
        )
        svc.register("ghost", pair)
    if settings.medium_api_token and settings.medium_user_id:
        from src.services.publishing.medium.adapter import MediumAdapter
        from src.services.publishing.medium.transformer import MediumTransformer

        pair = PlatformPair(
            transformer=MediumTransformer(),
            adapter=MediumAdapter(settings.medium_api_token, settings.medium_user_id),
        )
        svc.register("medium", pair)
    app.state.publishing_service = svc
    logger.info("publishing_service_initialized", platforms=list(svc._platforms.keys()))
```

- [ ] **Step 2: Create PgPublicationRepository in lifespan and pass to init**

In the lifespan function, after `article_repo` is created (around line 240 where `_init_publishing_service` is called), add:

```python
        from src.db.repositories import PgPublicationRepository

        pub_repo = PgPublicationRepository(async_session)
        app.state.pub_repo = pub_repo
        app.state.article_repo = article_repo
        _init_publishing_service(app, settings, article_repo, pub_repo)
```

Replace the existing `_init_publishing_service(app, settings, article_repo)` call with the above block.

- [ ] **Step 3: Run all backend tests for regressions**

Run: `uv run pytest tests/unit/ -q`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/api/main.py
git commit -m "feat: wire PgPublicationRepository into app startup"
```

---

## Task 7: Frontend Types + API Client + Hooks

**Files:**
- Create: `frontend/src/types/publishing.ts`
- Create: `frontend/src/lib/api/publications.ts`
- Create: `frontend/src/hooks/use-publications.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/types/publishing.ts
export type PublicationStatus = "success" | "failed" | "scheduled";

export interface PublicationEvent {
  timestamp: string;
  status: PublicationStatus;
  error_message: string | null;
}

export interface Publication {
  id: string;
  article_id: string;
  article_title: string;
  platform: string;
  status: PublicationStatus;
  external_id: string | null;
  external_url: string | null;
  published_at: string | null;
  view_count: number;
  seo_score: number;
  error_message: string | null;
  event_history: PublicationEvent[];
  created_at: string;
  updated_at: string;
}

export interface PublicationListResponse {
  items: Publication[];
  total: number;
  page: number;
  size: number;
}

export interface PlatformSummary {
  platform: string;
  total: number;
  success: number;
  failed: number;
  scheduled: number;
}
```

- [ ] **Step 2: Create API client functions**

```typescript
// frontend/src/lib/api/publications.ts
import { apiClient } from "./client";
import type {
  Publication,
  PublicationListResponse,
  PlatformSummary,
} from "@/types/publishing";
import type { PublishResult } from "./articles";

export async function getPublications(params: {
  page?: number;
  size?: number;
  platform?: string;
  status?: string;
}): Promise<PublicationListResponse> {
  const { data } = await apiClient.get<PublicationListResponse>(
    "/publications",
    { params },
  );
  return data;
}

export async function getPublication(id: string): Promise<Publication> {
  const { data } = await apiClient.get<Publication>(`/publications/${id}`);
  return data;
}

export async function getPlatformSummaries(): Promise<PlatformSummary[]> {
  const { data } = await apiClient.get<PlatformSummary[]>(
    "/publications/summaries",
  );
  return data;
}

export async function retryPublication(id: string): Promise<PublishResult> {
  const { data } = await apiClient.post<PublishResult>(
    `/publications/${id}/retry`,
  );
  return data;
}
```

- [ ] **Step 3: Create React Query hooks**

```typescript
// frontend/src/hooks/use-publications.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPublications,
  getPlatformSummaries,
  retryPublication,
} from "@/lib/api/publications";

interface PublicationFilters {
  platform?: string;
  status?: string;
  page?: number;
}

export function usePublications(filters: PublicationFilters = {}) {
  return useQuery({
    queryKey: ["publications", filters],
    queryFn: () =>
      getPublications({
        page: filters.page ?? 1,
        size: 20,
        platform: filters.platform,
        status: filters.status,
      }),
    staleTime: 30 * 1000,
  });
}

export function usePlatformSummaries() {
  return useQuery({
    queryKey: ["platform-summaries"],
    queryFn: getPlatformSummaries,
    staleTime: 60 * 1000,
  });
}

export function useRetryPublication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryPublication(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["publications"] });
      queryClient.invalidateQueries({ queryKey: ["platform-summaries"] });
    },
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/publishing.ts frontend/src/lib/api/publications.ts frontend/src/hooks/use-publications.ts
git commit -m "feat: add frontend types, API client, and hooks for publications"
```

---

## Task 8: Frontend Components — Platform Summary Card + Filters

**Files:**
- Create: `frontend/src/components/publishing/platform-summary-card.tsx`
- Create: `frontend/src/components/publishing/publication-filters.tsx`
- Create: `frontend/src/components/publishing/__tests__/platform-summary-card.test.tsx`
- Create: `frontend/src/components/publishing/__tests__/publication-filters.test.tsx`

- [ ] **Step 1: Write tests for PlatformSummaryCard**

```typescript
// frontend/src/components/publishing/__tests__/platform-summary-card.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PlatformSummaryCard } from "../platform-summary-card";

describe("PlatformSummaryCard", () => {
  it("renders platform name and counts", () => {
    render(
      <PlatformSummaryCard
        summary={{ platform: "ghost", total: 10, success: 8, failed: 1, scheduled: 1 }}
      />,
    );
    expect(screen.getByText("Ghost")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("capitalizes platform name", () => {
    render(
      <PlatformSummaryCard
        summary={{ platform: "medium", total: 3, success: 2, failed: 1, scheduled: 0 }}
      />,
    );
    expect(screen.getByText("Medium")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write tests for PublicationFilters**

```typescript
// frontend/src/components/publishing/__tests__/publication-filters.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PublicationFilters } from "../publication-filters";

describe("PublicationFilters", () => {
  it("renders all filter pills", () => {
    render(
      <PublicationFilters
        activePlatform="all"
        activeStatus="all"
        onPlatformChange={vi.fn()}
        onStatusChange={vi.fn()}
        totalCount={5}
      />,
    );
    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("calls onStatusChange when a status pill is clicked", () => {
    const onStatusChange = vi.fn();
    render(
      <PublicationFilters
        activePlatform="all"
        activeStatus="all"
        onPlatformChange={vi.fn()}
        onStatusChange={onStatusChange}
        totalCount={5}
      />,
    );
    fireEvent.click(screen.getByText("Failed"));
    expect(onStatusChange).toHaveBeenCalledWith("failed");
  });

  it("shows total count", () => {
    render(
      <PublicationFilters
        activePlatform="all"
        activeStatus="all"
        onPlatformChange={vi.fn()}
        onStatusChange={vi.fn()}
        totalCount={42}
      />,
    );
    expect(screen.getByText("42 Publications")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/publishing`
Expected: FAIL — files don't exist

- [ ] **Step 4: Implement PlatformSummaryCard**

```typescript
// frontend/src/components/publishing/platform-summary-card.tsx
import type { PlatformSummary } from "@/types/publishing";

interface PlatformSummaryCardProps {
  summary: PlatformSummary;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function PlatformSummaryCard({ summary }: PlatformSummaryCardProps) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <h3 className="font-heading text-lg font-semibold text-neutral-800">
        {capitalize(summary.platform)}
      </h3>
      <p className="mt-1 text-3xl font-heading font-semibold text-neutral-900">
        {summary.total}
      </p>
      <p className="mt-1 text-sm text-neutral-500">publications</p>
      <div className="mt-3 flex gap-4 text-xs font-medium">
        <span className="text-green-600">{summary.success} live</span>
        <span className="text-red-600">{summary.failed} failed</span>
        <span className="text-yellow-600">{summary.scheduled} scheduled</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Implement PublicationFilters**

```typescript
// frontend/src/components/publishing/publication-filters.tsx
import { cn } from "@/lib/utils";

const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "success", label: "Live" },
  { value: "failed", label: "Failed" },
  { value: "scheduled", label: "Scheduled" },
] as const;

interface PublicationFiltersProps {
  activePlatform: string;
  activeStatus: string;
  onPlatformChange: (platform: string) => void;
  onStatusChange: (status: string) => void;
  totalCount: number;
  platforms?: string[];
}

export function PublicationFilters({
  activePlatform,
  activeStatus,
  onPlatformChange,
  onStatusChange,
  totalCount,
  platforms = [],
}: PublicationFiltersProps) {
  const platformFilters = [
    { value: "all", label: "All" },
    ...platforms.map((p) => ({
      value: p,
      label: p.charAt(0).toUpperCase() + p.slice(1),
    })),
  ];

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap gap-2">
        {platformFilters.map(({ value, label }) => (
          <button
            key={`platform-${value}`}
            type="button"
            onClick={() => onPlatformChange(value === "all" ? "all" : value)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              activePlatform === value
                ? "bg-primary text-white"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200",
            )}
          >
            {label}
          </button>
        ))}
        <span className="mx-1 text-neutral-300">|</span>
        {STATUS_FILTERS.map(({ value, label }) => (
          <button
            key={`status-${value}`}
            type="button"
            onClick={() => onStatusChange(value === "all" ? "all" : value)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              activeStatus === value
                ? "bg-primary text-white"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <span className="text-sm text-neutral-500">{totalCount} Publications</span>
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/publishing`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/publishing/
git commit -m "feat: add PlatformSummaryCard and PublicationFilters components"
```

---

## Task 9: Frontend Component — Publications Table

**Files:**
- Create: `frontend/src/components/publishing/publications-table.tsx`
- Create: `frontend/src/components/publishing/__tests__/publications-table.test.tsx`

- [ ] **Step 1: Write tests for PublicationsTable**

```typescript
// frontend/src/components/publishing/__tests__/publications-table.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PublicationsTable } from "../publications-table";
import type { Publication } from "@/types/publishing";

const mockPub: Publication = {
  id: "pub-1",
  article_id: "art-1",
  article_title: "AI Security Trends",
  platform: "ghost",
  status: "success",
  external_id: "g-1",
  external_url: "https://blog.example.com/ai-security",
  published_at: "2026-03-27T10:00:00Z",
  view_count: 42,
  seo_score: 80,
  error_message: null,
  event_history: [],
  created_at: "2026-03-27T10:00:00Z",
  updated_at: "2026-03-27T10:00:00Z",
};

const failedPub: Publication = {
  ...mockPub,
  id: "pub-2",
  status: "failed",
  external_url: null,
  view_count: 0,
  error_message: "Connection refused",
};

describe("PublicationsTable", () => {
  it("renders publication rows", () => {
    render(
      <PublicationsTable publications={[mockPub]} onRetry={vi.fn()} retryingId={null} />,
    );
    expect(screen.getByText("AI Security Trends")).toBeInTheDocument();
    expect(screen.getByText("Ghost")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
  });

  it("shows retry button only for failed publications", () => {
    render(
      <PublicationsTable publications={[mockPub, failedPub]} onRetry={vi.fn()} retryingId={null} />,
    );
    const retryButtons = screen.getAllByText("Retry");
    expect(retryButtons).toHaveLength(1);
  });

  it("calls onRetry when retry button clicked", () => {
    const onRetry = vi.fn();
    render(
      <PublicationsTable publications={[failedPub]} onRetry={onRetry} retryingId={null} />,
    );
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledWith("pub-2");
  });

  it("shows N/A for non-ghost view counts", () => {
    const mediumPub = { ...mockPub, platform: "medium", view_count: 0 };
    render(
      <PublicationsTable publications={[mediumPub]} onRetry={vi.fn()} retryingId={null} />,
    );
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("shows empty state when no publications", () => {
    render(
      <PublicationsTable publications={[]} onRetry={vi.fn()} retryingId={null} />,
    );
    expect(screen.getByText("No publications yet")).toBeInTheDocument();
  });

  it("shows loading state on retry button when retrying", () => {
    render(
      <PublicationsTable publications={[failedPub]} onRetry={vi.fn()} retryingId="pub-2" />,
    );
    expect(screen.getByText("Retrying...")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/publishing/__tests__/publications-table.test.tsx`
Expected: FAIL — file doesn't exist

- [ ] **Step 3: Implement PublicationsTable**

```typescript
// frontend/src/components/publishing/publications-table.tsx
import { ExternalLink } from "lucide-react";
import type { Publication } from "@/types/publishing";

interface PublicationsTableProps {
  publications: Publication[];
  onRetry: (id: string) => void;
  retryingId: string | null;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string }> = {
    success: { label: "Live", className: "bg-green-50 text-green-600" },
    failed: { label: "Failed", className: "bg-red-50 text-red-600" },
    scheduled: { label: "Scheduled", className: "bg-yellow-50 text-yellow-600" },
  };
  const { label, className } = config[status] ?? { label: status, className: "bg-neutral-100 text-neutral-600" };
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}

function SeoScore({ score }: { score: number }) {
  const color = score >= 80 ? "text-green-600" : score >= 50 ? "text-yellow-600" : "text-red-600";
  return <span className={`text-sm font-medium ${color}`}>{score}</span>;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function PublicationsTable({ publications, onRetry, retryingId }: PublicationsTableProps) {
  if (publications.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-200 bg-white p-12 text-center">
        <p className="text-sm text-neutral-500">No publications yet</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-200 bg-white">
      <table className="w-full">
        <thead>
          <tr className="border-b border-neutral-100 bg-neutral-50">
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Article
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Platform
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Status
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Published
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Views
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              SEO
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {publications.map((pub) => (
            <tr key={pub.id} className="border-b border-neutral-100 hover:bg-neutral-50">
              <td className="px-4 py-3 text-sm font-medium text-neutral-900">
                {pub.article_title}
              </td>
              <td className="px-4 py-3 text-sm text-neutral-600">
                {capitalize(pub.platform)}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={pub.status} />
              </td>
              <td className="px-4 py-3 text-sm text-neutral-600">
                {formatDate(pub.published_at)}
              </td>
              <td className="px-4 py-3 text-sm text-neutral-600">
                {pub.platform === "ghost" ? pub.view_count : "N/A"}
              </td>
              <td className="px-4 py-3">
                <SeoScore score={pub.seo_score} />
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  {pub.external_url && (
                    <a
                      href={pub.external_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-neutral-400 hover:text-neutral-600"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                  {pub.status === "failed" && (
                    <button
                      type="button"
                      onClick={() => onRetry(pub.id)}
                      disabled={retryingId === pub.id}
                      className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
                    >
                      {retryingId === pub.id ? "Retrying..." : "Retry"}
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/publishing/__tests__/publications-table.test.tsx`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/publishing/publications-table.tsx frontend/src/components/publishing/__tests__/publications-table.test.tsx
git commit -m "feat: add PublicationsTable component with retry and SEO score"
```

---

## Task 10: Publishing Page — Replace Placeholder

**Files:**
- Modify: `frontend/src/app/(dashboard)/publishing/page.tsx`

- [ ] **Step 1: Replace placeholder with full publishing page**

```typescript
// frontend/src/app/(dashboard)/publishing/page.tsx
"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { usePublications, usePlatformSummaries, useRetryPublication } from "@/hooks/use-publications";
import { PlatformSummaryCard } from "@/components/publishing/platform-summary-card";
import { PublicationFilters } from "@/components/publishing/publication-filters";
import { PublicationsTable } from "@/components/publishing/publications-table";

export default function PublishingPage() {
  const [platform, setPlatform] = useState("all");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);

  const filters = {
    platform: platform === "all" ? undefined : platform,
    status: status === "all" ? undefined : status,
    page,
  };

  const { data: pubData, isLoading: pubLoading } = usePublications(filters);
  const { data: summaries, isLoading: sumLoading } = usePlatformSummaries();
  const retryMutation = useRetryPublication();

  const publications = pubData?.items ?? [];
  const total = pubData?.total ?? 0;
  const totalPages = Math.ceil(total / 20);
  const platformNames = summaries?.map((s) => s.platform) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Send className="h-6 w-6 text-primary" />
        <h1 className="font-heading text-3xl font-semibold text-neutral-800">
          Publishing
        </h1>
      </div>

      {/* Platform summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {sumLoading ? (
          <div className="col-span-full text-sm text-neutral-500">Loading platforms...</div>
        ) : summaries && summaries.length > 0 ? (
          summaries.map((s) => <PlatformSummaryCard key={s.platform} summary={s} />)
        ) : (
          <div className="col-span-full rounded-lg border border-neutral-200 bg-white p-6 text-center text-sm text-neutral-500">
            No platforms configured. Publish an article to see platform stats.
          </div>
        )}
      </div>

      {/* Filters */}
      <PublicationFilters
        activePlatform={platform}
        activeStatus={status}
        onPlatformChange={(p) => { setPlatform(p); setPage(1); }}
        onStatusChange={(s) => { setStatus(s); setPage(1); }}
        totalCount={total}
        platforms={platformNames}
      />

      {/* Publications table */}
      {pubLoading ? (
        <div className="text-sm text-neutral-500">Loading publications...</div>
      ) : (
        <PublicationsTable
          publications={publications}
          onRetry={(id) => retryMutation.mutate(id)}
          retryingId={retryMutation.isPending ? (retryMutation.variables ?? null) : null}
        />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-md px-3 py-1 text-sm text-neutral-600 hover:bg-neutral-100 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-neutral-500">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-md px-3 py-1 text-sm text-neutral-600 hover:bg-neutral-100 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS (no breaking changes to other pages)

- [ ] **Step 3: Run frontend build to verify no type errors**

Run: `cd frontend && npx next build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\(dashboard\)/publishing/page.tsx
git commit -m "feat: replace publishing placeholder with full dashboard page"
```

---

## Task 11: Run Full Test Suite + Lint

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `uv run pytest tests/unit/ -q`
Expected: ALL PASS

- [ ] **Step 2: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 3: Run linter**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
Expected: No errors. If format issues, fix with `uv run ruff format src/ tests/`

- [ ] **Step 4: Run mypy**

Run: `uv run mypy src/ --ignore-missing-imports`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 5: Fix any issues found, then commit**

```bash
git add -A
git commit -m "fix: lint and type fixes for publication tracking"
```

---

## Task 12: Update PROGRESS.md and BACKLOG.md

**Files:**
- Modify: `project-management/PROGRESS.md`
- Modify: `project-management/BACKLOG.md`

- [ ] **Step 1: Update PROGRESS.md**

Change PUBLISH-005 row in the Epic 5 table:
- Status: `Done`
- Branch: `feature/PUBLISH-005-publication-tracking`
- Plan: `[plan](../docs/superpowers/plans/2026-03-27-publish-005-publication-tracking.md)`
- Spec: `[spec](../docs/superpowers/specs/2026-03-27-publish-005-publication-tracking-design.md)`

- [ ] **Step 2: Update BACKLOG.md**

Move PUBLISH-005 from the Active Backlog section to Completed under Epic 5. Add `— DONE` suffix. Update the summary table: Publishing remaining drops from 3 to 2, remaining SP from 15 to 10, total remaining from 4 to 3, total remaining SP from 18 to 13.

- [ ] **Step 3: Commit**

```bash
git add project-management/PROGRESS.md project-management/BACKLOG.md
git commit -m "docs: mark PUBLISH-005 as done in PROGRESS.md and BACKLOG.md"
```
