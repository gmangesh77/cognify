# CONTENT-003: SEO & AI Discoverability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `seo_optimize` pipeline node that generates traditional SEO metadata (meta title, description, keywords) and AI discoverability fields (summary, key_claims, JSON-LD, provenance) via two LLM calls.

**Architecture:** New `seo_optimize` node added after `validate_article` in the content LangGraph pipeline. Two LLM calls (SEO + AI discoverability), JSON-LD assembled programmatically. `ContentService` refactored to use `ContentDeps` dataclass for dependency injection. SEO node lives in a separate `seo_node.py` to keep `nodes.py` under 200 lines.

**Tech Stack:** Python 3.12+, LangGraph, LangChain FakeLLM, Pydantic, pytest, structlog, pydantic-settings

**Spec:** `docs/superpowers/specs/2026-03-19-content-003-seo-ai-discoverability-design.md`

**Test command:** `uv run pytest --cov=src --cov-report=term-missing`

**Single test:** `uv run pytest tests/path/to/test.py::TestClass::test_name -v`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/models/content.py` | Modify | Add SchemaOrgAuthor, StructuredDataLD models; add structured_data to SEOMetadata |
| `src/models/content_pipeline.py` | Modify | Add AIDiscoverabilityResult, SEOResult models; extend ArticleDraft |
| `src/config/settings.py` | Modify | Add primary_model_name, drafting_model_name, embedding_version fields |
| `src/agents/content/seo_optimizer.py` | Create | generate_seo_metadata(), generate_ai_discoverability(), build_structured_data(), AI_DISCLOSURE_TEXT |
| `src/agents/content/seo_node.py` | Create | make_seo_node() factory for LangGraph pipeline |
| `src/agents/content/pipeline.py` | Modify | Add seo_optimize node, settings param to build_content_graph |
| `src/services/content_repositories.py` | Modify | Add ContentDeps dataclass |
| `src/services/content.py` | Modify | Refactor to use ContentDeps, store seo_result |
| `src/api/schemas/articles.py` | Modify | Add StructuredDataLDResponse, SEOResultResponse; extend ArticleDraftResponse |
| `src/api/routers/articles.py` | Modify | Update _get_content_service for ContentDeps |
| `tests/unit/models/test_content_pipeline_models.py` | Modify | Tests for new models |
| `tests/unit/agents/content/test_seo_optimizer.py` | Create | Tests for SEO + AI discoverability functions |
| `tests/unit/agents/content/test_pipeline.py` | Modify | Tests for seo_optimize node in graph |
| `tests/unit/services/test_content_service.py` | Modify | Tests for ContentDeps, seo_result storage |
| `tests/unit/api/test_article_endpoints.py` | Modify | Update fixtures for ContentDeps |

---

## Task 1: Data Models — StructuredDataLD, SEOResult, AIDiscoverabilityResult

**Files:**
- Modify: `src/models/content.py`
- Modify: `src/models/content_pipeline.py`
- Modify: `tests/unit/models/test_content_pipeline_models.py`

- [ ] **Step 1: Write failing tests for new models**

Add to `tests/unit/models/test_content_pipeline_models.py`:

```python
from src.models.content import SchemaOrgAuthor, StructuredDataLD
from src.models.content_pipeline import AIDiscoverabilityResult, SEOResult
from src.models.content import Provenance, SEOMetadata


class TestStructuredDataLD:
    def test_construct(self) -> None:
        ld = StructuredDataLD(
            headline="Test Article",
            description="A test.",
            keywords=["ai", "test"],
            date_published="2026-03-19T00:00:00Z",
            date_modified="2026-03-19T00:00:00Z",
        )
        assert ld.headline == "Test Article"
        assert ld.type == "Article"
        assert ld.context == "https://schema.org"

    def test_serializes_with_aliases(self) -> None:
        ld = StructuredDataLD(
            headline="Test",
            description="D",
            date_published="2026-03-19",
            date_modified="2026-03-19",
        )
        data = ld.model_dump(by_alias=True)
        assert data["@context"] == "https://schema.org"
        assert data["@type"] == "Article"
        assert data["datePublished"] == "2026-03-19"

    def test_frozen(self) -> None:
        ld = StructuredDataLD(
            headline="Test", description="D",
            date_published="2026-03-19", date_modified="2026-03-19",
        )
        with pytest.raises(ValidationError):
            ld.headline = "Changed"  # type: ignore[misc]


