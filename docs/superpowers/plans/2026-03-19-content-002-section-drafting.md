# CONTENT-002: Section-by-Section Drafting with RAG — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the content pipeline to draft each article section sequentially using RAG-retrieved context from Milvus, with inline citations and word count validation.

**Architecture:** Three new LangGraph nodes (generate_queries, draft_sections, validate_article) added after the existing generate_outline node, with a conditional edge gating on retriever availability. Section drafting is sequential for narrative coherence, with LLM-generated retrieval queries per section. A DraftingContext dataclass bundles dependencies to respect the max 3 params rule.

**Tech Stack:** Python 3.12+, LangGraph, LangChain FakeLLM, Pydantic, pytest, structlog, MilvusRetriever (mocked in tests)

**Spec:** `docs/superpowers/specs/2026-03-19-content-002-section-drafting-design.md`

**Test command:** `uv run pytest --cov=src --cov-report=term-missing`

**Single test:** `uv run pytest tests/path/to/test.py::TestClass::test_name -v`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/models/content_pipeline.py` | Modify | Add CitationRef, SectionQueries, SectionDraft models; DRAFT_COMPLETE status |
| `src/agents/content/query_generator.py` | Create | LLM-based retrieval query generation per outline section |
| `src/agents/content/section_drafter.py` | Create | DraftingContext, RAG retrieval + LLM section drafting + citation extraction |
| `src/agents/content/pipeline.py` | Modify | Add 3 new nodes, conditional edge, retriever param |
| `src/services/content.py` | Modify | Add draft_article(), update(), retriever param |
| `src/api/schemas/articles.py` | Modify | Add CitationRefResponse, SectionDraftResponse, extend ArticleDraftResponse |
| `src/api/routers/articles.py` | Modify | Add POST /articles/drafts/{draft_id}/sections endpoint |
| `tests/unit/models/test_content_pipeline_models.py` | Modify | Tests for new models |
| `tests/unit/agents/content/test_query_generator.py` | Create | Tests for query generation |
| `tests/unit/agents/content/test_section_drafter.py` | Create | Tests for section drafting + citation extraction |
| `tests/unit/agents/content/test_pipeline.py` | Modify | Tests for extended graph |
| `tests/unit/agents/content/test_validate_article.py` | Create | Tests for validation node |
| `tests/unit/services/test_content_service.py` | Modify | Tests for draft_article() |
| `tests/unit/api/test_article_endpoints.py` | Modify | Tests for new endpoint |

---

## Task 1: Data Models — CitationRef, SectionQueries, SectionDraft

**Files:**
- Modify: `src/models/content_pipeline.py`
- Modify: `tests/unit/models/test_content_pipeline_models.py`

- [ ] **Step 1: Write failing tests for new models**

Add to `tests/unit/models/test_content_pipeline_models.py`:

```python
from src.models.content_pipeline import (
    CitationRef,
    DraftStatus,
    SectionDraft,
    SectionQueries,
)


class TestCitationRef:
    def test_construct(self) -> None:
        ref = CitationRef(index=1, source_url="https://a.com", source_title="A")
        assert ref.index == 1
        assert ref.source_url == "https://a.com"

    def test_frozen(self) -> None:
        ref = CitationRef(index=1, source_url="https://a.com", source_title="A")
        with pytest.raises(ValidationError):
            ref.index = 2  # type: ignore[misc]


class TestSectionQueries:
    def test_construct(self) -> None:
        sq = SectionQueries(section_index=0, queries=["q1", "q2"])
        assert sq.section_index == 0
        assert len(sq.queries) == 2

    def test_frozen(self) -> None:
        sq = SectionQueries(section_index=0, queries=["q1"])
        with pytest.raises(ValidationError):
            sq.section_index = 1  # type: ignore[misc]


class TestSectionDraft:
    def test_construct(self) -> None:
        ref = CitationRef(index=1, source_url="https://a.com", source_title="A")
        sd = SectionDraft(
            section_index=0,
            title="Intro",
            body_markdown="Text with [1] citation.",
            word_count=5,
            citations_used=[ref],
        )
        assert sd.title == "Intro"
        assert sd.word_count == 5
        assert len(sd.citations_used) == 1

    def test_frozen(self) -> None:
        sd = SectionDraft(
            section_index=0,
            title="Intro",
            body_markdown="Text",
            word_count=1,
            citations_used=[],
        )
        with pytest.raises(ValidationError):
            sd.title = "Changed"  # type: ignore[misc]


class TestDraftStatusExtended:
    def test_draft_complete_value(self) -> None:
        assert DraftStatus.DRAFT_COMPLETE == "draft_complete"

    def test_all_values(self) -> None:
        expected = {
            "outline_generating", "outline_complete",
            "drafting", "draft_complete", "complete", "failed",
        }
        assert {s.value for s in DraftStatus} == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/models/test_content_pipeline_models.py -v`

Expected: FAIL — `CitationRef`, `SectionQueries`, `SectionDraft` not importable, `DRAFT_COMPLETE` not found.

- [ ] **Step 3: Add new models to content_pipeline.py**

Add to `src/models/content_pipeline.py` after the `COMPLETE` line in `DraftStatus`:

```python
    DRAFT_COMPLETE = "draft_complete"
