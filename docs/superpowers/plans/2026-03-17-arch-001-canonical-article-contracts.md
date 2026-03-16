# ARCH-001: CanonicalArticle Model & Content Contracts — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the Pydantic models and Protocol definitions that establish the content pipeline boundary between content generation and publishing.

**Architecture:** Pure data contracts in `src/models/` — no behavior, no I/O. Two files: `content.py` (CanonicalArticle + supporting models) and `publishing.py` (PlatformPayload, PublicationResult, Transformer/Adapter protocols). TDD with pytest.

**Tech Stack:** Python 3.12+, Pydantic v2, typing.Protocol, StrEnum, pytest

**Spec:** [`docs/superpowers/specs/2026-03-17-arch-001-canonical-article-contracts-design.md`](../specs/2026-03-17-arch-001-canonical-article-contracts-design.md)

---

## Chunk 1: Content Models

### Task 1: Content Model Tests

**Files:**
- Create: `tests/unit/models/__init__.py`
- Create: `tests/unit/models/test_content.py`

- [ ] **Step 1: Create test directory**

```bash
mkdir -p tests/unit/models
touch tests/unit/models/__init__.py
```

Ensure `tests/unit/__init__.py` and `tests/__init__.py` also exist:

```bash
touch tests/__init__.py tests/unit/__init__.py
```

- [ ] **Step 2: Write content model tests**

Create `tests/unit/models/test_content.py`:

```python
"""Tests for content pipeline models."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
)


def _make_seo() -> SEOMetadata:
    return SEOMetadata(
        title="Test Article Title",
        description="A test article description for SEO purposes.",
        keywords=["test", "article"],
    )


def _make_citation() -> Citation:
    return Citation(index=1, title="Source Paper", url="https://example.com/paper")


def _make_provenance() -> Provenance:
    return Provenance(
        research_session_id=uuid4(),
        primary_model="claude-opus-4",
        drafting_model="claude-sonnet-4",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="1.0.0",
    )


def _make_article(**overrides: object) -> CanonicalArticle:
    defaults = {
        "title": "Test Article",
        "body_markdown": "# Heading\n\nBody content [1].",
        "summary": "A test article summary.",
        "key_claims": ["Claim one backed by source [1]."],
        "content_type": ContentType.ARTICLE,
        "seo": _make_seo(),
        "citations": [_make_citation()],
        "authors": ["Cognify Research"],
        "domain": "cybersecurity",
        "provenance": _make_provenance(),
    }
    defaults.update(overrides)
    return CanonicalArticle(**defaults)


class TestSEOMetadata:
    def test_valid_construction(self):
        seo = SEOMetadata(
            title="Valid Title",
            description="Valid description.",
            keywords=["seo"],
        )
        assert seo.title == "Valid Title"
        assert seo.canonical_url is None

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            SEOMetadata(title="", description="Valid.")

    def test_title_over_max_rejected(self):
        with pytest.raises(ValidationError):
            SEOMetadata(title="x" * 71, description="Valid.")

    def test_empty_description_rejected(self):
        with pytest.raises(ValidationError):
            SEOMetadata(title="Valid", description="")

    def test_description_over_max_rejected(self):
        with pytest.raises(ValidationError):
            SEOMetadata(title="Valid", description="x" * 171)


class TestCitation:
    def test_valid_construction(self):
        c = Citation(index=1, title="Paper", url="https://example.com")
        assert c.index == 1
        assert c.authors == []
        assert c.published_at is None

    def test_index_zero_rejected(self):
        with pytest.raises(ValidationError):
            Citation(index=0, title="Paper", url="https://example.com")

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            Citation(index=1, title="", url="https://example.com")


class TestImageAsset:
    def test_valid_construction(self):
        img = ImageAsset(url="https://example.com/image.png")
        assert isinstance(img.id, UUID)
        assert img.caption is None
        assert img.metadata == {}

    def test_metadata_accepts_mixed_types(self):
        img = ImageAsset(
            url="https://example.com/img.png",
            metadata={"width": 1024, "height": 768, "format": "png", "dpi": 72.0},
        )
        assert img.metadata["width"] == 1024
        assert img.metadata["format"] == "png"


class TestProvenance:
    def test_valid_construction(self):
        p = _make_provenance()
        assert isinstance(p.research_session_id, UUID)
        assert p.primary_model == "claude-opus-4"

    def test_empty_model_rejected(self):
        with pytest.raises(ValidationError):
            Provenance(
                research_session_id=uuid4(),
                primary_model="",
                drafting_model="claude-sonnet-4",
                embedding_model="all-MiniLM-L6-v2",
                embedding_version="1.0.0",
            )


class TestContentType:
    def test_values(self):
        assert ContentType.ARTICLE == "article"
        assert ContentType.HOW_TO == "how-to"
        assert ContentType.ANALYSIS == "analysis"
        assert ContentType.REPORT == "report"


class TestCanonicalArticle:
    def test_valid_construction(self):
        article = _make_article()
        assert isinstance(article.id, UUID)
        assert article.title == "Test Article"
        assert article.ai_generated is True
        assert isinstance(article.generated_at, datetime)

    def test_round_trip_serialization(self):
        article = _make_article()
        data = article.model_dump()
        restored = CanonicalArticle.model_validate(data)
        assert restored.title == article.title
        assert restored.citations[0].index == 1

    def test_frozen_immutability(self):
        article = _make_article()
        with pytest.raises(ValidationError):
            article.title = "Modified"

    def test_missing_title_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(title=None)

    def test_empty_citations_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(citations=[])

    def test_empty_authors_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(authors=[])

    def test_empty_key_claims_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(key_claims=[])

    def test_invalid_content_type_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(content_type="blog-post")

    def test_optional_subtitle_none(self):
        article = _make_article(subtitle=None)
        assert article.subtitle is None

    def test_optional_visuals_empty(self):
        article = _make_article(visuals=[])
        assert article.visuals == []

    def test_default_id_generated(self):
        a1 = _make_article()
        a2 = _make_article()
        assert a1.id != a2.id

    def test_nested_invalid_seo_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(seo=SEOMetadata(title="", description="Valid."))

    def test_missing_body_markdown_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(body_markdown=None)

    def test_missing_summary_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(summary=None)

    def test_missing_seo_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(seo=None)

    def test_missing_provenance_rejected(self):
        with pytest.raises(ValidationError):
            _make_article(provenance=None)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_content.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.content'`

- [ ] **Step 4: Commit test file**

```bash
git add tests/unit/models/
git commit -m "test(arch-001): add content model validation tests (red phase)"
```

---

### Task 2: Implement Content Models

**Files:**
- Modify: `src/models/__init__.py`
- Create: `src/models/content.py`

- [ ] **Step 1: Create content models**

Create `src/models/content.py`:

```python
"""Content pipeline models — the canonical article boundary.

These models define the contract between content generation (Epics 2-4)
and publishing (Epic 5). See ADR-003 for rationale.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ContentType(StrEnum):
    """Article content type. Maps to Schema.org @type in platform transformers."""

    ARTICLE = "article"
    HOW_TO = "how-to"
    ANALYSIS = "analysis"
    REPORT = "report"


class SEOMetadata(BaseModel):
    """Platform-neutral SEO defaults."""

    title: str = Field(min_length=1, max_length=70)
    description: str = Field(min_length=1, max_length=170)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    canonical_url: str | None = None


class Citation(BaseModel):
    """Source reference for inline citations."""

    index: int = Field(ge=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None


class ImageAsset(BaseModel):
    """Reference to a visual asset (chart, illustration, diagram)."""

    id: UUID = Field(default_factory=uuid4)
    url: str = Field(min_length=1)
    caption: str | None = None
    alt_text: str | None = None
    metadata: dict[str, str | int | float] = Field(default_factory=dict)


class Provenance(BaseModel):
    """Tracks which models and versions produced the article."""

    research_session_id: UUID
    primary_model: str = Field(min_length=1)
    drafting_model: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    embedding_version: str = Field(min_length=1)


class CanonicalArticle(BaseModel):
    """The central content pipeline contract.

    Output of content generation, input to all publishing transformers.
    Frozen after construction — downstream consumers must not mutate it.
    """

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

- [ ] **Step 2: Run tests to verify they pass**

```bash
"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_content.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/models/content.py
git commit -m "feat(arch-001): add CanonicalArticle and supporting content models"
```

---

## Chunk 2: Publishing Contracts

### Task 3: Publishing Contract Tests

**Files:**
- Create: `tests/unit/models/test_publishing.py`

- [ ] **Step 1: Write publishing contract tests**

Create `tests/unit/models/test_publishing.py`:

```python
"""Tests for publishing contract models and protocols."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.publishing import (
    Adapter,
    PlatformPayload,
    PublicationResult,
    PublicationStatus,
    Transformer,
)
from src.models.content import CanonicalArticle


class TestPlatformPayload:
    def test_valid_construction(self):
        payload = PlatformPayload(
            platform="ghost",
            article_id=uuid4(),
            content="<h1>Title</h1><p>Body</p>",
        )
        assert payload.platform == "ghost"
        assert payload.metadata == {}

    def test_empty_platform_rejected(self):
        with pytest.raises(ValidationError):
            PlatformPayload(
                platform="",
                article_id=uuid4(),
                content="content",
            )

    def test_metadata_accepts_mixed_types(self):
        payload = PlatformPayload(
            platform="wordpress",
            article_id=uuid4(),
            content="content",
            metadata={"featured": True, "word_count": 1500, "slug": "test-post"},
        )
        assert payload.metadata["featured"] is True
        assert payload.metadata["word_count"] == 1500

    def test_serialization_round_trip(self):
        payload = PlatformPayload(
            platform="ghost",
            article_id=uuid4(),
            content="<p>Body</p>",
            metadata={"tag": "test"},
        )
        data = payload.model_dump()
        restored = PlatformPayload.model_validate(data)
        assert restored.platform == payload.platform


class TestPublicationStatus:
    def test_values(self):
        assert PublicationStatus.SUCCESS == "success"
        assert PublicationStatus.FAILED == "failed"
        assert PublicationStatus.SCHEDULED == "scheduled"


class TestPublicationResult:
    def test_success_result(self):
        result = PublicationResult(
            article_id=uuid4(),
            platform="ghost",
            status=PublicationStatus.SUCCESS,
            external_id="abc123",
            external_url="https://blog.example.com/post/abc123",
            published_at=datetime.now(UTC),
        )
        assert result.status == PublicationStatus.SUCCESS
        assert result.error_message is None

    def test_failed_result(self):
        result = PublicationResult(
            article_id=uuid4(),
            platform="ghost",
            status=PublicationStatus.FAILED,
            error_message="Invalid API key",
        )
        assert result.status == PublicationStatus.FAILED
        assert result.error_message == "Invalid API key"
        assert result.external_id is None

    def test_scheduled_result(self):
        result = PublicationResult(
            article_id=uuid4(),
            platform="wordpress",
            status=PublicationStatus.SCHEDULED,
        )
        assert result.status == PublicationStatus.SCHEDULED


class TestTransformerProtocol:
    def test_class_satisfies_protocol(self):
        class MockTransformer:
            def transform(self, article: CanonicalArticle) -> PlatformPayload:
                return PlatformPayload(
                    platform="test",
                    article_id=article.id,
                    content=article.body_markdown,
                )

        assert isinstance(MockTransformer(), Transformer)

    def test_non_conforming_class_fails(self):
        class NotATransformer:
            def do_something(self) -> None:
                pass

        assert not isinstance(NotATransformer(), Transformer)


class TestAdapterProtocol:
    def test_class_satisfies_protocol(self):
        class MockAdapter:
            async def publish(
                self,
                payload: PlatformPayload,
                schedule_at: datetime | None = None,
            ) -> PublicationResult:
                return PublicationResult(
                    article_id=payload.article_id,
                    platform=payload.platform,
                    status=PublicationStatus.SUCCESS,
                )

        assert isinstance(MockAdapter(), Adapter)

    def test_non_conforming_class_fails(self):
        class NotAnAdapter:
            def upload(self) -> None:
                pass

        assert not isinstance(NotAnAdapter(), Adapter)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_publishing.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.publishing'`

- [ ] **Step 3: Commit test file**

```bash
git add tests/unit/models/test_publishing.py
git commit -m "test(arch-001): add publishing contract tests (red phase)"
```

---

### Task 4: Implement Publishing Contracts

**Files:**
- Create: `src/models/publishing.py`

- [ ] **Step 1: Create publishing contracts**

Create `src/models/publishing.py`:

```python
"""Publishing pipeline contracts — transformer/adapter protocols.