class TestAIDiscoverabilityResult:
    def test_construct(self) -> None:
        result = AIDiscoverabilityResult(
            summary="A concise summary of the article.",
            key_claims=["Claim 1 [1]", "Claim 2 [2]"],
        )
        assert len(result.key_claims) == 2

    def test_frozen(self) -> None:
        result = AIDiscoverabilityResult(
            summary="Summary", key_claims=["Claim"],
        )
        with pytest.raises(ValidationError):
            result.summary = "Changed"  # type: ignore[misc]


class TestSEOResult:
    def test_construct(self) -> None:
        from uuid import uuid4
        seo = SEOMetadata(title="Test Title for SEO", description="A test description for the article.")
        prov = Provenance(
            research_session_id=uuid4(),
            primary_model="claude-sonnet-4",
            drafting_model="claude-sonnet-4",
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="v1",
        )
        result = SEOResult(
            seo=seo, summary="Summary", key_claims=["Claim"],
            provenance=prov, ai_disclosure="Disclosure text",
        )
        assert result.summary == "Summary"
        assert result.provenance.primary_model == "claude-sonnet-4"

    def test_frozen(self) -> None:
        from uuid import uuid4
        seo = SEOMetadata(title="Test Title for SEO", description="A test description.")
        prov = Provenance(
            research_session_id=uuid4(), primary_model="m", drafting_model="m",
            embedding_model="e", embedding_version="v1",
        )
        result = SEOResult(
            seo=seo, summary="S", key_claims=["C"],
            provenance=prov, ai_disclosure="D",
        )
        with pytest.raises(ValidationError):
            result.summary = "Changed"  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/models/test_content_pipeline_models.py -v`

Expected: FAIL — imports not found.

- [ ] **Step 3: Add models to content.py and content_pipeline.py**

In `src/models/content.py`, add before the existing `SEOMetadata` class:

```python
class SchemaOrgAuthor(BaseModel, frozen=True):
    """Schema.org author for JSON-LD."""
    type: str = Field(default="Organization", alias="@type")
    name: str = "Cognify"

    model_config = ConfigDict(populate_by_name=True)


class StructuredDataLD(BaseModel, frozen=True):
    """Typed JSON-LD Schema.org Article structured data."""
    context: str = Field(default="https://schema.org", alias="@context")
    type: str = Field(default="Article", alias="@type")
    headline: str
    description: str
    keywords: list[str] = Field(default_factory=list)
    author: SchemaOrgAuthor = Field(default_factory=SchemaOrgAuthor)
    date_published: str = Field(alias="datePublished")
    date_modified: str = Field(alias="dateModified")

    model_config = ConfigDict(populate_by_name=True)
```

Add to `SEOMetadata`:
```python
    structured_data: StructuredDataLD | None = None
```

In `src/models/content_pipeline.py`, add after `SectionDraft`:

```python
class AIDiscoverabilityResult(BaseModel, frozen=True):
    """LLM-extracted summary and key claims."""
    summary: str = Field(max_length=500)
    key_claims: list[str] = Field(min_length=1, max_length=10)
```

Add after `AIDiscoverabilityResult`:

```python
from src.models.content import Provenance, SEOMetadata

class SEOResult(BaseModel, frozen=True):
    """Output of the seo_optimize pipeline node."""
    seo: SEOMetadata
    summary: str
    key_claims: list[str]
    provenance: Provenance
    ai_disclosure: str
```

Extend `ArticleDraft` with:
```python
    seo_result: SEOResult | None = None
```

Note: Be careful with import ordering — `content_pipeline.py` already imports `ContentType` from `content.py`. Add `Provenance` and `SEOMetadata` to that import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/models/test_content_pipeline_models.py -v`

- [ ] **Step 5: Run full test suite for regressions**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 6: Commit**

