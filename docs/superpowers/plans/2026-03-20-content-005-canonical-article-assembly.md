# CONTENT-005: CanonicalArticle Assembly — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assemble all intermediate pipeline outputs into a complete, validated `CanonicalArticle` — the platform-neutral contract between content generation and publishing. Completes Epic 3.

**Architecture:** Pure assembly function in `article_assembler.py` compiles section drafts, SEO metadata, citations, and provenance into a `CanonicalArticle`. `ContentService.finalize_article()` orchestrates: load draft, validate readiness, assemble, store, update status. New `ArticleRepository` for article persistence. Two new API endpoints: POST finalize + GET article.

**Tech Stack:** Python 3.12+, Pydantic, FastAPI, pytest, structlog

**Spec:** `docs/superpowers/specs/2026-03-20-content-005-canonical-article-assembly-design.md`

**Test command:** `uv run pytest --cov=src --cov-report=term-missing`

**Single test:** `uv run pytest tests/path/to/test.py::TestClass::test_name -v`

**Worktree:** `D:\Workbench\github\cognify-content-005` (branch `feature/CONTENT-005-canonical-article-assembly`)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/models/content_pipeline.py` | Modify | Add `article_id`, `global_citations`, `references_markdown` to ArticleDraft |
| `src/services/content_repositories.py` | Modify | Add ArticleRepository protocol, InMemoryArticleRepository, extend ContentRepositories |
| `src/agents/content/article_assembler.py` | Create | assemble_canonical_article(), body compilation, citation transform, validation |
| `src/services/content.py` | Modify | Add finalize_article(), update _store_drafted to persist global_citations |
| `src/api/schemas/articles.py` | Modify | Add CanonicalArticleResponse, CitationResponse, ProvenanceResponse, SEOMetadataResponse, ImageAssetResponse |
| `src/api/routers/articles.py` | Modify | Add POST finalize + GET article endpoints |
| `tests/unit/models/test_content_pipeline_models.py` | Modify | Tests for new ArticleDraft fields |
| `tests/unit/agents/content/test_article_assembler.py` | Create | Tests for assembly logic |
| `tests/unit/services/test_content_service.py` | Modify | Tests for finalize_article() |
| `tests/unit/api/test_article_endpoints.py` | Modify | Tests for new endpoints |

---

## Task 1: Extend ArticleDraft + ArticleRepository

**Files:**
- Modify: `src/models/content_pipeline.py`
- Modify: `src/services/content_repositories.py`
- Modify: `tests/unit/models/test_content_pipeline_models.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/models/test_content_pipeline_models.py`:

```python
class TestArticleDraftExtended:
    def test_article_id_default_none(self) -> None:
        draft = ArticleDraft(
            session_id=uuid4(), topic_id=uuid4(), created_at=datetime.now(UTC),
        )
        assert draft.article_id is None

    def test_global_citations_default_empty(self) -> None:
        draft = ArticleDraft(
            session_id=uuid4(), topic_id=uuid4(), created_at=datetime.now(UTC),
        )
        assert draft.global_citations == []
        assert draft.references_markdown == ""
```

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/models/test_content_pipeline_models.py::TestArticleDraftExtended -v`

- [ ] **Step 3: Add fields to ArticleDraft**

Add to `ArticleDraft` in `src/models/content_pipeline.py` (after `seo_result`):

```python
    article_id: UUID | None = None
    global_citations: list[dict[str, object]] = Field(default_factory=list)  # Citation dicts from pipeline; assembler converts via Citation.model_validate()
    references_markdown: str = ""
```

Note: `global_citations` uses `dict[str, object]` because LangGraph's TypedDict state serializes Pydantic models to dicts. The assembler's `_transform_citations()` converts back to `Citation` models. An alternative is storing `list[Citation]` and converting at `_store_drafted` time, but this adds complexity to the persistence layer for marginal type-safety gain.

- [ ] **Step 4: Add ArticleRepository to content_repositories.py**

Add to `src/services/content_repositories.py`:

```python
from src.models.content import CanonicalArticle


class ArticleRepository(Protocol):
    async def create(self, article: CanonicalArticle) -> CanonicalArticle: ...
    async def get(self, article_id: UUID) -> CanonicalArticle | None: ...


class InMemoryArticleRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, CanonicalArticle] = {}

    async def create(self, article: CanonicalArticle) -> CanonicalArticle:
        self._store[article.id] = article
        return article

    async def get(self, article_id: UUID) -> CanonicalArticle | None:
        return self._store.get(article_id)
```

Extend `ContentRepositories`:

```python
@dataclass(frozen=True)
class ContentRepositories:
    drafts: ArticleDraftRepository
    research: ResearchSessionReader
    articles: ArticleRepository
```

- [ ] **Step 5: Update all ContentRepositories call sites**

This is a breaking change. Search for `ContentRepositories(` across all test files and add the `articles` parameter. Files to update:
- `tests/unit/services/test_content_service.py` — all `_make_service*` helpers
- `tests/unit/api/test_article_endpoints.py` — all app fixtures

Add `articles=InMemoryArticleRepository()` to each.

- [ ] **Step 6: Run tests — all should pass**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 7: Commit**

```bash
git add src/models/content_pipeline.py src/services/content_repositories.py tests/unit/models/test_content_pipeline_models.py tests/unit/services/test_content_service.py tests/unit/api/test_article_endpoints.py
git commit -m "feat(content-005): extend ArticleDraft, add ArticleRepository, extend ContentRepositories"
```

---

## Task 2: Update _store_drafted to persist global_citations

**Files:**
- Modify: `src/services/content.py`

- [ ] **Step 1: Update _store_drafted**

In `src/services/content.py`, update `_store_drafted` (around line 168-195) to also persist `global_citations` and `references_markdown` from the pipeline result:

Add to the `model_copy` update dict:

```python
"global_citations": list(result.get("global_citations", [])),
"references_markdown": str(result.get("references_markdown", "")),
```

- [ ] **Step 2: Run full suite**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 3: Commit**

```bash
git add src/services/content.py
git commit -m "feat(content-005): persist global_citations and references_markdown on ArticleDraft"
```

---

## Task 3: Article Assembler

**Files:**
- Create: `src/agents/content/article_assembler.py`
- Create: `tests/unit/agents/content/test_article_assembler.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_article_assembler.py`:

```python
"""Tests for CanonicalArticle assembly from pipeline outputs."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.agents.content.article_assembler import assemble_canonical_article
from src.models.content import CanonicalArticle, ContentType, Provenance, SEOMetadata
from src.models.content_pipeline import (
    ArticleDraft,
    ArticleOutline,
    CitationRef,
    DraftStatus,
    OutlineSection,
    SectionDraft,
    SEOResult,
)
from src.models.research import TopicInput


def _make_topic() -> TopicInput:
    return TopicInput(id=uuid4(), title="Test Topic", description="Desc", domain="tech")


def _make_seo_result() -> SEOResult:
    seo = SEOMetadata(title="SEO Title Here Now", description="A test SEO description for the article.")
    prov = Provenance(
        research_session_id=uuid4(),
        primary_model="claude-sonnet-4",
        drafting_model="claude-sonnet-4",
        embedding_model="all-MiniLM-L6-v2",
        embedding_version="v1",
    )
    return SEOResult(
        seo=seo, summary="A concise test summary.", key_claims=["Claim one [1]", "Claim two [2]"],
        provenance=prov, ai_disclosure="AI generated.",
    )


def _make_section(index: int, word_count: int = 400) -> SectionDraft:
    words = " ".join(["word"] * word_count)
    return SectionDraft(
        section_index=index,
        title=f"Section {index}",
        body_markdown=words,
        word_count=word_count,
        citations_used=[CitationRef(index=1, source_url="https://a.com", source_title="A")],
    )


def _make_outline() -> ArticleOutline:
    return ArticleOutline(
        title="Test Article Title",
        subtitle="A subtitle",
        content_type="article",
        sections=[
            OutlineSection(index=0, title="Intro", description="D", key_points=["P"], target_word_count=400, relevant_facets=[0]),
            OutlineSection(index=1, title="Body", description="D", key_points=["P"], target_word_count=400, relevant_facets=[0]),
            OutlineSection(index=2, title="Conclusion", description="D", key_points=["P"], target_word_count=400, relevant_facets=[0]),
            OutlineSection(index=3, title="Analysis", description="D", key_points=["P"], target_word_count=400, relevant_facets=[0]),
        ],
        total_target_words=1600,
        reasoning="R",
    )


def _make_global_citations(count: int = 5) -> list[dict[str, object]]:
    return [
        {"index": i + 1, "title": f"Source {i}", "url": f"https://src{i}.com", "authors": [], "published_at": None}
        for i in range(count)
    ]


def _make_draft() -> ArticleDraft:
    return ArticleDraft(
        session_id=uuid4(),
        topic_id=uuid4(),
        outline=_make_outline(),
        status=DraftStatus.DRAFT_COMPLETE,
        created_at=datetime.now(UTC),
        section_drafts=[_make_section(0), _make_section(1), _make_section(2), _make_section(3)],
        seo_result=_make_seo_result(),
        global_citations=_make_global_citations(5),
        references_markdown="[1] Source 0 - https://src0.com\n",
    )


class TestAssembleCanonicalArticle:
    def test_happy_path(self) -> None:
        draft = _make_draft()
        topic = _make_topic()
        result = assemble_canonical_article(draft, topic)
        assert isinstance(result, CanonicalArticle)
        assert result.title == "Test Article Title"
        assert result.domain == "tech"
        assert result.ai_generated is True

    def test_body_has_h2_headings(self) -> None:
        draft = _make_draft()
        result = assemble_canonical_article(draft, _make_topic())
        assert "## Section 0" in result.body_markdown
        assert "## Section 1" in result.body_markdown

    def test_body_has_references_section(self) -> None:
        draft = _make_draft()
        result = assemble_canonical_article(draft, _make_topic())
        assert "## References" in result.body_markdown

    def test_citations_from_global_citations(self) -> None:
        draft = _make_draft()
        result = assemble_canonical_article(draft, _make_topic())
        assert len(result.citations) == 5
        assert result.citations[0].url == "https://src0.com"

    def test_summary_from_seo_result(self) -> None:
        draft = _make_draft()
        result = assemble_canonical_article(draft, _make_topic())
        assert result.summary == "A concise test summary."

    def test_provenance_from_seo_result(self) -> None:
        draft = _make_draft()
        result = assemble_canonical_article(draft, _make_topic())
        assert result.provenance.primary_model == "claude-sonnet-4"

    def test_visuals_empty(self) -> None:
        draft = _make_draft()
        result = assemble_canonical_article(draft, _make_topic())
        assert result.visuals == []

    def test_validation_fails_below_word_count(self) -> None:
        draft = _make_draft()
        # Replace sections with very short ones (total < 1500)
        short_drafts = [_make_section(i, word_count=100) for i in range(4)]
        draft = draft.model_copy(update={"section_drafts": short_drafts})
        with pytest.raises(ValueError, match="1500"):
            assemble_canonical_article(draft, _make_topic())

    def test_validation_fails_below_citation_count(self) -> None:
        draft = _make_draft()
        draft = draft.model_copy(update={"global_citations": _make_global_citations(3)})
        with pytest.raises(ValueError, match="5"):
            assemble_canonical_article(draft, _make_topic())
```

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/agents/content/test_article_assembler.py -v`

- [ ] **Step 3: Implement article_assembler.py**

Create `src/agents/content/article_assembler.py`:

```python
"""CanonicalArticle assembly from pipeline outputs.

Pure function — no LLM, no I/O. Compiles section drafts, SEO metadata,
citations, and provenance into the final CanonicalArticle contract.
"""