```

Add after the `ArticleOutline` class:

```python
class CitationRef(BaseModel, frozen=True):
    """Lightweight citation reference collected during drafting."""

    index: int
    source_url: str
    source_title: str


class SectionQueries(BaseModel, frozen=True):
    """Retrieval queries generated for one outline section."""

    section_index: int
    queries: list[str]


class SectionDraft(BaseModel, frozen=True):
    """Drafted content for one article section."""

    section_index: int
    title: str
    body_markdown: str
    word_count: int
    citations_used: list[CitationRef]
```

Extend `ArticleDraft` with new fields (add after `completed_at`):

```python
    section_drafts: list[SectionDraft] = Field(default_factory=list)
    citations: list[CitationRef] = Field(default_factory=list)
    total_word_count: int = 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/models/test_content_pipeline_models.py -v`

Expected: ALL PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `uv run pytest --tb=short -q`

Expected: All 576+ tests pass (existing tests unaffected by additive changes).

- [ ] **Step 6: Commit**

```bash
git add src/models/content_pipeline.py tests/unit/models/test_content_pipeline_models.py
git commit -m "feat(content-002): add CitationRef, SectionQueries, SectionDraft models"
```

---

## Task 2: Query Generator

**Files:**
- Create: `src/agents/content/query_generator.py`
- Create: `tests/unit/agents/content/test_query_generator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_query_generator.py`:

```python
"""Tests for LLM-based section query generation."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.query_generator import generate_section_queries
from src.models.content_pipeline import (
    ArticleOutline,
    OutlineSection,
    SectionQueries,
)


def _make_outline(section_count: int = 3) -> ArticleOutline:
    sections = [
        OutlineSection(
            index=i,
            title=f"Section {i}",
            description=f"Desc {i}",
            key_points=[f"Point {i}"],
            target_word_count=300,
            relevant_facets=[0],
        )
        for i in range(section_count)
    ]
    return ArticleOutline(
        title="Test",
        content_type="article",
        sections=sections,
        total_target_words=section_count * 300,
        reasoning="R",
    )


def _queries_json(section_count: int = 3) -> str:
    return json.dumps([
        {"section_index": i, "queries": [f"query {i}a", f"query {i}b"]}
        for i in range(section_count)
    ])


class TestGenerateSectionQueries:
    async def test_happy_path(self) -> None:
        llm = FakeListChatModel(responses=[_queries_json(3)])
        outline = _make_outline(3)
        result = await generate_section_queries(outline, llm)
        assert len(result) == 3
        assert all(isinstance(sq, SectionQueries) for sq in result)
        assert result[0].section_index == 0
        assert len(result[0].queries) == 2

    async def test_single_section(self) -> None:
        llm = FakeListChatModel(responses=[_queries_json(1)])
        outline = _make_outline(1)
        result = await generate_section_queries(outline, llm)
        assert len(result) == 1

    async def test_retries_on_bad_json(self) -> None:
        llm = FakeListChatModel(responses=["bad json", _queries_json(2)])
        outline = _make_outline(2)
        result = await generate_section_queries(outline, llm)
        assert len(result) == 2

    async def test_raises_after_max_retries(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        outline = _make_outline(2)
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_section_queries(outline, llm)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/agents/content/test_query_generator.py -v`

Expected: FAIL — `query_generator` module does not exist.

- [ ] **Step 3: Implement query_generator.py**

Create `src/agents/content/query_generator.py`:

```python
"""LLM-based retrieval query generation for article sections.