These protocols define the contract between the Publishing Service
and platform-specific implementations. See ADR-004 for rationale.
"""

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.content import CanonicalArticle


class PlatformPayload(BaseModel):
    """Base model for platform-specific output.

    Each platform transformer subclasses this with platform-specific fields.
    """

    platform: str = Field(min_length=1)
    article_id: UUID
    content: str = Field(min_length=1)
    metadata: dict[str, str | int | bool] = Field(default_factory=dict)


class PublicationStatus(StrEnum):
    """Status of a publish operation."""

    SUCCESS = "success"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class PublicationResult(BaseModel):
    """Result of a publish operation returned by adapters."""

    article_id: UUID
    platform: str
    status: PublicationStatus
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    error_message: str | None = None


@runtime_checkable
class Transformer(Protocol):
    """Pure function contract: CanonicalArticle -> PlatformPayload.

    No I/O. Must be unit-testable without mocks.
    """

    def transform(self, article: CanonicalArticle) -> PlatformPayload: ...


@runtime_checkable
class Adapter(Protocol):
    """I/O contract: PlatformPayload -> external platform API.

    Raise exceptions for transient/retryable failures (network, rate limit).
    Return PublicationResult(status=FAILED) for permanent failures.
    """

    async def publish(
        self,
        payload: PlatformPayload,
        schedule_at: datetime | None = None,
    ) -> PublicationResult: ...
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_publishing.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/models/publishing.py
git commit -m "feat(arch-001): add publishing contracts (PlatformPayload, Transformer, Adapter protocols)"
```

---

## Chunk 3: Module Exports & Final Verification

### Task 5: Module Exports and Full Suite

**Files:**
- Modify: `src/models/__init__.py`

- [ ] **Step 1: Update module exports**

Replace `src/models/__init__.py` with:

```python
"""Core domain models and cross-cutting contracts."""

from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
)
from src.models.publishing import (
    Adapter,
    PlatformPayload,
    PublicationResult,
    PublicationStatus,
    Transformer,
)

__all__ = [
    "CanonicalArticle",
    "Citation",
    "ContentType",
    "ImageAsset",
    "Provenance",
    "SEOMetadata",
    "Adapter",
    "PlatformPayload",
    "PublicationResult",
    "PublicationStatus",
    "Transformer",
]
```

- [ ] **Step 2: Run full test suite**

```bash
"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v
```

Expected: All tests pass (existing tests + new model tests).

- [ ] **Step 3: Run linting**

```bash
"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/models/ tests/unit/models/
```

Expected: No errors.

- [ ] **Step 4: Run type checking**

```bash
"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify mypy src/models/ --strict
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add src/models/__init__.py
git commit -m "feat(arch-001): add module exports for content and publishing contracts"
```