from datetime import UTC, datetime

import structlog
from pydantic import ValidationError

from src.models.content import CanonicalArticle, Citation
from src.models.content_pipeline import ArticleDraft, SectionDraft
from src.models.research import TopicInput

logger = structlog.get_logger()

_MIN_WORD_COUNT = 1500
_MIN_CITATIONS = 5


def assemble_canonical_article(
    draft: ArticleDraft,
    topic: TopicInput,
) -> CanonicalArticle:
    """Assemble a CanonicalArticle from a completed draft."""
    seo_result = draft.seo_result
    citations = _transform_citations(draft.global_citations)
    body = _compile_body(draft.section_drafts, draft.references_markdown)
    _validate_assembly(body, citations)
    return _build_article(draft, topic, body, citations)


def _compile_body(
    sections: list[SectionDraft],
    references_md: str,  # pre-computed by citation_manager; no need for _build_references helper (spec deviation: reuse existing markdown instead of regenerating)
) -> str:
    """Compile section drafts into a single markdown body with headings."""
    parts = []
    for s in sorted(sections, key=lambda x: x.section_index):
        parts.append(f"## {s.title}\n\n{s.body_markdown}")
    if references_md:
        parts.append(f"## References\n\n{references_md}")
    return "\n\n".join(parts)


def _transform_citations(
    global_citations: list[dict[str, object]],
) -> list[Citation]:
    """Deserialize global citation dicts into Citation models."""
    return [Citation.model_validate(c) for c in global_citations]


def _validate_assembly(body: str, citations: list[Citation]) -> None:
    """Validate business rules before Pydantic construction."""
    word_count = len(body.split())
    if word_count < _MIN_WORD_COUNT:
        msg = f"Article body is {word_count} words, minimum is {_MIN_WORD_COUNT}"
        raise ValueError(msg)
    if len(citations) < _MIN_CITATIONS:
        msg = f"Article has {len(citations)} citations, minimum is {_MIN_CITATIONS}"
        raise ValueError(msg)


def _build_article(
    draft: ArticleDraft,
    topic: TopicInput,
    body: str,
    citations: list[Citation],
) -> CanonicalArticle:
    """Construct the frozen CanonicalArticle."""
    seo = draft.seo_result
    try:
        article = CanonicalArticle(
            title=draft.outline.title,
            subtitle=draft.outline.subtitle,
            body_markdown=body,
            summary=seo.summary,
            key_claims=list(seo.key_claims),
            content_type=draft.outline.content_type,
            seo=seo.seo,
            citations=citations,
            authors=["Cognify"],
            domain=topic.domain,
            provenance=seo.provenance,
        )
    except ValidationError as exc:
        msg = f"CanonicalArticle validation failed: {exc}"
        raise ValueError(msg) from exc
    logger.info(
        "article_assembled",
        article_id=str(article.id),
        title=article.title,
        word_count=len(body.split()),
        citation_count=len(citations),
    )
    return article
```

NOTE: `_build_article` has 4 params. This exceeds max 3. The implementer should restructure — either bundle `body + citations` into a small dataclass, or pass them through the draft (but they're derived values). A pragmatic fix: since `_build_article` is private and the logic is straightforward, the implementer can combine `_validate_assembly` and `_build_article` into one function that takes `(draft, topic, body)` and derives citations internally. Or accept the 4-param private function with a comment. The implementer should decide.

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/agents/content/test_article_assembler.py -v`

- [ ] **Step 5: Run full suite**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 6: Commit**

```bash
git add src/agents/content/article_assembler.py tests/unit/agents/content/test_article_assembler.py
git commit -m "feat(content-005): add CanonicalArticle assembler with validation"
```

---

## Task 4: ContentService.finalize_article()

**Files:**
- Modify: `src/services/content.py`
- Modify: `tests/unit/services/test_content_service.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/services/test_content_service.py`:

```python
from src.models.content import CanonicalArticle


class TestFinalizeArticle:
    async def test_happy_path(self) -> None:
        svc, session = await _make_service_with_retriever()
        outline_draft = await svc.generate_outline(session.id)
        drafted = await svc.draft_article(outline_draft.id)
        result = await svc.finalize_article(drafted.id)
        assert isinstance(result, CanonicalArticle)
        assert result.title == drafted.outline.title
        assert result.domain == "tech"
        # Draft should be updated to COMPLETE
        updated_draft = await svc.get_draft(drafted.id)
        assert updated_draft.status == DraftStatus.COMPLETE
        assert updated_draft.article_id == result.id

    async def test_rejects_unknown_draft(self) -> None:
        svc, _ = await _make_service_with_retriever()
        with pytest.raises(NotFoundError):
            await svc.finalize_article(uuid4())

    async def test_rejects_non_draft_complete(self) -> None:
        svc, session = await _make_service_with_retriever()
        outline_draft = await svc.generate_outline(session.id)
        # Outline is in OUTLINE_COMPLETE, not DRAFT_COMPLETE
        with pytest.raises(ValueError, match="not ready"):
            await svc.finalize_article(outline_draft.id)

    async def test_rejects_no_seo_result(self) -> None:
        svc, session = await _make_service_with_retriever()
        outline_draft = await svc.generate_outline(session.id)
        drafted = await svc.draft_article(outline_draft.id)
        # Clear seo_result
        cleared = drafted.model_copy(update={"seo_result": None})
        await svc._repos.drafts.update(cleared)
        with pytest.raises(ValueError, match="SEO"):
            await svc.finalize_article(drafted.id)
```

IMPORTANT: The `_make_service_with_retriever` helper needs enough FakeLLM responses for the full pipeline including SEO. It must also produce section drafts with enough words (>= 1500 total) and enough citations (>= 5) to pass assembly validation. The helper may need updating — check its current state and add responses/fixtures as needed.

Also: the `_make_service_with_retriever` helper currently creates `ContentRepositories` without `articles`. Update it to include `articles=InMemoryArticleRepository()`.

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/services/test_content_service.py::TestFinalizeArticle -v`

- [ ] **Step 3: Implement finalize_article()**

Add to `src/services/content.py`:

```python
from src.agents.content.article_assembler import assemble_canonical_article
from src.models.content import CanonicalArticle

async def finalize_article(self, draft_id: UUID) -> CanonicalArticle:
    """Assemble a CanonicalArticle from a completed draft."""
    draft = await self.get_draft(draft_id)
    self._validate_finalize_ready(draft)
    session = await self._load_session(draft.session_id)
    topic = self._build_topic_input(session)
    article = assemble_canonical_article(draft, topic)
    return await self._store_article(draft, article)
```

Helper methods (each < 20 lines):

```python
def _validate_finalize_ready(self, draft: ArticleDraft) -> None:
    if draft.status != DraftStatus.DRAFT_COMPLETE:
        msg = f"Draft {draft.id} not ready for finalization"
        raise ValueError(msg)
    if draft.seo_result is None:
        msg = f"Draft {draft.id}: SEO optimization not completed"
        raise ValueError(msg)

async def _store_article(
    self, draft: ArticleDraft, article: CanonicalArticle
) -> CanonicalArticle:
    stored = await self._repos.articles.create(article)
    updated = draft.model_copy(update={
        "status": DraftStatus.COMPLETE,
        "article_id": article.id,
    })
    await self._repos.drafts.update(updated)
    logger.info("article_finalization_complete", draft_id=str(draft.id), article_id=str(article.id))
    return stored
```

Also add a `get_article` method for the GET endpoint:

```python
async def get_article(self, article_id: UUID) -> CanonicalArticle:
    article = await self._repos.articles.get(article_id)
    if article is None:
        raise NotFoundError(f"Article {article_id} not found")
    return article