Generates 1-2 focused semantic search queries per outline section.
Single LLM call for all sections to avoid redundant queries.
"""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.content_pipeline import ArticleOutline, SectionQueries

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You are a research retrieval specialist. Given an article outline, "
    "generate 1-2 focused search queries per section for finding relevant "
    "passages in a knowledge base. Queries should be semantic and specific. "
    "Respond with valid JSON only."
)

_USER_TEMPLATE = (
    "Generate retrieval queries for each section:\n\n"
    "{sections_text}\n\n"
    "Return JSON array: "
    '[{{"section_index": 0, "queries": ["query1", "query2"]}}]'
)

_MAX_RETRIES = 2


def _format_sections(outline: ArticleOutline) -> str:
    lines = []
    for s in outline.sections:
        points = ", ".join(s.key_points)
        lines.append(f"Section {s.index}: {s.title} — {s.description} (key: {points})")
    return "\n".join(lines)


async def generate_section_queries(
    outline: ArticleOutline,
    llm: BaseChatModel,
) -> list[SectionQueries]:
    """Generate retrieval queries for all outline sections."""
    user_msg = _USER_TEMPLATE.format(sections_text=_format_sections(outline))
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_msg)]

    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = json.loads(response.content)
            result = [SectionQueries.model_validate(item) for item in data]
            logger.info(
                "section_queries_generated",
                section_count=len(result),
                total_queries=sum(len(sq.queries) for sq in result),
            )
            return result
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("query_generation_parse_failed", attempt=attempt + 1, error=str(exc))

    msg = f"Failed to generate section queries after {_MAX_RETRIES} attempts"
    raise ValueError(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_query_generator.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/content/query_generator.py tests/unit/agents/content/test_query_generator.py
git commit -m "feat(content-002): add LLM-based section query generator"
```

---

## Task 3: Section Drafter — DraftingContext, retrieval, drafting, citation extraction

**Files:**
- Create: `src/agents/content/section_drafter.py`
- Create: `tests/unit/agents/content/test_section_drafter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_section_drafter.py`:

```python
"""Tests for section drafter — RAG retrieval + LLM drafting + citation extraction."""

from unittest.mock import AsyncMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.section_drafter import (
    DraftingContext,
    draft_section,
    extract_citations,
)
from src.models.content_pipeline import (
    CitationRef,
    OutlineSection,
    SectionDraft,
    SectionQueries,
)
from src.models.research import ChunkResult


def _make_section(index: int = 0) -> OutlineSection:
    return OutlineSection(
        index=index,
        title=f"Section {index}",
        description=f"Description {index}",
        key_points=[f"Point {index}"],
        target_word_count=300,
        relevant_facets=[0],
    )


def _make_queries(index: int = 0) -> SectionQueries:
    return SectionQueries(section_index=index, queries=["query a", "query b"])


def _make_chunks(count: int = 5) -> list[ChunkResult]:
    return [
        ChunkResult(
            text=f"Chunk {i} content about the topic.",
            source_url=f"https://source{i}.com",
            source_title=f"Source {i}",
            score=0.9 - i * 0.1,
            chunk_index=i,
        )
        for i in range(count)
    ]


def _make_context(
    chunks: list[ChunkResult] | None = None,
    prior: list[SectionDraft] | None = None,
) -> DraftingContext:
    retriever = AsyncMock()
    retriever.retrieve = AsyncMock(return_value=chunks or _make_chunks())
    llm = FakeListChatModel(responses=[
        "This section discusses findings [1] and analysis [2]. More details [3]."
    ])
    return DraftingContext(
        retriever=retriever,
        topic_id="topic-123",
        llm=llm,
        prior_drafts=prior or [],
    )


class TestExtractCitations:
    def test_extracts_valid_refs(self) -> None:
        chunks = _make_chunks(3)
        text = "Fact one [1] and fact two [2]."
        refs = extract_citations(text, chunks)
        assert len(refs) == 2
        assert refs[0] == CitationRef(index=1, source_url="https://source0.com", source_title="Source 0")
        assert refs[1] == CitationRef(index=2, source_url="https://source1.com", source_title="Source 1")

    def test_ignores_invalid_refs(self) -> None:
        chunks = _make_chunks(2)
        text = "Valid [1] and invalid [5]."
        refs = extract_citations(text, chunks)
        assert len(refs) == 1
        assert refs[0].index == 1

    def test_no_citations(self) -> None:
        chunks = _make_chunks(3)
        refs = extract_citations("No citations here.", chunks)
        assert refs == []


class TestDraftSection:
    async def test_happy_path(self) -> None:
        ctx = _make_context()
        result = await draft_section(_make_section(), _make_queries(), ctx)
        assert isinstance(result, SectionDraft)
        assert result.section_index == 0
        assert result.title == "Section 0"
        assert result.word_count > 0
        assert len(result.citations_used) > 0
        ctx.retriever.retrieve.assert_called()

    async def test_deduplicates_chunks(self) -> None:
        # Same chunk from both queries
        chunk = ChunkResult(
            text="Dup", source_url="https://dup.com",
            source_title="Dup", score=0.9, chunk_index=0,
        )
        retriever = AsyncMock()
        retriever.retrieve = AsyncMock(return_value=[chunk])
        llm = FakeListChatModel(responses=["Text with [1] ref."])
        ctx = DraftingContext(
            retriever=retriever, topic_id="t", llm=llm, prior_drafts=[],
        )
        result = await draft_section(_make_section(), _make_queries(), ctx)
        # 2 queries but chunks deduped — should still work
        assert result.word_count > 0

    async def test_zero_chunks_fallback(self) -> None:
        ctx = _make_context(chunks=[])
        result = await draft_section(_make_section(), _make_queries(), ctx)
        assert isinstance(result, SectionDraft)
        assert result.citations_used == []

    async def test_prior_drafts_in_prompt(self) -> None:
        prior = SectionDraft(
            section_index=0, title="Intro",
            body_markdown="First sentence here. More text.",
            word_count=5, citations_used=[],
        )
        ctx = _make_context(prior=[prior])
        result = await draft_section(_make_section(1), _make_queries(1), ctx)
        assert isinstance(result, SectionDraft)
        # Verify LLM was called (prompt included prior context)
        ctx.retriever.retrieve.assert_called()

    async def test_word_count_correct(self) -> None:
        ctx = _make_context()
        result = await draft_section(_make_section(), _make_queries(), ctx)
        actual = len(result.body_markdown.split())
        assert result.word_count == actual
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/agents/content/test_section_drafter.py -v`

Expected: FAIL — `section_drafter` module does not exist.

- [ ] **Step 3: Implement section_drafter.py**

Create `src/agents/content/section_drafter.py`:

```python
"""Section drafter — RAG retrieval + LLM drafting + citation extraction.

