# ARCH-001: CanonicalArticle Model & Content Contracts — Design Spec

## 1. Overview

**Ticket**: ARCH-001 — CanonicalArticle Model & Content Contracts
**Goal**: Define the core Pydantic models and Protocol definitions that establish the content pipeline boundary between content generation (Epics 2-4) and publishing (Epic 5). These are pure data contracts — no behavior, no I/O, no API endpoints.

**ADR references**:
- [ADR-003: CanonicalArticle as Content Pipeline Boundary](../../architecture/adrs/ADR-003-canonical-article-boundary.md)
- [ADR-004: Centralized Publishing with Transformer/Adapter Pattern](../../architecture/adrs/ADR-004-publishing-transformer-adapter-pattern.md)

**Key principle**: Everything upstream (research, drafting, SEO) produces a `CanonicalArticle`. Everything downstream (Ghost formatting, WordPress blocks, Medium markdown) consumes it. These two worlds share only the canonical schema.

## 2. File Structure

```
src/models/
    __init__.py           # Re-exports all public models and protocols
    content.py            # CanonicalArticle and supporting models
    publishing.py         # PlatformPayload, PublicationResult, Transformer/Adapter protocols
tests/unit/models/
    __init__.py
    test_content.py       # Content model validation tests
    test_publishing.py    # Publishing contract tests
```

## 3. Content Models (`src/models/content.py`)

### SEOMetadata

Platform-neutral SEO defaults. Platform transformers may override for platform-specific constraints (e.g., Ghost meta title length differs from Medium).

```python
class SEOMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=70)
    description: str = Field(min_length=1, max_length=170)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    canonical_url: str | None = None
```

### Citation

Source reference for inline citations. Every factual claim in the article should reference one or more citations.

```python
class Citation(BaseModel):
    index: int = Field(ge=1)                # [1], [2], etc. — matches inline markers in body_markdown
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
```

### ImageAsset

Reference to a visual asset (chart, AI illustration, diagram). The actual file lives in S3 or local storage; this model holds the reference and metadata.

```python
class ImageAsset(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    url: str = Field(min_length=1)
    caption: str | None = None
    alt_text: str | None = None
    metadata: dict[str, str | int | float] = Field(default_factory=dict)
```

### Provenance

Tracks which models and versions produced the article. Required for reproducibility, auditing, and AI Act compliance.

```python
class Provenance(BaseModel):
    research_session_id: UUID
    primary_model: str = Field(min_length=1)
    drafting_model: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    embedding_version: str = Field(min_length=1)
```

### ContentType

Extensible enum for article types. Maps to Schema.org `@type` in platform transformers. Uses `StrEnum` for easy extension when new content types are needed (e.g., "tutorial", "news-brief"). Deliberate tightening from ADR-003's bare `str` sketch.

```python
class ContentType(StrEnum):
    ARTICLE = "article"
    HOW_TO = "how-to"
    ANALYSIS = "analysis"
    REPORT = "report"
```

### CanonicalArticle

The central contract. Output of the content generation pipeline, input to all publishing transformers. Frozen after construction — downstream consumers (transformers, adapters) must not mutate it.

```python
class CanonicalArticle(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = None
    body_markdown: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=500)
    key_claims: list[str] = Field(min_length=1, max_length=10)
    content_type: ContentType
    seo: SEOMetadata
    citations: list[Citation] = Field(min_length=1)
    visuals: list[ImageAsset] = Field(default_factory=list)
    authors: list[str] = Field(min_length=1)
    domain: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provenance: Provenance
    ai_generated: bool = True
```

**Validation rules**:
- `key_claims` must have at least 1 entry (top factual claims for AI discoverability)
- `citations` must have at least 1 entry (no uncited articles)
- `authors` must have at least 1 entry
- `content_type` uses `ContentType` StrEnum (extensible, maps to Schema.org `@type`). Tightened from ADR-003's bare `str` sketch for type safety.
- `seo.title` max 70 chars, `seo.description` max 170 chars (generous limits, platform transformers enforce tighter per-platform constraints)

## 4. Publishing Contracts (`src/models/publishing.py`)

### PlatformPayload

Base model for platform-specific output. Each platform transformer subclasses this with platform-specific fields (e.g., `GhostPayload` adds `html`, `tags`, `feature_image`).