```

**File size fix**: `content.py` is at 207 lines. Before adding finalize methods, extract `_aggregate_citations` (module-level function, lines 198-207) to `content_repositories.py`. This saves ~12 lines. Then add finalize_article + helpers (~25 lines). Net: ~220 lines — still over. Also move the `finalize_article`, `_validate_finalize_ready`, `_store_article`, and `get_article` methods into a new `src/services/content_finalize.py` module as standalone async functions that take `(repos, draft, ...)` params, and have `ContentService` delegate to them. This keeps `content.py` under 200.

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/services/test_content_service.py -v`

- [ ] **Step 5: Run full suite**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 6: Commit**

```bash
git add src/services/content.py tests/unit/services/test_content_service.py
git commit -m "feat(content-005): add finalize_article() to ContentService"
```

---

## Task 5: API Response Schemas

**Files:**
- Modify: `src/api/schemas/articles.py`

- [ ] **Step 1: Add response schemas**

Add to `src/api/schemas/articles.py`:

```python
class CitationResponse(BaseModel):
    index: int
    title: str
    url: str
    authors: list[str]
    published_at: datetime | None


class ProvenanceResponse(BaseModel):
    research_session_id: UUID
    primary_model: str
    drafting_model: str
    embedding_model: str
    embedding_version: str


class ImageAssetResponse(BaseModel):
    id: UUID
    url: str
    caption: str | None
    alt_text: str | None


class SEOMetadataResponse(BaseModel):
    title: str
    description: str
    keywords: list[str]
    canonical_url: str | None
    structured_data: StructuredDataLDResponse | None = None


class CanonicalArticleResponse(BaseModel):
    id: UUID
    title: str
    subtitle: str | None
    body_markdown: str
    summary: str
    key_claims: list[str]
    content_type: str
    seo: SEOMetadataResponse
    citations: list[CitationResponse]
    visuals: list[ImageAssetResponse]
    authors: list[str]
    domain: str
    generated_at: datetime
    provenance: ProvenanceResponse
    ai_generated: bool
```

Note: `StructuredDataLDResponse` already exists from CONTENT-003. Import it.

- [ ] **Step 2: Run existing tests**

Run: `uv run pytest tests/unit/api/test_article_endpoints.py -v`

- [ ] **Step 3: Commit**

```bash
git add src/api/schemas/articles.py
git commit -m "feat(content-005): add CanonicalArticleResponse and supporting schemas"
```

---

## Task 6: API Endpoints — POST finalize + GET article

**Files:**
- Modify: `src/api/routers/articles.py`
- Modify: `tests/unit/api/test_article_endpoints.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/api/test_article_endpoints.py`:

Create new fixtures for finalization tests — needs a draft in DRAFT_COMPLETE status with seo_result and enough data for assembly validation (>= 1500 words, >= 5 citations).

```python
class TestFinalizeArticle:
    async def test_returns_201(
        self, finalize_client: httpx.AsyncClient, auth_settings: Settings, finalized_draft_id: str,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await finalize_client.post(
            f"/api/v1/articles/drafts/{finalized_draft_id}/finalize",
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["title"] is not None
        assert data["ai_generated"] is True
        assert len(data["citations"]) >= 5

    async def test_viewer_cannot_finalize(
        self, finalize_client: httpx.AsyncClient, auth_settings: Settings, finalized_draft_id: str,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await finalize_client.post(
            f"/api/v1/articles/drafts/{finalized_draft_id}/finalize",
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_invalid_draft_returns_404(
        self, finalize_client: httpx.AsyncClient, auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await finalize_client.post(
            f"/api/v1/articles/drafts/{uuid4()}/finalize",
            headers=headers,
        )
        assert resp.status_code == 404


class TestGetArticle:
    async def test_returns_200(
        self, finalize_client: httpx.AsyncClient, auth_settings: Settings, finalized_draft_id: str,
    ) -> None:
        # First finalize to create the article
        headers = make_auth_header("editor", auth_settings)
        finalize_resp = await finalize_client.post(
            f"/api/v1/articles/drafts/{finalized_draft_id}/finalize",
            headers=headers,
        )
        article_id = finalize_resp.json()["id"]
        # Then GET it
        viewer_headers = make_auth_header("viewer", auth_settings)
        resp = await finalize_client.get(
            f"/api/v1/articles/{article_id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == article_id

    async def test_not_found_returns_404(
        self, finalize_client: httpx.AsyncClient, auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await finalize_client.get(
            f"/api/v1/articles/{uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 404
```