Drafts a single article section grounded in retrieved research chunks.
Citations are extracted post-draft by matching [N] refs to source chunks.
"""

import re
from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.content_pipeline import (
    CitationRef,
    OutlineSection,
    SectionDraft,
    SectionQueries,
)
from src.models.research import ChunkResult
from src.services.milvus_retriever import MilvusRetriever

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You are an expert long-form writer. Draft a section of an article "
    "using the provided research context. Every factual claim must include "
    "an inline citation like [1], [2] referencing the numbered sources. "
    "Write in a clear, authoritative tone. Target approximately "
    "{target_word_count} words."
)

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class DraftingContext:
    """Shared dependencies for section drafting."""

    retriever: MilvusRetriever
    topic_id: str
    llm: BaseChatModel
    prior_drafts: list[SectionDraft]


async def draft_section(
    section: OutlineSection,
    queries: SectionQueries,
    ctx: DraftingContext,
) -> SectionDraft:
    """Draft one section using RAG context and LLM."""
    logger.info("section_draft_started", section_index=section.index, title=section.title)
    chunks = await _retrieve_chunks(queries, ctx)
    logger.info("section_chunks_retrieved", section_index=section.index, chunk_count=len(chunks), unique_sources=len({c.source_url for c in chunks}))
    text = await _call_llm(section, chunks, ctx)
    citations = extract_citations(text, chunks)
    word_count = len(text.split())
    _log_word_count(section, word_count, len(citations))
    return SectionDraft(
        section_index=section.index,
        title=section.title,
        body_markdown=text,
        word_count=word_count,
        citations_used=citations,
    )


async def _retrieve_chunks(
    queries: SectionQueries,
    ctx: DraftingContext,
) -> list[ChunkResult]:
    """Retrieve and deduplicate chunks across all queries."""
    seen: dict[tuple[str, int], ChunkResult] = {}
    for q in queries.queries:
        results = await ctx.retriever.retrieve(q, ctx.topic_id, top_k=5)
        for chunk in results:
            key = (chunk.source_url, chunk.chunk_index)
            if key not in seen or chunk.score > seen[key].score:
                seen[key] = chunk
    ranked = sorted(seen.values(), key=lambda c: c.score, reverse=True)
    return ranked[:5]


async def _call_llm(
    section: OutlineSection,
    chunks: list[ChunkResult],
    ctx: DraftingContext,
) -> str:
    """Build prompt and call LLM to draft section text."""
    system = _SYSTEM_PROMPT.format(target_word_count=section.target_word_count)
    user = _build_user_prompt(section, chunks, ctx.prior_drafts)
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    response = await ctx.llm.ainvoke(messages)
    return str(response.content)


def _build_user_prompt(
    section: OutlineSection,
    chunks: list[ChunkResult],
    prior_drafts: list[SectionDraft],
) -> str:
    """Assemble the user prompt with section info, RAG context, and prior summary."""
    parts = [
        f"## Section: {section.title}\n{section.description}",
        f"Key points: {', '.join(section.key_points)}",
        f"Target: ~{section.target_word_count} words\n",
    ]
    if chunks:
        parts.append("### Research Context")
        for i, c in enumerate(chunks, 1):
            parts.append(f'[{i}] Source: "{c.source_title}" ({c.source_url})\n{c.text}\n')
    if prior_drafts:
        parts.append("### Prior Sections")
        for d in prior_drafts:
            first = d.body_markdown.split(".")[0] + "."
            parts.append(f"- {d.title}: {first}")
    return "\n".join(parts)


def extract_citations(
    text: str,
    chunks: list[ChunkResult],
) -> list[CitationRef]:
    """Parse [N] references from text and map to source chunks."""
    refs: list[CitationRef] = []
    seen: set[int] = set()
    for match in _CITATION_PATTERN.finditer(text):
        num = int(match.group(1))
        if num in seen or num < 1 or num > len(chunks):
            if num > len(chunks):
                logger.warning("citation_reference_invalid", ref_number=num)
            continue
        seen.add(num)
        chunk = chunks[num - 1]
        refs.append(CitationRef(index=num, source_url=chunk.source_url, source_title=chunk.source_title))
    return refs


def _log_word_count(section: OutlineSection, wc: int, citation_count: int) -> None:
    if wc < 200 or wc > 500:
        logger.warning("section_word_count_outside_range", section_index=section.index, word_count=wc, target=section.target_word_count)
    logger.info("section_draft_complete", section_index=section.index, word_count=wc, citations_count=citation_count)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_section_drafter.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/content/section_drafter.py tests/unit/agents/content/test_section_drafter.py
git commit -m "feat(content-002): add section drafter with RAG retrieval and citation extraction"
```

---

## Task 4: Article Validation Logic

**Files:**
- Create: `tests/unit/agents/content/test_validate_article.py`

Validation logic will be added to the pipeline in Task 5. Here we test it as a pure function first.

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_validate_article.py`:

```python
"""Tests for article validation — word count checks and citation dedup."""

from unittest.mock import AsyncMock

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.section_drafter import DraftingContext
from src.agents.content.validate import validate_drafts
from src.models.content_pipeline import CitationRef, SectionDraft


def _make_draft(index: int, word_count: int, url: str = "https://a.com") -> SectionDraft:
    words = " ".join(["word"] * word_count)
    return SectionDraft(
        section_index=index,
        title=f"Section {index}",
        body_markdown=words,
        word_count=word_count,
        citations_used=[CitationRef(index=1, source_url=url, source_title="A")],
    )


class TestValidateDrafts:
    def test_passes_when_above_target(self) -> None:
        drafts = [_make_draft(0, 800), _make_draft(1, 800)]
        result = validate_drafts(drafts)
        assert result.total_word_count == 1600
        assert result.needs_expansion is False

    def test_flags_below_target(self) -> None:
        drafts = [_make_draft(0, 400), _make_draft(1, 300)]
        result = validate_drafts(drafts)
        assert result.total_word_count == 700
        assert result.needs_expansion is True
        assert result.shortest_index == 1

    def test_deduplicates_citations(self) -> None:
        drafts = [
            _make_draft(0, 800, url="https://a.com"),
            _make_draft(1, 800, url="https://a.com"),
        ]
        result = validate_drafts(drafts)
        assert len(result.all_citations) == 1


class TestReplaceSection:
    def test_replaces_by_index(self) -> None:
        drafts = [_make_draft(0, 400), _make_draft(1, 300)]
        new = _make_draft(1, 600)
        result = replace_section(drafts, new)
        assert result[1].word_count == 600
        assert result[0].word_count == 400
```

Update the import in the test file to include `replace_section`:

```python
from src.agents.content.validate import replace_section, validate_drafts
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/agents/content/test_validate_article.py -v`

Expected: FAIL — `validate` module does not exist.

- [ ] **Step 3: Implement validate.py**

Create `src/agents/content/validate.py`:

```python
"""Article validation — word count checks, citation aggregation, re-drafting.

