# PUBLISH-005: Publication Tracking — Design Spec

## Overview

Add persistent publication tracking so users can see all publications across platforms, monitor their status, retry failures from the dashboard, and view engagement metrics where available.

**Ticket**: PUBLISH-005 (Must, 5 SP)
**Depends on**: PUBLISH-001 (Ghost, done), PUBLISH-003 (Medium, done)

---

## 1. Database Schema

### New table: `publications`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | Publication record ID |
| `article_id` | UUID | FK → canonical_articles.id, NOT NULL | Source article |
| `platform` | VARCHAR(50) | NOT NULL | Platform name: "ghost", "medium", etc. |
| `status` | VARCHAR(20) | NOT NULL | "success", "failed", "scheduled" |
| `external_id` | VARCHAR(255) | NULLABLE | Platform's post ID |
| `external_url` | TEXT | NULLABLE | Public URL on platform |
| `published_at` | TIMESTAMP TZ | NULLABLE | When successfully published |
| `view_count` | INTEGER | NOT NULL, default 0 | Views from platform API (0 if unsupported) |
| `seo_score` | INTEGER | NOT NULL, default 0 | 0-100 computed from article SEO metadata |
| `error_message` | TEXT | NULLABLE | Latest error (null on success) |
| `event_history` | JSONB | NOT NULL, default [] | Append-only log of attempts |
| `created_at` | TIMESTAMP TZ | NOT NULL, default now | First publish attempt |
| `updated_at` | TIMESTAMP TZ | NOT NULL, default now | Last state change |

**Constraints:**
- Unique constraint on `(article_id, platform)` — one record per article-platform pair
- Index on `platform` for filtered queries
- Index on `status` for filtered queries

**Event history JSONB schema** (each entry):
```json
{
  "timestamp": "2026-03-27T10:00:00Z",
  "status": "failed",
  "error_message": "Connection timeout"
}
```

Retries update the top-level `status`, `external_id`, `external_url`, `published_at`, `error_message`, and `updated_at` columns, and append a new entry to `event_history`.

### SQLAlchemy model: `PublicationRow`

New table class in `src/db/tables.py`:

```python
class PublicationRow(Base):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("canonical_articles.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seo_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_history: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("article_id", "platform", name="uq_publication_article_platform"),
        Index("ix_publication_platform", "platform"),
        Index("ix_publication_status", "status"),
    )
```

### Alembic migration

New migration: `add_publications_table` — creates the `publications` table with all columns, constraints, and indexes.

---

## 2. Pydantic Models

### New models in `src/models/publishing.py`

**`Publication`** — domain model for a publication record:
```python
class Publication(BaseModel, frozen=True):
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
    event_history: list[PublicationEvent] = []
    created_at: datetime
    updated_at: datetime
```

**`PublicationEvent`** — single event in the history log:
```python
class PublicationEvent(BaseModel, frozen=True):
    timestamp: datetime
    status: PublicationStatus
    error_message: str | None = None
```

### API response models

**`PublicationResponse`** — single publication for API responses:
```python
class PublicationResponse(BaseModel):
    id: UUID
    article_id: UUID
    article_title: str  # denormalized for display
    platform: str
    status: PublicationStatus
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    view_count: int = 0
    seo_score: int = 0
    error_message: str | None = None
    event_history: list[PublicationEvent] = []
    created_at: datetime
    updated_at: datetime
```

**`PublicationListResponse`** — paginated list:
```python
class PublicationListResponse(BaseModel):
    items: list[PublicationResponse]
    total: int
    page: int
    size: int
```

**`PlatformSummary`** — per-platform stats for dashboard cards:
```python
class PlatformSummary(BaseModel):
    platform: str
    total: int
    success: int
    failed: int
    scheduled: int
```

---

## 3. SEO Score Computation

Computed from the parent article's `SEOMetadata` at publish time and stored on the publication row. Not recomputed — it's a snapshot.

| Field | Points | Check |
|-------|-------:|-------|
| `seo.title` | 20 | Non-empty string |
| `seo.description` | 20 | Non-empty string |
| `seo.keywords` | 20 | Non-empty list |
| `seo.canonical_url` | 15 | Non-empty string |
| `seo.structured_data` | 25 | Not None |
| **Total** | **100** | |

Function: `compute_seo_score(seo: SEOMetadata) -> int` in `src/services/publishing/service.py`.

---

## 4. Repository: `PgPublicationRepository`

New class in `src/db/repositories.py`:

```python
class PgPublicationRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None: ...

    async def create(self, publication: Publication) -> Publication
    async def get(self, publication_id: UUID) -> Publication | None
    async def get_by_article_platform(self, article_id: UUID, platform: str) -> Publication | None
    async def list(
        self,
        page: int = 1,
        size: int = 20,
        platform: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Publication], int]
    async def update(self, publication: Publication) -> Publication
    async def update_view_count(self, publication_id: UUID, count: int) -> None
    async def get_platform_summaries(self) -> list[PlatformSummary]
```

The `list` method joins `canonical_articles` to fetch `article_title` for the response. Orders by `updated_at DESC`.

---

## 5. Service Changes

### `PublishingService` modifications

**After `publish()` completes**, persist the result:
1. Compute SEO score from the article's `seo` metadata
2. Check if a `Publication` row exists for `(article_id, platform)`:
   - **Exists**: Update status, external_id, external_url, published_at, error_message, seo_score. Append new event to `event_history`.
   - **New**: Create row with initial event in `event_history`.

**New methods:**

```python
async def retry(self, publication_id: UUID) -> PublicationResult:
    """Load failed publication, re-run publish, update row."""
    pub = await self._pub_repo.get(publication_id)
    # Validate status is "failed"
    result = await self.publish(pub.article_id, pub.platform)
    return result

async def refresh_view_counts(self) -> int:
    """Fetch view counts from Ghost for all success publications. Returns count updated."""
    # For each Ghost publication with status=success and external_id:
    #   GET {ghost_api_url}/ghost/api/admin/posts/{external_id}/?fields=id,title
    #   Ghost doesn't expose views via Admin API directly — use Content API
    #   GET {ghost_api_url}/ghost/api/content/posts/{external_id}/?key={content_api_key}
    # Note: Ghost Content API doesn't expose view counts either in standard installs.
    # For MVP, skip actual Ghost view fetching. The schema supports it, and we can
    # wire it when Ghost Members/analytics is configured. Return 0 updated.

async def get_publications(self, page, size, platform, status) -> tuple[list[Publication], int]:
    """Delegate to repository."""

async def get_platform_summaries(self) -> list[PlatformSummary]:
    """Delegate to repository."""
```

**Constructor change**: Accept `pub_repo: PgPublicationRepository` as a new dependency.

---

## 6. API Endpoints

All in `src/api/routers/publishing.py`. All require authentication.

### `GET /api/v1/publications`
- **Auth**: `require_viewer_or_above`
- **Query params**: `page` (default 1), `size` (default 20), `platform` (optional), `status` (optional)
- **Response**: `PublicationListResponse` (200)
- **Rate limit**: `30/minute`

### `GET /api/v1/publications/summaries`
- **Auth**: `require_viewer_or_above`
- **Response**: `list[PlatformSummary]` (200)
- **Rate limit**: `30/minute`

### `GET /api/v1/publications/{publication_id}`
- **Auth**: `require_viewer_or_above`
- **Response**: `PublicationResponse` (200), 404 if not found
- **Rate limit**: `30/minute`

### `POST /api/v1/publications/{publication_id}/retry`
- **Auth**: `require_editor_or_above`
- **Response**: `PublicationResponse` (200), 404 if not found, 400 if status != "failed"
- **Rate limit**: `5/minute`

### Existing endpoint change

`POST /api/v1/articles/{article_id}/publish` — no API signature change. Internally, `PublishingService.publish()` now persists the result. The response stays `PublishResponse`.

---

## 7. Frontend

### Publishing page (`frontend/src/app/(dashboard)/publishing/page.tsx`)

Replace the `<PagePlaceholder>` with a functional dashboard.

**Layout:**

```
┌─────────────────────────────────────────────────┐
│  Publishing                                      │
├──────────┬──────────┬──────────┬────────────────┤
│  Ghost   │  Medium  │  (more)  │                │
│  12 pub  │  3 pub   │          │                │
│  10✓ 2✗  │  2✓ 1✗   │          │                │
├──────────┴──────────┴──────────┴────────────────┤
│  Filter: [All] [Ghost] [Medium] | [All] [Live]  │
│          [Failed] [Scheduled]                    │
├─────────────────────────────────────────────────┤
│  Article Title │ Platform │ Status │ Date │ ...  │
│  ─────────────────────────────────────────────── │
│  AI Trends...  │ Ghost    │ ✓ Live │ Mar 27│ ... │
│  Cloud Sec...  │ Medium   │ ✗ Fail │ Mar 26│ ... │
│  ...                                             │
├─────────────────────────────────────────────────┤
│  < 1 2 3 >                                       │
└─────────────────────────────────────────────────┘
```