The `finalize_client` and `finalized_draft_id` fixtures need to set up:
1. A ContentService with retriever + InMemoryArticleRepository
2. Run the full pipeline (generate_outline + draft_article) to get a DRAFT_COMPLETE draft
3. The draft must have global_citations (>= 5), references_markdown, seo_result, and section_drafts with enough words

This fixture is complex — the implementer should study the existing `drafting_app` fixture pattern and extend it.

- [ ] **Step 2: Run tests — should fail**

Run: `uv run pytest tests/unit/api/test_article_endpoints.py::TestFinalizeArticle -v`

- [ ] **Step 3: Add endpoints**

Add to `src/api/routers/articles.py`:

```python
@limiter.limit("3/minute")
@articles_router.post(
    "/articles/drafts/{draft_id}/finalize",
    response_model=CanonicalArticleResponse,
    status_code=HTTP_201_CREATED,
)
async def finalize_article(
    request: Request,
    draft_id: str,
    user: TokenPayload = Depends(require_editor_or_above),
) -> CanonicalArticleResponse:
    svc = _get_content_service(request)
    article = await svc.finalize_article(UUID(draft_id))
    return _to_canonical_response(article)


@limiter.limit("30/minute")
@articles_router.get(
    "/articles/{article_id}",
    response_model=CanonicalArticleResponse,
)
async def get_article(
    request: Request,
    article_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> CanonicalArticleResponse:
    svc = _get_content_service(request)
    article = await svc.get_article(UUID(article_id))
    return _to_canonical_response(article)
```

Add `_to_canonical_response(article: CanonicalArticle) -> CanonicalArticleResponse` helper that maps the model to the response schema. Extract citation/provenance/seo mapping to sub-helpers to stay under 20 lines.

**File size fix**: `articles.py` is at 184 lines. Adding 2 endpoints + mapper = ~224 lines (over 200). Create `src/api/routers/canonical_articles.py` with the finalize + get-article endpoints and the `_to_canonical_response` helper. Register it in `src/api/main.py` with `prefix=settings.api_v1_prefix, tags=["articles"]`.

- [ ] **Step 4: Run tests — should pass**

Run: `uv run pytest tests/unit/api/test_article_endpoints.py -v`

- [ ] **Step 5: Run full suite**

Run: `uv run pytest --tb=short -q`

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/articles.py tests/unit/api/test_article_endpoints.py
# Also add canonical_articles.py and main.py if split
git commit -m "feat(content-005): add POST finalize and GET article endpoints"
```

---

## Task 7: Update BACKLOG + Final Cleanup

**Files:**
- All modified files
- `project-management/BACKLOG.md`
- `project-management/PROGRESS.md`

- [ ] **Step 1: Update BACKLOG.md**

Change the CONTENT-005 acceptance criteria to remove "New pipeline node: compile_article" and replace with "ContentService method: finalize_article" (per spec deviation decision).

- [ ] **Step 2: Run full test suite with coverage**

Run: `uv run pytest --cov=src --cov-report=term-missing --tb=short`

- [ ] **Step 3: Run linting**

Run: `uv run ruff check src/ --fix && uv run ruff format src/ tests/`

- [ ] **Step 4: Run type checking**

Run: `uv run mypy src/`

- [ ] **Step 5: Commit fixes**

```bash
git add -u
git commit -m "chore(content-005): format, fix lint, update types, update BACKLOG"
```

- [ ] **Step 6: Update PROGRESS.md**

Set CONTENT-005 to In Progress with branch and plan/spec links.

```bash
git add project-management/PROGRESS.md
git commit -m "docs: update PROGRESS.md — CONTENT-005 in progress"
```