```python
class PlatformPayload(BaseModel):
    platform: str = Field(min_length=1)
    article_id: UUID
    content: str = Field(min_length=1)
    metadata: dict[str, str | int | bool] = Field(default_factory=dict)
```

### PublicationResult

Result of a publish operation returned by adapters.

```python
class PublicationStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SCHEDULED = "scheduled"

class PublicationResult(BaseModel):
    article_id: UUID
    platform: str
    status: PublicationStatus
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    error_message: str | None = None
```

### Transformer Protocol

Pure function contract: takes a CanonicalArticle, returns a PlatformPayload. No I/O. Must be unit-testable without mocks.

```python
@runtime_checkable
class Transformer(Protocol):
    def transform(self, article: CanonicalArticle) -> PlatformPayload: ...
```

### Adapter Protocol

I/O contract: takes a PlatformPayload and publishes it. Handles authentication, HTTP calls, retries, error mapping.

```python
@runtime_checkable
class Adapter(Protocol):
    async def publish(
        self,
        payload: PlatformPayload,
        schedule_at: datetime | None = None,
    ) -> PublicationResult: ...
```

**Design notes**:
- Protocols live in `src/models/publishing.py` (not `src/services/publishing/protocols.py` as ADR-004 sketched) because they are pure contracts with no service-layer dependencies. This keeps all cross-cutting type definitions in one place.
- **Adapter error semantics**: Adapters should raise exceptions for transient/retryable failures (network errors, rate limits) so the Publishing Service can apply retry/backoff. Return `PublicationResult(status=FAILED)` for permanent failures (invalid credentials, content rejected by platform). The Publishing Service owns retry policy; adapters signal retry-ability via exception vs. return.

## 5. Module Exports (`src/models/__init__.py`)

```python
from .content import (
    CanonicalArticle,
    ContentType,
    SEOMetadata,
    Citation,
    ImageAsset,
    Provenance,
)
from .publishing import (
    PlatformPayload,
    PublicationResult,
    PublicationStatus,
    Transformer,
    Adapter,
)
```

## 6. Testing Strategy

### Content Model Tests (`tests/unit/models/test_content.py`)

- **Valid construction**: Build a complete `CanonicalArticle` with all required fields, verify it serializes/deserializes correctly via `model_dump()` / `model_validate()`
- **Required field validation**: Verify `ValidationError` when missing required fields (title, body_markdown, summary, citations, authors, seo, provenance)
- **Constraint validation**: Empty title rejected, empty citations list rejected, `content_type` outside literal union rejected, `seo.title` over 70 chars rejected
- **Optional fields**: `subtitle=None`, `visuals=[]` are valid
- **Default factories**: `id` auto-generates UUID, `generated_at` auto-generates datetime, `ai_generated` defaults to `True`
- **Nested model validation**: Invalid `SEOMetadata` (empty title) inside `CanonicalArticle` raises `ValidationError`

### Publishing Contract Tests (`tests/unit/models/test_publishing.py`)

- **PlatformPayload construction**: Valid construction and serialization
- **PublicationResult**: Test all status variants (success, failed, scheduled), optional fields (external_id, error_message)
- **Protocol structural typing**: Verify a class implementing `Transformer.transform()` satisfies `isinstance` check via `runtime_checkable` or structural typing test

## 7. Patterns & Conventions

- Follow existing Pydantic patterns from `src/api/schemas/topics.py` (Field descriptions, validators)
- No `Any` types (per CLAUDE.md)
- Protocol classes use `typing.Protocol` with `@runtime_checkable` (PEP 544), extending the pattern from `src/api/auth/repository.py`
- `CanonicalArticle` is frozen (`ConfigDict(frozen=True)`) — immutable after construction
- `datetime.now(UTC)` used for timestamps (not deprecated `datetime.utcnow`), consistent with existing codebase
- `StrEnum` for `PublicationStatus` (Python 3.11+, project uses 3.12+)

## 8. Out of Scope

- No API endpoints (RESEARCH-001, PUBLISH-001)
- No service layer or business logic
- No SQLAlchemy ORM models (added when persistence is needed)
- No TrendSource protocol (ARCH-002)
- No Transformer/Adapter implementations (PUBLISH-001+)
- No database migrations