**Platform summary cards** (top):
- Card per platform: name, total count, success/failed breakdown
- Styled per DESIGN.md card pattern: `rounded-lg border border-neutral-200 bg-white shadow-sm p-6`

**Filter bar:**
- Platform pills: All, Ghost, Medium (rounded-full, active = `bg-primary text-white`)
- Status pills: All, Live (success), Failed, Scheduled
- Matches existing filter pattern from Topics page

**Publications table:**
- Columns: Article Title, Platform, Status, Published Date, Views, SEO Score, Actions
- Status badges per DESIGN.md: success → `bg-success-light text-success`, failed → `bg-error-light text-error`, scheduled → `bg-warning-light text-warning`
- Views: number for Ghost, "N/A" for others
- SEO score: colored text (green >=80, yellow >=50, red <50)
- Actions: "View" (external link icon, opens external_url), "Retry" button (only on failed, shows spinner during request)
- Pagination at bottom

### Hooks (`frontend/src/hooks/use-publications.ts`)

```typescript
function usePublications(filters: { platform?: string; status?: string; page?: number })
  -> { publications: Publication[], total: number, isLoading: boolean, mutate }

function usePlatformSummaries()
  -> { summaries: PlatformSummary[], isLoading: boolean }
```

### API layer (`frontend/src/lib/api/publications.ts`)

```typescript
function getPublications(params: { page?, size?, platform?, status? }): Promise<PublicationListResponse>
function getPublication(id: string): Promise<PublicationResponse>
function getPlatformSummaries(): Promise<PlatformSummary[]>
function retryPublication(id: string): Promise<PublicationResponse>
```

### TypeScript types (`frontend/src/types/publishing.ts`)

```typescript
interface Publication {
  id: string
  article_id: string
  article_title: string
  platform: string
  status: "success" | "failed" | "scheduled"
  external_id?: string
  external_url?: string
  published_at?: string
  view_count: number
  seo_score: number
  error_message?: string
  event_history: PublicationEvent[]
  created_at: string
  updated_at: string
}

interface PublicationEvent {
  timestamp: string
  status: "success" | "failed" | "scheduled"
  error_message?: string
}

interface PlatformSummary {
  platform: string
  total: number
  success: number
  failed: number
  scheduled: number
}
```

---

## 8. Testing

### Backend unit tests (~30-40 tests)

**Repository tests** (`tests/unit/db/test_publication_repository.py`):
- Create publication, get by ID, get by article+platform
- List with pagination, filter by platform, filter by status
- Update status + event_history append
- Update view count
- Platform summaries aggregation
- Unique constraint on duplicate article+platform

**Service tests** (`tests/unit/services/test_publishing_service.py`):
- Publish persists result (new row)
- Publish updates existing row on re-publish
- Retry loads and re-publishes failed publication
- Retry rejects non-failed publications (400)
- SEO score computation: all fields present (100), partial fields, no fields (0)
- Event history appended on each attempt

**API tests** (`tests/unit/api/test_publication_endpoints.py`):
- GET /publications: auth check, pagination, filters
- GET /publications/{id}: auth check, 404
- POST /publications/{id}/retry: auth check (editor+), 404, 400 on non-failed
- GET /publications/summaries: auth check, response shape

### Frontend tests (~15-20 tests)

**Component tests:**
- Platform summary cards render counts correctly
- Publications table renders rows with correct badges/colors
- Filter pills toggle active state and refetch
- Retry button: shows spinner, calls API, updates row
- "N/A" shown for non-Ghost view counts
- SEO score color coding (green/yellow/red)
- Empty state when no publications
- Pagination navigation

---

## 9. Design Decisions

1. **Single table with JSONB history** over separate events table — simpler schema, sufficient for audit trail at current scale. If event volume grows large, migrate to a separate table later.
2. **SEO score as snapshot** — computed at publish time and stored, not recomputed. The article's SEO metadata doesn't change post-generation.
3. **View counts deferred** — Ghost Content API doesn't reliably expose view counts in standard installs. Schema supports it; wiring deferred until Ghost Members/analytics is configured. Shows 0 for now.
4. **Synchronous retry** — no background worker needed. `PublishingService.publish()` already has 3-retry exponential backoff. Frontend shows spinner during the call.
5. **Upsert on article+platform** — re-publishing to the same platform updates the existing row rather than creating duplicates.