```bash
git add src/models/content.py src/models/content_pipeline.py tests/unit/models/test_content_pipeline_models.py
git commit -m "feat(content-003): add StructuredDataLD, AIDiscoverabilityResult, SEOResult models"
```

---

## Task 2: Settings Extension

**Files:**
- Modify: `src/config/settings.py`
- Modify: `tests/unit/test_settings.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_settings.py`:

```python
def test_model_name_defaults(self) -> None:
    s = Settings()
    assert s.primary_model_name == "claude-sonnet-4"
    assert s.drafting_model_name == "claude-sonnet-4"
    assert s.embedding_version == "v1"
    # embedding_model already exists
    assert s.embedding_model == "all-MiniLM-L6-v2"
```

- [ ] **Step 2: Run test — should fail**

Run: `uv run pytest tests/unit/test_settings.py -v`

- [ ] **Step 3: Add fields to Settings**

Add to `src/config/settings.py` after the existing `top_k_retrieval` field:

```python
    # Content pipeline model names (for Provenance tracking)
    primary_model_name: str = "claude-sonnet-4"
    drafting_model_name: str = "claude-sonnet-4"
    embedding_version: str = "v1"
```

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/test_settings.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/config/settings.py tests/unit/test_settings.py
git commit -m "feat(content-003): add model name settings for provenance tracking"
```

---

## Task 3: SEO Optimizer Module

**Files:**
- Create: `src/agents/content/seo_optimizer.py`
- Create: `tests/unit/agents/content/test_seo_optimizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_seo_optimizer.py`:

```python
"""Tests for SEO metadata and AI discoverability generation."""

import json
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.seo_optimizer import (
    AI_DISCLOSURE_TEXT,
    build_structured_data,
    generate_ai_discoverability,
    generate_seo_metadata,
)
from src.models.content import SEOMetadata, StructuredDataLD
from src.models.content_pipeline import (
    AIDiscoverabilityResult,
    CitationRef,
    SectionDraft,
)


def _seo_json() -> str:
    return json.dumps({
        "title": "Test Article About AI Security Trends",
        "description": "A comprehensive analysis of emerging AI security threats and mitigation strategies for 2026.",
        "keywords": ["AI security", "cybersecurity", "threat analysis", "2026 trends", "mitigation"],
    })


def _discoverability_json() -> str:
    return json.dumps({
        "summary": "This article examines emerging AI security threats in 2026 and provides actionable mitigation strategies.",
        "key_claims": [
            "AI-powered phishing attacks increased 300% in 2025 [1]",
            "Zero-trust architecture reduces breach risk by 60% [2]",
            "Most organizations lack AI-specific incident response plans [3]",
        ],
    })


def _make_section_drafts() -> list[SectionDraft]:
    return [
        SectionDraft(
            section_index=0, title="Introduction",
            body_markdown="AI security is evolving [1].",
            word_count=5,
            citations_used=[CitationRef(index=1, source_url="https://a.com", source_title="A")],
        ),
    ]