Pure validation functions (no I/O) plus a re-draft helper that requires
the DraftingContext. Called by the validate_article graph node.
"""

from dataclasses import dataclass

import structlog

from src.models.content_pipeline import CitationRef, SectionDraft

logger = structlog.get_logger()

_MIN_TOTAL_WORDS = 1500


@dataclass(frozen=True)
class ValidationResult:
    """Result of article draft validation."""

    total_word_count: int
    all_citations: list[CitationRef]
    needs_expansion: bool
    shortest_index: int | None


def validate_drafts(drafts: list[SectionDraft]) -> ValidationResult:
    """Validate section drafts and aggregate citations."""
    total = sum(d.word_count for d in drafts)
    citations = _deduplicate_citations(drafts)
    shortest = _find_shortest(drafts)
    needs_expansion = total < _MIN_TOTAL_WORDS
    _log_results(drafts, total, citations, needs_expansion, shortest)
    return ValidationResult(
        total_word_count=total,
        all_citations=citations,
        needs_expansion=needs_expansion,
        shortest_index=shortest,
    )


def replace_section(
    drafts: list[SectionDraft],
    new_draft: SectionDraft,
) -> list[SectionDraft]:
    """Replace a section draft by index, return updated list."""
    return [new_draft if d.section_index == new_draft.section_index else d for d in drafts]


def _deduplicate_citations(drafts: list[SectionDraft]) -> list[CitationRef]:
    seen: dict[str, CitationRef] = {}
    for d in drafts:
        for c in d.citations_used:
            if c.source_url not in seen:
                seen[c.source_url] = c
    return list(seen.values())


def _find_shortest(drafts: list[SectionDraft]) -> int | None:
    if not drafts:
        return None
    return min(drafts, key=lambda d: d.word_count).section_index


def _log_results(
    drafts: list[SectionDraft],
    total: int,
    citations: list[CitationRef],
    needs_expansion: bool,
    shortest: int | None,
) -> None:
    for d in drafts:
        if d.word_count < 200 or d.word_count > 500:
            logger.warning("section_word_count_outside_range", section_index=d.section_index, word_count=d.word_count)
    if needs_expansion:
        logger.warning("article_below_word_target", total_words=total, target=_MIN_TOTAL_WORDS, shortest_section=shortest)
    logger.info("article_draft_validated", total_words=total, section_count=len(drafts), unique_citations=len(citations))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_validate_article.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/content/validate.py tests/unit/agents/content/test_validate_article.py
git commit -m "feat(content-002): add article validation with word count checks and citation dedup"
```

---

## Task 5: Extend LangGraph Pipeline — add 3 nodes + conditional edge

**Files:**
- Modify: `src/agents/content/pipeline.py`
- Modify: `tests/unit/agents/content/test_pipeline.py`

- [ ] **Step 1: Write failing tests for extended pipeline**

Add to `tests/unit/agents/content/test_pipeline.py`:

```python
import json
from unittest.mock import AsyncMock

from src.agents.content.pipeline import build_content_graph
from src.models.content_pipeline import SectionDraft


def _queries_json(section_count: int = 2) -> str:
    return json.dumps([
        {"section_index": i, "queries": [f"q{i}"]}
        for i in range(section_count)
    ])


def _mock_retriever() -> AsyncMock:
    from src.models.research import ChunkResult

    chunk = ChunkResult(
        text="Research finding about the topic.",
        source_url="https://src.com",
        source_title="Source",
        score=0.9,
        chunk_index=0,
    )
    retriever = AsyncMock()
    retriever.retrieve = AsyncMock(return_value=[chunk])
    return retriever


class TestContentPipelineWithDrafting:
    async def test_full_graph_with_retriever(self) -> None:
        responses = [
            _outline_json(),  # outline
            _queries_json(2),  # queries
            "Draft section 0 text with [1] citation.",  # draft section 0
            "Draft section 1 text with [1] citation about more.",  # draft section 1
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
        assert result["status"] == "draft_complete"
        assert len(result["section_drafts"]) == 2
        assert result["total_word_count"] > 0

    async def test_graph_without_retriever_stops_at_outline(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json()])
        graph = build_content_graph(llm)  # no retriever
        result = await graph.ainvoke({
            "topic": _make_topic(),
            "research_plan": _make_plan(),
            "findings": _make_findings(),
            "session_id": uuid4(),
            "outline": None,
            "status": "outline_generating",
            "error": None,
        })
        assert result["status"] == "outline_complete"
        assert "section_drafts" not in result or result.get("section_drafts") is None

    async def test_query_generation_failure_sets_failed(self) -> None:
        responses = [_outline_json(), "bad json", "bad json"]  # outline ok, queries fail
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

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/agents/content/test_pipeline.py::TestContentPipelineWithDrafting -v`

Expected: FAIL — `build_content_graph` does not accept `retriever` param.

- [ ] **Step 3: Extend pipeline.py with new nodes and conditional edge**

Update `src/agents/content/pipeline.py`. Add imports at top:

```python
from typing import NotRequired, TypedDict

from src.agents.content.query_generator import generate_section_queries
from src.agents.content.section_drafter import DraftingContext, draft_section
from src.agents.content.validate import validate_drafts
from src.models.content_pipeline import ArticleOutline, SectionDraft, SectionQueries
from src.services.milvus_retriever import MilvusRetriever
```

Extend `ContentState` with `NotRequired` fields:

```python
class ContentState(TypedDict):
    topic: TopicInput
    research_plan: ResearchPlan | None
    findings: list[FacetFindings]
    session_id: UUID
    outline: ArticleOutline | None
    status: str
    error: str | None
    section_queries: NotRequired[list[SectionQueries]]
    section_drafts: NotRequired[list[SectionDraft]]
    total_word_count: NotRequired[int]
```

Update `build_content_graph` to accept retriever and add nodes conditionally:

```python
def build_content_graph(
    llm: BaseChatModel,
    retriever: MilvusRetriever | None = None,
) -> CompiledStateGraph:
    graph = StateGraph(ContentState)
    graph.add_node("generate_outline", _make_outline_node(llm))
    graph.set_entry_point("generate_outline")

    if retriever is None:
        graph.add_edge("generate_outline", END)
    else:
        graph.add_node("generate_queries", _make_queries_node(llm))
        graph.add_node("draft_sections", _make_draft_node(llm, retriever))
        graph.add_node("validate_article", _make_validate_node(llm, retriever))
        graph.add_conditional_edges("generate_outline", _should_draft)
        graph.add_edge("generate_queries", "draft_sections")
        graph.add_edge("draft_sections", "validate_article")
        graph.add_edge("validate_article", END)

    return graph.compile()
```

Extract `outline_node` to a factory (`_make_outline_node`), add factory functions for each new node. Each node function stays under 20 lines by delegating to the modules from Tasks 2-4.

The `_should_draft` function:

```python
def _should_draft(state: ContentState) -> str:
    if state.get("outline") is not None and state.get("status") != "failed":
        return "generate_queries"
    return END
```

The `_make_queries_node`, `_make_draft_node`, and `_make_validate_node` closures each delegate to their respective module functions.

The `_make_validate_node` factory must implement the re-draft behavior from the spec:
1. Call `validate_drafts(section_drafts)` to get `ValidationResult`
2. If `needs_expansion` is True and `shortest_index` is not None:
   - Log `section_redraft_triggered` with `section_index` and `previous_words`
   - Find the corresponding `OutlineSection` and `SectionQueries` from state
   - Call `draft_section()` with an expanded target word count (original + 200)
   - Call `replace_section()` to swap the re-drafted section
   - Re-validate to get updated totals (no further retry)
3. Return updated `section_drafts`, `total_word_count`, deduplicated `citations`, and status `"draft_complete"`

This keeps the re-draft to one retry only, as per spec.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agents/content/test_pipeline.py -v`

Expected: ALL PASS (both old and new tests).

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest --tb=short -q`

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/agents/content/pipeline.py tests/unit/agents/content/test_pipeline.py
git commit -m "feat(content-002): extend content pipeline with query, draft, and validate nodes"
```

---

## Task 6: ContentService — draft_article() and repository update

**Files:**
- Modify: `src/services/content.py`
- Modify: `tests/unit/services/test_content_service.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/services/test_content_service.py`:

```python
from unittest.mock import AsyncMock
from src.models.content_pipeline import DraftStatus


class TestDraftArticle:
    async def test_drafts_article_from_outline(self) -> None:
        svc, session = await _make_service_with_retriever()
        outline_draft = await svc.generate_outline(session.id)
        assert outline_draft.status == DraftStatus.OUTLINE_COMPLETE
        result = await svc.draft_article(outline_draft.id)
        assert result.status == DraftStatus.DRAFT_COMPLETE
        assert len(result.section_drafts) > 0
        assert result.total_word_count > 0

    async def test_rejects_unknown_draft(self) -> None:
        svc, _ = await _make_service_with_retriever()
        with pytest.raises(NotFoundError):
            await svc.draft_article(uuid4())

    async def test_rejects_draft_not_outline_complete(self) -> None:
        svc, session = await _make_service_with_retriever()
        # Create a draft that's still generating
        from src.models.content_pipeline import ArticleDraft
        draft = ArticleDraft(
            session_id=session.id,
            topic_id=session.topic_id,
            status=DraftStatus.OUTLINE_GENERATING,
            created_at=datetime.now(UTC),
        )
        await svc._repos.drafts.create(draft)
        with pytest.raises(ValueError, match="not ready"):
            await svc.draft_article(draft.id)

    async def test_requires_retriever(self) -> None:
        svc, session = await _make_service()  # no retriever
        outline_draft = await svc.generate_outline(session.id)
        with pytest.raises(ValueError, match="retriever required"):
            await svc.draft_article(outline_draft.id)
```

Add a helper `_make_service_with_retriever` that constructs a `ContentService` with a mocked retriever:

```python
async def _make_service_with_retriever(
    session: ResearchSession | None = None,
) -> tuple[ContentService, ResearchSession]:
    session = session or _make_complete_session()
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)

    queries_json = json.dumps([
        {"section_index": 0, "queries": ["q0"]}
    ])
    llm = FakeListChatModel(responses=[
        _outline_json(),   # outline generation
        queries_json,      # query generation
        "Draft text with [1] citation about research.",  # section draft
    ])
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
    )
    retriever = AsyncMock()
    from src.models.research import ChunkResult
    retriever.retrieve = AsyncMock(return_value=[
        ChunkResult(text="Chunk", source_url="https://a.com", source_title="A", score=0.9, chunk_index=0),
    ])
    return ContentService(repos, llm, retriever=retriever), session
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/services/test_content_service.py::TestDraftArticle -v`

Expected: FAIL — `ContentService` does not accept `retriever`, no `draft_article` method.

- [ ] **Step 3: Implement draft_article() and extend ContentService**

Update `src/services/content.py`:

1. Add `retriever` parameter to `__init__`:
```python
def __init__(
    self,
    repos: ContentRepositories,
    llm: BaseChatModel,
    retriever: MilvusRetriever | None = None,
) -> None:
    self._repos = repos
    self._llm = llm
    self._retriever = retriever
```

2. Add `update` to `ArticleDraftRepository` protocol and `InMemoryArticleDraftRepository`:
```python
class ArticleDraftRepository(Protocol):
    async def create(self, draft: ArticleDraft) -> ArticleDraft: ...
    async def get(self, draft_id: UUID) -> ArticleDraft | None: ...
    async def update(self, draft: ArticleDraft) -> ArticleDraft: ...
```

```python
async def update(self, draft: ArticleDraft) -> ArticleDraft:
    self._store[draft.id] = draft
    return draft
```

3. Add `draft_article` method:
```python
async def draft_article(self, draft_id: UUID) -> ArticleDraft:
    draft = await self.get_draft(draft_id)
    self._validate_draft_ready(draft)
    session = await self._load_session(draft.session_id)
    findings = self._reconstruct_findings(session)
    topic = self._build_topic_input(session)
    result = await self._run_drafting_pipeline(topic, findings, draft)
    return await self._store_drafted(draft, result)
```

4. Add helper methods `_validate_draft_ready`, `_run_drafting_pipeline`, `_store_drafted` — each under 20 lines.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/services/test_content_service.py -v`

Expected: ALL PASS (old + new tests).

- [ ] **Step 5: Commit**

```bash
git add src/services/content.py tests/unit/services/test_content_service.py
git commit -m "feat(content-002): add draft_article() to ContentService with retriever support"
```

---

## Task 7: API Schema Extension

**Files:**
- Modify: `src/api/schemas/articles.py`

- [ ] **Step 1: Extend API schemas**

Add to `src/api/schemas/articles.py`:

```python
class CitationRefResponse(BaseModel):
    index: int
    source_url: str
    source_title: str


class SectionDraftResponse(BaseModel):
    section_index: int
    title: str
    body_markdown: str
    word_count: int
    citations_used: list[CitationRefResponse]
```

Extend `ArticleDraftResponse`:
```python
class ArticleDraftResponse(BaseModel):
    draft_id: UUID
    session_id: UUID
    status: str
    outline: ArticleOutlineResponse | None
    created_at: datetime
    completed_at: datetime | None
    section_drafts: list[SectionDraftResponse] = []
    citations: list[CitationRefResponse] = []
    total_word_count: int = 0
```

- [ ] **Step 2: Run existing tests to check no regressions**

Run: `uv run pytest tests/unit/api/test_article_endpoints.py -v`

Expected: ALL PASS (new fields have defaults, backward compatible).

- [ ] **Step 3: Commit**

```bash
git add src/api/schemas/articles.py
git commit -m "feat(content-002): extend article API schemas with section draft and citation responses"
```

---

## Task 8: API Endpoint — POST /articles/drafts/{draft_id}/sections

**Files:**
- Modify: `src/api/routers/articles.py`
- Modify: `tests/unit/api/test_article_endpoints.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/api/test_article_endpoints.py`:

```python
class TestDraftSections:
    async def test_returns_201(
        self,
        drafting_client: httpx.AsyncClient,
        auth_settings: Settings,
        draft_id_with_outline: str,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await drafting_client.post(
            f"/api/v1/articles/drafts/{draft_id_with_outline}/sections",
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["section_drafts"]) > 0
        assert data["total_word_count"] > 0
        assert data["status"] == "draft_complete"

    async def test_viewer_cannot_draft(
        self,
        drafting_client: httpx.AsyncClient,
        auth_settings: Settings,
        draft_id_with_outline: str,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await drafting_client.post(
            f"/api/v1/articles/drafts/{draft_id_with_outline}/sections",
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_invalid_draft_returns_404(
        self,
        drafting_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await drafting_client.post(
            f"/api/v1/articles/drafts/{uuid4()}/sections",
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_draft_not_ready_returns_400(
        self,
        drafting_client: httpx.AsyncClient,
        auth_settings: Settings,
        draft_id_not_ready: str,
    ) -> None:
        """Draft in OUTLINE_GENERATING status should be rejected."""
        headers = make_auth_header("editor", auth_settings)
        resp = await drafting_client.post(
            f"/api/v1/articles/drafts/{draft_id_not_ready}/sections",
            headers=headers,
        )
        assert resp.status_code == 400
```

Add a `draft_id_not_ready` fixture that creates an `ArticleDraft` in `OUTLINE_GENERATING` status without an outline.

Add fixtures `drafting_client` and `draft_id_with_outline` that set up a `ContentService` with a mocked retriever and pre-generate an outline draft.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/test_article_endpoints.py::TestDraftSections -v`

Expected: FAIL — endpoint does not exist.

- [ ] **Step 3: Add the endpoint**

Add to `src/api/routers/articles.py`:

```python
@limiter.limit("3/minute")
@articles_router.post(
    "/articles/drafts/{draft_id}/sections",
    response_model=ArticleDraftResponse,
    status_code=HTTP_201_CREATED,
)
async def draft_sections(
    request: Request,
    draft_id: str,
    user: TokenPayload = Depends(require_editor_or_above),
) -> ArticleDraftResponse:
    svc = _get_content_service(request)
    draft = await svc.draft_article(UUID(draft_id))
    return _to_draft_response(draft)
```

Add a `_to_draft_response` helper that converts `ArticleDraft` → `ArticleDraftResponse` including the new section_drafts and citations fields.

Update the existing `get_draft` endpoint to also use `_to_draft_response` (with section_drafts populated if available).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/test_article_endpoints.py -v`

Expected: ALL PASS.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest --tb=short -q`

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/articles.py tests/unit/api/test_article_endpoints.py
git commit -m "feat(content-002): add POST /articles/drafts/{id}/sections endpoint"
```

---

## Task 9: Final Integration Test & Cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite with coverage**

Run: `uv run pytest --cov=src --cov-report=term-missing --tb=short`

Expected: All tests pass, coverage >= 80% on new code.

- [ ] **Step 2: Run linting**

Run: `uv run ruff check src/ && uv run ruff format --check src/`

Fix any issues.

- [ ] **Step 3: Run type checking**

Run: `uv run mypy src/`

Fix any type errors in new code.

- [ ] **Step 4: Format code**

Run: `uv run ruff format src/ tests/`

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -u
git commit -m "chore(content-002): format, fix lint, update types"
```

- [ ] **Step 6: Update PROGRESS.md**

Update `project-management/PROGRESS.md`:
- Set CONTENT-002 status to **In Progress** (or Done if merging)
- Add branch name
- Link plan and spec files

```bash
git add project-management/PROGRESS.md
git commit -m "docs: update PROGRESS.md — CONTENT-002 in progress"
```