class TestGenerateSeoMetadata:
    async def test_happy_path(self) -> None:
        llm = FakeListChatModel(responses=[_seo_json()])
        result = await generate_seo_metadata("Test Article", "Body text here.", llm)
        assert isinstance(result, SEOMetadata)
        assert len(result.title) > 0
        assert len(result.keywords) > 0

    async def test_retries_on_bad_json(self) -> None:
        llm = FakeListChatModel(responses=["bad", _seo_json()])
        result = await generate_seo_metadata("Test", "Body.", llm)
        assert isinstance(result, SEOMetadata)

    async def test_raises_after_max_retries(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_seo_metadata("Test", "Body.", llm)


class TestGenerateAiDiscoverability:
    async def test_happy_path(self) -> None:
        llm = FakeListChatModel(responses=[_discoverability_json()])
        drafts = _make_section_drafts()
        citations = [CitationRef(index=1, source_url="https://a.com", source_title="A")]
        result = await generate_ai_discoverability(drafts, citations, llm)
        assert isinstance(result, AIDiscoverabilityResult)
        assert len(result.summary) > 0
        assert len(result.key_claims) >= 1

    async def test_retries_on_bad_json(self) -> None:
        llm = FakeListChatModel(responses=["bad", _discoverability_json()])
        result = await generate_ai_discoverability(_make_section_drafts(), [], llm)
        assert isinstance(result, AIDiscoverabilityResult)

    async def test_raises_after_max_retries(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_ai_discoverability(_make_section_drafts(), [], llm)

    async def test_truncates_long_summary(self) -> None:
        long_summary = "A" * 600 + ". Short sentence."
        data = json.dumps({"summary": long_summary, "key_claims": ["Claim [1]"]})
        llm = FakeListChatModel(responses=[data])
        result = await generate_ai_discoverability(_make_section_drafts(), [], llm)
        assert len(result.summary) <= 500


class TestBuildStructuredData:
    def test_builds_json_ld(self) -> None:
        seo = SEOMetadata(title="Test Title", description="Test desc.", keywords=["ai", "test"])
        result = build_structured_data(seo, "My Article", "2026-03-19T00:00:00Z")
        assert isinstance(result, StructuredDataLD)
        assert result.headline == "My Article"
        assert result.description == "Test desc."

    def test_serializes_with_schema_org_aliases(self) -> None:
        seo = SEOMetadata(title="T", description="D", keywords=["k"])
        result = build_structured_data(seo, "Title", "2026-03-19")
        data = result.model_dump(by_alias=True)
        assert data["@context"] == "https://schema.org"
        assert data["@type"] == "Article"
        assert "datePublished" in data


class TestAiDisclosureConstant:
    def test_is_nonempty_string(self) -> None:
        assert isinstance(AI_DISCLOSURE_TEXT, str)
        assert len(AI_DISCLOSURE_TEXT) > 0
```

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/agents/content/test_seo_optimizer.py -v`

- [ ] **Step 3: Implement seo_optimizer.py**

Create `src/agents/content/seo_optimizer.py`:

```python
"""SEO metadata and AI discoverability generation.

Two LLM calls: one for traditional SEO (title, description, keywords),
one for AI discoverability (summary, key_claims). JSON-LD structured
data assembled programmatically. AI disclosure is a static constant.
"""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.content import SEOMetadata, StructuredDataLD
from src.models.content_pipeline import (
    AIDiscoverabilityResult,
    CitationRef,
    SectionDraft,
)

logger = structlog.get_logger()

_MAX_RETRIES = 2

AI_DISCLOSURE_TEXT = (
    "This article was generated using AI research and writing tools. "
    "All claims are sourced and cited."
)

_SEO_SYSTEM = (
    "You are an SEO specialist. Generate optimized metadata for this "
    "article. Respond with valid JSON only: "
    '{"title": "50-60 chars", "description": "150-160 chars", '
    '"keywords": ["5-10 keywords"]}'
)

_DISCOVERABILITY_SYSTEM = (
    "You are a content analyst. Extract a concise 1-2 sentence summary "
    "(max 500 chars) and 3-5 key factual claims with citation indices "
    "from this article. Respond with valid JSON only: "
    '{"summary": "...", "key_claims": ["claim [1]...", ...]}'
)

_MAX_SUMMARY_LEN = 500


async def generate_seo_metadata(
    article_title: str,
    body_text: str,
    llm: BaseChatModel,
) -> SEOMetadata:
    """Generate SEO title, description, and keywords via LLM."""
    user_msg = f"Article: {article_title}\n\n{body_text[:3000]}"
    messages = [SystemMessage(content=_SEO_SYSTEM), HumanMessage(content=user_msg)]
    return await _parse_seo_response(llm, messages)


async def generate_ai_discoverability(
    section_drafts: list[SectionDraft],
    citations: list[CitationRef],
    llm: BaseChatModel,
) -> AIDiscoverabilityResult:
    """Extract summary and key claims via LLM."""
    user_msg = _build_discoverability_prompt(section_drafts, citations)
    messages = [SystemMessage(content=_DISCOVERABILITY_SYSTEM), HumanMessage(content=user_msg)]
    return await _parse_discoverability_response(llm, messages)


def build_structured_data(
    seo: SEOMetadata,
    article_title: str,
    generated_at: str,
) -> StructuredDataLD:
    """Assemble JSON-LD Schema.org Article from SEO metadata."""
    result = StructuredDataLD(
        headline=article_title,
        description=seo.description,
        keywords=list(seo.keywords),
        date_published=generated_at,
        date_modified=generated_at,
    )
    logger.info("structured_data_assembled", schema_type="Article")
    return result


def _build_discoverability_prompt(
    drafts: list[SectionDraft],
    citations: list[CitationRef],
) -> str:
    sections = "\n\n".join(f"## {d.title}\n{d.body_markdown}" for d in drafts)
    cites = "\n".join(f"[{c.index}] {c.source_title} ({c.source_url})" for c in citations)
    return f"Article content:\n{sections}\n\nSources:\n{cites}"


async def _parse_seo_response(
    llm: BaseChatModel,
    messages: list[SystemMessage | HumanMessage],
) -> SEOMetadata:
    """Call LLM, parse JSON into SEOMetadata. Retry on failure."""
    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = json.loads(str(response.content))
            result = SEOMetadata.model_validate(data)
            logger.info("seo_metadata_generated", title_len=len(result.title), description_len=len(result.description), keyword_count=len(result.keywords))
            return result
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("seo_parse_failed", attempt=attempt + 1, error=str(exc))
    raise ValueError(f"Failed to generate SEO metadata after {_MAX_RETRIES} attempts")


async def _parse_discoverability_response(
    llm: BaseChatModel,
    messages: list[SystemMessage | HumanMessage],
) -> AIDiscoverabilityResult:
    """Call LLM, parse JSON into AIDiscoverabilityResult. Retry on failure."""
    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = json.loads(str(response.content))
            data = _maybe_truncate_summary(data)
            result = AIDiscoverabilityResult.model_validate(data)
            logger.info("ai_discoverability_generated", summary_len=len(result.summary), key_claims_count=len(result.key_claims))
            return result
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("discoverability_parse_failed", attempt=attempt + 1, error=str(exc))
    raise ValueError(f"Failed to generate AI discoverability after {_MAX_RETRIES} attempts")


def _maybe_truncate_summary(data: dict[str, object]) -> dict[str, object]:
    """Truncate summary at sentence boundary if over limit."""
    summary = str(data.get("summary", ""))
    if len(summary) <= _MAX_SUMMARY_LEN:
        return data
    logger.warning("summary_truncated", original_len=len(summary))
    truncated = summary[:_MAX_SUMMARY_LEN].rsplit(".", 1)[0] + "."
    return {**data, "summary": truncated}
```

Each parse function has exactly 2 params, returns a typed model, and uses typed `list[SystemMessage | HumanMessage]` for messages.

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/agents/content/test_seo_optimizer.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/agents/content/seo_optimizer.py tests/unit/agents/content/test_seo_optimizer.py
git commit -m "feat(content-003): add SEO metadata and AI discoverability generator"
```

---

## Task 4: SEO Node Factory

**Files:**
- Create: `src/agents/content/seo_node.py`

- [ ] **Step 1: Implement seo_node.py**

Create `src/agents/content/seo_node.py`:

```python
"""SEO optimize node factory for the content pipeline graph.

Separate file from nodes.py to keep both under 200 lines.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.content.seo_optimizer import (
    AI_DISCLOSURE_TEXT,
    build_structured_data,
    generate_ai_discoverability,
    generate_seo_metadata,
)
from src.config.settings import Settings
from src.models.content import Provenance, SEOMetadata
from src.models.content_pipeline import (
    ArticleOutline,
    CitationRef,
    SEOResult,
    SectionDraft,
)

if TYPE_CHECKING:
    from src.agents.content.pipeline import ContentState

logger = structlog.get_logger()


def make_seo_node(llm: BaseChatModel, settings: Settings | None = None) -> Any:
    """Factory: returns async node function for seo_optimize."""
    resolved = settings or Settings()

    async def seo_node(state: ContentState) -> dict[str, object]:
        try:
            return await _run_seo(state, llm, resolved)
        except Exception as exc:
            logger.error("seo_optimize_failed", error=str(exc))
            return {"status": "failed", "error": str(exc)}

    return seo_node


async def _run_seo(
    state: ContentState,
    llm: BaseChatModel,
    settings: Settings,
) -> dict[str, object]:
    """Execute SEO optimization: two LLM calls + programmatic assembly."""
    outline = _coerce_outline(state)
    drafts = _coerce_drafts(state)
    body_text = "\n\n".join(d.body_markdown for d in drafts)
    citations = _collect_citations(drafts)

    seo = await generate_seo_metadata(outline.title, body_text, llm)
    ai_result = await generate_ai_discoverability(drafts, citations, llm)

    generated_at = datetime.now(UTC).isoformat()
    structured = build_structured_data(seo, outline.title, generated_at)
    seo_with_ld = seo.model_copy(update={"structured_data": structured})
    provenance = _build_provenance(state, settings)

    result = SEOResult(
        seo=seo_with_ld, summary=ai_result.summary,
        key_claims=list(ai_result.key_claims),
        provenance=provenance, ai_disclosure=AI_DISCLOSURE_TEXT,
    )
    logger.info("seo_optimize_complete", has_seo=True, has_summary=True, has_key_claims=True)
    return {"seo_result": result}


def _coerce_outline(state: ContentState) -> ArticleOutline:
    o = state["outline"]
    return o if isinstance(o, ArticleOutline) else ArticleOutline.model_validate(o)


def _coerce_drafts(state: ContentState) -> list[SectionDraft]:
    raw = state.get("section_drafts", [])
    return [d if isinstance(d, SectionDraft) else SectionDraft.model_validate(d) for d in raw]


def _collect_citations(drafts: list[SectionDraft]) -> list[CitationRef]:
    seen: dict[str, CitationRef] = {}
    for d in drafts:
        for c in d.citations_used:
            if c.source_url not in seen:
                seen[c.source_url] = c
    return list(seen.values())


def _build_provenance(state: ContentState, settings: Settings) -> Provenance:
    session_id = state["session_id"]
    if not isinstance(session_id, UUID):
        session_id = UUID(str(session_id))
    return Provenance(
        research_session_id=session_id,
        primary_model=settings.primary_model_name,
        drafting_model=settings.drafting_model_name,
        embedding_model=settings.embedding_model,
        embedding_version=settings.embedding_version,
    )
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest --tb=short -q`

(No dedicated tests for seo_node.py yet — pipeline tests in Task 6 will cover it.)

- [ ] **Step 3: Commit**

```bash
git add src/agents/content/seo_node.py
git commit -m "feat(content-003): add SEO node factory for content pipeline"
```

---

## Task 5: ContentDeps Refactor + Service Extension

**Files:**
- Modify: `src/services/content_repositories.py`
- Modify: `src/services/content.py`
- Modify: `tests/unit/services/test_content_service.py`
- Modify: `tests/unit/api/test_article_endpoints.py`
- Modify: `src/api/routers/articles.py`

This is the breaking change task. All call sites must be updated.

- [ ] **Step 1: Write failing tests**

Update `tests/unit/services/test_content_service.py`:

Replace the existing `_make_service` and `_make_service_with_retriever` helpers to use `ContentDeps`:

```python
from src.services.content_repositories import ContentDeps

async def _make_service(
    session: ResearchSession | None = None,
) -> tuple[ContentService, ResearchSession]:
    session = session or _make_complete_session()
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)
    llm = FakeListChatModel(responses=[_outline_json()])
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
    )
    deps = ContentDeps(llm=llm)
    return ContentService(repos, deps), session
```

Add test:

```python
class TestContentDeps:
    async def test_service_uses_deps(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        assert draft.outline is not None

    # test_draft_article_includes_seo_result moved to Task 6 (requires pipeline wiring)
```

The `_make_service_with_retriever` helper needs additional FakeLLM responses for the SEO node (SEO metadata JSON + AI discoverability JSON).

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/services/test_content_service.py::TestContentDeps -v`

- [ ] **Step 3: Add ContentDeps to content_repositories.py**

Add to `src/services/content_repositories.py`:

```python
from langchain_core.language_models import BaseChatModel
from src.services.milvus_retriever import MilvusRetriever
from src.config.settings import Settings

@dataclass(frozen=True)
class ContentDeps:
    """Bundled dependencies for ContentService."""
    llm: BaseChatModel
    retriever: MilvusRetriever | None = None
    settings: Settings | None = None
```

- [ ] **Step 4: Refactor ContentService to use ContentDeps**

Update `src/services/content.py`:
- Change `__init__` to take `(repos, deps: ContentDeps)`
- Replace `self._llm` with `self._deps.llm`
- Replace `self._retriever` with `self._deps.retriever`
- Update `_run_pipeline` and `_run_drafting` to pass `self._deps.settings` to `build_content_graph`
- Update `_store_drafted` to also store `seo_result` from pipeline result
- Update `__all__` to include `ContentDeps`
- **File size**: `content.py` is at 202 lines (pre-existing violation). The ContentDeps refactor replaces 3 `__init__` params with 1, saving ~2 lines. The `_store_drafted` update adds ~3 lines for `seo_result`. Net change is small. If the file exceeds 205 lines, extract `_aggregate_citations` to `content_repositories.py`.

- [ ] **Step 5: Update API factory**

Update `src/api/routers/articles.py` `_get_content_service` — no code change needed if the factory reads from `app.state.content_service` (already constructed externally).

- [ ] **Step 6: Update ALL test fixtures**

Update `tests/unit/services/test_content_service.py` and `tests/unit/api/test_article_endpoints.py` — all places that construct `ContentService(repos, llm, ...)` must use `ContentService(repos, ContentDeps(llm=llm, ...))`.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest --tb=short -q`

All tests must pass.

- [ ] **Step 8: Commit**

```bash
git add src/services/content_repositories.py src/services/content.py tests/unit/services/test_content_service.py tests/unit/api/test_article_endpoints.py src/api/routers/articles.py
git commit -m "feat(content-003): refactor ContentService to use ContentDeps, store seo_result"
```

---

## Task 6: Pipeline Integration — Wire seo_optimize Node

**Files:**
- Modify: `src/agents/content/pipeline.py`
- Modify: `tests/unit/agents/content/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/agents/content/test_pipeline.py`:

```python
def _seo_json() -> str:
    return json.dumps({
        "title": "Test SEO Title for the Article",
        "description": "A test description that is long enough to pass validation for the SEO metadata.",
        "keywords": ["test", "seo", "ai"],
    })

def _discoverability_json() -> str:
    return json.dumps({
        "summary": "Test summary of the article content.",
        "key_claims": ["Key claim one [1]", "Key claim two [1]"],
    })


class TestContentPipelineWithSEO:
    async def test_full_graph_produces_seo_result(self) -> None:
        responses = [
            _outline_json(),         # outline
            _queries_json(2),        # queries
            "Draft section 0 [1].",  # draft section 0
            "Draft section 1 [1].",  # draft section 1
            _seo_json(),             # SEO metadata
            _discoverability_json(), # AI discoverability
        ]
        llm = FakeListChatModel(responses=responses)
        retriever = _mock_retriever()
        graph = build_content_graph(llm, retriever=retriever)
        result = await graph.ainvoke({
            "topic": _make_topic(),
            "research_plan": _make_plan(),
            "findings": _make_findings(),
            "session_id": uuid4(),
            "outline": None,
            "status": "outline_generating",
            "error": None,
        })
        assert result.get("seo_result") is not None
        assert result["seo_result"].summary != ""

    async def test_seo_failure_sets_failed(self) -> None:
        responses = [
            _outline_json(),
            _queries_json(2),
            "Draft section 0 [1].",
            "Draft section 1 [1].",
            "bad seo json",
            "bad seo json",
        ]
        llm = FakeListChatModel(responses=responses)
        retriever = _mock_retriever()
        graph = build_content_graph(llm, retriever=retriever)
        result = await graph.ainvoke({
            "topic": _make_topic(),
            "research_plan": _make_plan(),
            "findings": _make_findings(),
            "session_id": uuid4(),
            "outline": None,
            "status": "outline_generating",
            "error": None,
        })
        assert result["status"] == "failed"
```

Also add to `tests/unit/services/test_content_service.py` (the test moved from Task 5):

```python
class TestDraftArticleWithSEO:
    async def test_draft_article_includes_seo_result(self) -> None:
        svc, session = await _make_service_with_retriever()
        outline_draft = await svc.generate_outline(session.id)
        result = await svc.draft_article(outline_draft.id)
        assert result.seo_result is not None
        assert result.seo_result.summary != ""
        assert len(result.seo_result.key_claims) >= 1
```

The `_make_service_with_retriever` helper must include additional FakeLLM responses for the SEO node: append `_seo_json()` and `_discoverability_json()` to the responses list.

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/agents/content/test_pipeline.py::TestContentPipelineWithSEO tests/unit/services/test_content_service.py::TestDraftArticleWithSEO -v`

- [ ] **Step 3: Wire seo_optimize node into pipeline.py**

Update `src/agents/content/pipeline.py`:

Add import:
```python
from src.agents.content.seo_node import make_seo_node
from src.config.settings import Settings
```

Add `settings` parameter to `build_content_graph`:
```python
def build_content_graph(
    llm: BaseChatModel,
    retriever: MilvusRetriever | None = None,
    settings: Settings | None = None,
) -> CompiledStateGraph:
```

Add `seo_result: NotRequired[SEOResult]` to `ContentState`. Add import for `SEOResult`.

When retriever is not None, add:
```python
graph.add_node("seo_optimize", make_seo_node(llm, settings))
```

Change `validate_article → END` edge to `validate_article → seo_optimize`:
```python
graph.add_edge("validate_article", "seo_optimize")
graph.add_edge("seo_optimize", END)
```

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/agents/content/test_pipeline.py -v`

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 6: Commit**

```bash
git add src/agents/content/pipeline.py tests/unit/agents/content/test_pipeline.py
git commit -m "feat(content-003): wire seo_optimize node into content pipeline"
```

---

## Task 7: API Schema Extension

**Files:**
- Modify: `src/api/schemas/articles.py`

- [ ] **Step 1: Add response schemas**

Add to `src/api/schemas/articles.py`:

```python
class StructuredDataLDResponse(BaseModel):
    headline: str
    description: str
    keywords: list[str]
    date_published: str
    date_modified: str


class SEOResultResponse(BaseModel):
    title: str
    description: str
    keywords: list[str]
    summary: str
    key_claims: list[str]
    ai_disclosure: str
    structured_data: StructuredDataLDResponse | None = None
```

Extend `ArticleDraftResponse`:
```python
    seo_result: SEOResultResponse | None = None
```

Update `_to_draft_response` in `articles.py` router to map `draft.seo_result` to `SEOResultResponse` when present.

- [ ] **Step 2: Run existing tests for regressions**

Run: `uv run pytest tests/unit/api/test_article_endpoints.py -v`

- [ ] **Step 3: Commit**

```bash
git add src/api/schemas/articles.py src/api/routers/articles.py
git commit -m "feat(content-003): add SEO result response schemas"
```

---

## Task 8: Final Integration Test & Cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite with coverage**

Run: `uv run pytest --cov=src --cov-report=term-missing --tb=short`

- [ ] **Step 2: Run linting**

Run: `uv run ruff check src/ && uv run ruff format --check src/`

- [ ] **Step 3: Run type checking**

Run: `uv run mypy src/`

- [ ] **Step 4: Format code**

Run: `uv run ruff format src/ tests/`

- [ ] **Step 5: Final commit if needed**

```bash
git add -u
git commit -m "chore(content-003): format, fix lint, update types"
```

- [ ] **Step 6: Update PROGRESS.md**

Change CONTENT-003 row to In Progress with branch and plan/spec links.

```bash
git add project-management/PROGRESS.md
git commit -m "docs: update PROGRESS.md — CONTENT-003 in progress"
```
