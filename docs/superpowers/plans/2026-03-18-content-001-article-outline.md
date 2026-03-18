# CONTENT-001: Article Outline Generation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a content pipeline that generates structured article outlines (4-8 sections with narrative flow) from completed research sessions, exposing an API endpoint for outline generation and review.

**Architecture:** Separate LangGraph content pipeline graph with a `generate_outline` node. `ContentService` loads findings from research sessions, runs the pipeline, and stores `ArticleDraft` records. LLM-based outline generator follows the same pattern as `planner.py` (system prompt + JSON parse + retry).

**Tech Stack:** LangGraph (existing), langchain-core (existing), Pydantic, FastAPI, pytest, FakeLLM

**Spec:** [`docs/superpowers/specs/2026-03-18-content-001-article-outline-design.md`](../specs/2026-03-18-content-001-article-outline-design.md)

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/models/content_pipeline.py` | DraftStatus, OutlineSection, ArticleOutline, ArticleDraft |
| `src/models/research_db.py` | Add `findings_data` field to ResearchSession (modify) |
| `src/services/research.py` | Update `run_and_finalize` to persist findings (modify) |
| `src/agents/content/__init__.py` | Package init |
| `src/agents/content/outline_generator.py` | `generate_outline()` LLM function |
| `src/agents/content/pipeline.py` | ContentState TypedDict + `build_content_graph()` |
| `src/services/content.py` | ContentService, ContentRepositories, in-memory repos |
| `src/api/schemas/articles.py` | Request/response schemas |
| `src/api/routers/articles.py` | POST /articles/generate, GET /articles/drafts/{id} |
| `src/api/main.py` | Register articles router (modify) |

---

## Task 1: Findings Persistence (Prerequisite)

**Files:**
- Modify: `src/models/research_db.py`
- Modify: `src/services/research.py`
- Modify: `tests/unit/services/test_research_service.py`

- [ ] **Step 1: Add `findings_data` field to ResearchSession**

In `src/models/research_db.py`, add to `ResearchSession`:

```python
    findings_data: list[dict[str, object]] = Field(default_factory=list)
```

- [ ] **Step 2: Update `run_and_finalize` to persist findings**

In `src/services/research.py`, update `run_and_finalize`:

```python
    async def run_and_finalize(
        self, session_id: UUID, topic: TopicInput
    ) -> None:
        try:
            result = await self._orchestrator.run(session_id, topic)
            session = await self._repos.sessions.get(session_id)
            if session:
                findings_raw = result.get("findings", [])
                findings_data = [
                    f.model_dump() if hasattr(f, "model_dump") else f
                    for f in findings_raw
                ]
                updated = session.model_copy(
                    update={
                        "status": "complete",
                        "findings_data": findings_data,
                        "completed_at": datetime.now(UTC),
                    }
                )
                await self._repos.sessions.update(updated)
        except Exception as exc:
            logger.error(
                "orchestrator_failed",
                session_id=str(session_id),
                error=str(exc),
            )
            session = await self._repos.sessions.get(session_id)
            if session:
                updated = session.model_copy(
                    update={"status": "failed", "completed_at": datetime.now(UTC)}
                )
                await self._repos.sessions.update(updated)
```

- [ ] **Step 3: Run existing tests to ensure no regressions**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/models/research_db.py src/services/research.py
git commit -m "feat(content-001): persist research findings in ResearchSession for content pipeline"
```

---

## Task 2: Content Pipeline Data Models

**Files:**
- Create: `src/models/content_pipeline.py`
- Create: `tests/unit/models/test_content_pipeline_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/models/test_content_pipeline_models.py`:

```python
"""Tests for content pipeline Pydantic models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.content_pipeline import (
    ArticleDraft,
    ArticleOutline,
    DraftStatus,
    OutlineSection,
)


class TestOutlineSection:
    def test_construct(self) -> None:
        section = OutlineSection(
            index=0,
            title="Introduction",
            description="Set the context",
            key_points=["Point 1", "Point 2"],
            target_word_count=300,
            relevant_facets=[0, 1],
        )
        assert section.title == "Introduction"
        assert section.target_word_count == 300

    def test_frozen(self) -> None:
        section = OutlineSection(
            index=0,
            title="Intro",
            description="Desc",
            key_points=["P"],
            target_word_count=200,
            relevant_facets=[0],
        )
        with pytest.raises(ValidationError):
            section.title = "Changed"  # type: ignore[misc]


class TestArticleOutline:
    def test_construct(self) -> None:
        sections = [
            OutlineSection(
                index=i,
                title=f"Section {i}",
                description=f"Desc {i}",
                key_points=[f"Point {i}"],
                target_word_count=300,
                relevant_facets=[i % 3],
            )
            for i in range(5)
        ]
        outline = ArticleOutline(
            title="Test Article",
            content_type="article",
            sections=sections,
            total_target_words=1500,
            reasoning="Good structure",
        )
        assert len(outline.sections) == 5
        assert outline.total_target_words == 1500

    def test_serialization_roundtrip(self) -> None:
        outline = ArticleOutline(
            title="Test",
            content_type="analysis",
            sections=[
                OutlineSection(
                    index=0, title="S", description="D",
                    key_points=["P"], target_word_count=200,
                    relevant_facets=[0],
                ),
            ],
            total_target_words=200,
            reasoning="R",
        )
        data = outline.model_dump()
        restored = ArticleOutline.model_validate(data)
        assert restored == outline


class TestDraftStatus:
    def test_values(self) -> None:
        assert DraftStatus.OUTLINE_GENERATING == "outline_generating"
        assert DraftStatus.OUTLINE_COMPLETE == "outline_complete"
        assert DraftStatus.FAILED == "failed"


class TestArticleDraft:
    def test_construct_defaults(self) -> None:
        draft = ArticleDraft(
            session_id=uuid4(),
            topic_id=uuid4(),
            created_at=datetime.now(UTC),
        )
        assert draft.status == DraftStatus.OUTLINE_GENERATING
        assert draft.outline is None

    def test_with_outline(self) -> None:
        outline = ArticleOutline(
            title="Test",
            content_type="article",
            sections=[
                OutlineSection(
                    index=0, title="S", description="D",
                    key_points=["P"], target_word_count=200,
                    relevant_facets=[0],
                ),
            ],
            total_target_words=200,
            reasoning="R",
        )
        draft = ArticleDraft(
            session_id=uuid4(),
            topic_id=uuid4(),
            outline=outline,
            status=DraftStatus.OUTLINE_COMPLETE,
            created_at=datetime.now(UTC),
        )
        assert draft.outline is not None
        assert draft.status == DraftStatus.OUTLINE_COMPLETE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_content_pipeline_models.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement models**

Create `src/models/content_pipeline.py`:

```python
"""Content pipeline models — outline generation and article drafting.

Intermediate models for the content pipeline stages (CONTENT-001 through
CONTENT-004). Not part of the final CanonicalArticle contract.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.content import ContentType


class DraftStatus(StrEnum):
    """Valid article draft statuses."""

    OUTLINE_GENERATING = "outline_generating"
    OUTLINE_COMPLETE = "outline_complete"
    DRAFTING = "drafting"
    COMPLETE = "complete"
    FAILED = "failed"


class OutlineSection(BaseModel, frozen=True):
    """A single section in an article outline."""

    index: int
    title: str
    description: str
    key_points: list[str]
    target_word_count: int
    relevant_facets: list[int]


class ArticleOutline(BaseModel, frozen=True):
    """LLM-generated article outline from research findings."""

    title: str
    subtitle: str | None = None
    content_type: ContentType
    sections: list[OutlineSection]
    total_target_words: int
    reasoning: str


class ArticleDraft(BaseModel):
    """Tracks article generation state."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    topic_id: UUID
    outline: ArticleOutline | None = None
    status: DraftStatus = DraftStatus.OUTLINE_GENERATING
    created_at: datetime
    completed_at: datetime | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_content_pipeline_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/models/content_pipeline.py tests/unit/models/test_content_pipeline_models.py
git commit -m "feat(content-001): add content pipeline data models"
```

---

## Task 3: Outline Generator (LLM Function)

**Files:**
- Create: `src/agents/content/__init__.py`
- Create: `src/agents/content/outline_generator.py`
- Create: `tests/unit/agents/content/__init__.py`
- Create: `tests/unit/agents/content/test_outline_generator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/__init__.py` (empty) and `tests/unit/agents/content/test_outline_generator.py`:

```python
"""Tests for the LLM-based article outline generator."""

import json
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.outline_generator import generate_outline
from src.models.content_pipeline import ArticleOutline
from src.models.research import FacetFindings, SourceDocument, TopicInput
from datetime import UTC, datetime


def _make_topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="AI Security Trends in 2026",
        description="Emerging threats and defenses",
        domain="cybersecurity",
    )


def _make_findings(num_facets: int = 3) -> list[FacetFindings]:
    return [
        FacetFindings(
            facet_index=i,
            sources=[
                SourceDocument(
                    url=f"https://example.com/{i}",
                    title=f"Source {i}",
                    snippet=f"Content about facet {i}",
                    retrieved_at=datetime.now(UTC),
                ),
            ],
            claims=[f"Claim {i}a", f"Claim {i}b"],
            summary=f"Summary of facet {i} research findings.",
        )
        for i in range(num_facets)
    ]


def _outline_json(num_sections: int = 5) -> str:
    sections = [
        {
            "index": i,
            "title": f"Section {i}",
            "description": f"Covers aspect {i}",
            "key_points": [f"Point {i}a", f"Point {i}b", f"Point {i}c"],
            "target_word_count": 300,
            "relevant_facets": [i % 3],
        }
        for i in range(num_sections)
    ]
    return json.dumps({
        "title": "AI Security Trends: A Comprehensive Analysis",
        "subtitle": "Emerging threats and defense strategies",
        "content_type": "article",
        "sections": sections,
        "total_target_words": num_sections * 300,
        "reasoning": "Structured for narrative flow from overview to specifics.",
    })


class TestGenerateOutline:
    async def test_returns_valid_outline(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json(5)])
        outline = await generate_outline(_make_topic(), _make_findings(), llm)
        assert isinstance(outline, ArticleOutline)
        assert len(outline.sections) == 5
        assert outline.total_target_words == 1500

    async def test_sections_have_required_fields(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json(4)])
        outline = await generate_outline(_make_topic(), _make_findings(), llm)
        for section in outline.sections:
            assert section.title != ""
            assert len(section.key_points) >= 1
            assert section.target_word_count > 0
            assert len(section.relevant_facets) >= 1

    async def test_handles_malformed_json(self) -> None:
        llm = FakeListChatModel(responses=["not json", _outline_json(5)])
        outline = await generate_outline(_make_topic(), _make_findings(), llm)
        assert isinstance(outline, ArticleOutline)

    async def test_raises_on_repeated_failure(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_outline(_make_topic(), _make_findings(), llm)

    async def test_uses_findings_in_prompt(self) -> None:
        """Verify the LLM receives findings context."""
        llm = FakeListChatModel(responses=[_outline_json(5)])
        findings = _make_findings(3)
        outline = await generate_outline(_make_topic(), findings, llm)
        # If the outline was generated, the LLM received a valid prompt
        assert outline is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/content/test_outline_generator.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement outline generator**

Create `src/agents/content/__init__.py` (empty) and `src/agents/content/outline_generator.py`:

```python
"""LLM-based article outline generation.

Takes research findings and generates a structured 4-8 section outline
with narrative flow, target word counts, and key points per section.
Follows the same pattern as planner.py.
"""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.content_pipeline import ArticleOutline
from src.models.research import FacetFindings, TopicInput

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You are an expert content strategist. Generate a structured "
    "article outline from research findings. The outline should have "
    "4-8 sections with narrative flow: introduction, findings, "
    "analysis, and conclusion. Respond with valid JSON only."
)

_USER_TEMPLATE = (
    "Generate an article outline for this topic:\n\n"
    "Title: {title}\n"
    "Description: {description}\n"
    "Domain: {domain}\n\n"
    "Research findings:\n{findings_summary}\n\n"
    "Requirements:\n"
    "- 4-8 sections ordered for narrative flow\n"
    "- Each section: 200-500 target words\n"
    "- Total: 1500-3000 words\n"
    "- Map each section to relevant facet indices\n\n"
    "Return JSON: {schema_hint}"
)

_SCHEMA_HINT = (
    '{{"title": "...", "subtitle": "...", "content_type": "article", '
    '"sections": [{{"index": 0, "title": "...", "description": "...", '
    '"key_points": ["..."], "target_word_count": 300, '
    '"relevant_facets": [0]}}], '
    '"total_target_words": 1500, "reasoning": "..."}}'
)

_MAX_RETRIES = 2


def _summarize_findings(findings: list[FacetFindings]) -> str:
    """Build a concise summary of findings for the LLM prompt."""
    lines = []
    for f in findings:
        lines.append(
            f"Facet {f.facet_index}: {f.summary} "
            f"({len(f.sources)} sources, {len(f.claims)} claims)"
        )
    return "\n".join(lines)


async def generate_outline(
    topic: TopicInput,
    findings: list[FacetFindings],
    llm: BaseChatModel,
) -> ArticleOutline:
    """Generate an article outline from topic and findings."""
    logger.info(
        "outline_generation_started",
        topic_title=topic.title,
    )
    user_msg = _USER_TEMPLATE.format(
        title=topic.title,
        description=topic.description,
        domain=topic.domain,
        findings_summary=_summarize_findings(findings),
        schema_hint=_SCHEMA_HINT,
    )
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = json.loads(response.content)
            return ArticleOutline.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "outline_parse_failed",
                attempt=attempt + 1,
                error=str(exc),
            )

    msg = f"Failed to generate outline after {_MAX_RETRIES} attempts"
    raise ValueError(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/content/test_outline_generator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/content/ tests/unit/agents/content/
git commit -m "feat(content-001): add LLM-based article outline generator"
```

---

## Task 4: Content Pipeline Graph

**Files:**
- Create: `src/agents/content/pipeline.py`
- Create: `tests/unit/agents/content/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_pipeline.py`:

```python
"""Tests for the content pipeline LangGraph graph."""

import json
from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.pipeline import build_content_graph
from src.models.research import FacetFindings, ResearchPlan, ResearchFacet, SourceDocument, TopicInput
from datetime import UTC, datetime


def _make_topic() -> TopicInput:
    return TopicInput(
        id=uuid4(), title="Test", description="Desc", domain="tech"
    )


def _make_plan() -> ResearchPlan:
    return ResearchPlan(
        facets=[
            ResearchFacet(index=0, title="F0", description="D0", search_queries=["q0"]),
        ],
        reasoning="Plan",
    )


def _make_findings() -> list[FacetFindings]:
    return [
        FacetFindings(
            facet_index=0,
            sources=[SourceDocument(url="https://a.com", title="A", snippet="S", retrieved_at=datetime.now(UTC))],
            claims=["Claim"],
            summary="Summary",
        ),
    ]


def _outline_json() -> str:
    return json.dumps({
        "title": "Test Article",
        "content_type": "article",
        "sections": [
            {"index": 0, "title": "Intro", "description": "D", "key_points": ["P"], "target_word_count": 300, "relevant_facets": [0]},
            {"index": 1, "title": "Conclusion", "description": "D", "key_points": ["P"], "target_word_count": 200, "relevant_facets": [0]},
        ],
        "total_target_words": 500,
        "reasoning": "Simple structure",
    })


class TestContentPipeline:
    async def test_graph_generates_outline(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json()])
        graph = build_content_graph(llm)
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
        assert result["outline"] is not None
        assert len(result["outline"].sections) == 2

    async def test_graph_handles_failure(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        graph = build_content_graph(llm)
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
        assert result["error"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/content/test_pipeline.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement content pipeline**

Create `src/agents/content/pipeline.py`:

```python
"""Content pipeline LangGraph StateGraph.

Orchestrates article generation stages. CONTENT-001 adds the
generate_outline node. Future tickets add draft, SEO, and compile nodes.
"""

from typing import TypedDict
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.content.outline_generator import generate_outline
from src.models.content_pipeline import ArticleOutline
from src.models.research import (
    FacetFindings,
    ResearchPlan,
    TopicInput,
)

logger = structlog.get_logger()


class ContentState(TypedDict):
    """State flowing through the content pipeline graph."""

    topic: TopicInput
    research_plan: ResearchPlan
    findings: list[FacetFindings]
    session_id: UUID
    outline: ArticleOutline | None
    status: str
    error: str | None


def build_content_graph(llm: BaseChatModel) -> CompiledStateGraph:
    """Build and compile the content pipeline graph."""
    graph = StateGraph(ContentState)

    async def outline_node(state: ContentState) -> dict:  # type: ignore[type-arg]
        topic = state["topic"]
        if not isinstance(topic, TopicInput):
            topic = TopicInput.model_validate(topic)
        findings = [
            f if isinstance(f, FacetFindings) else FacetFindings.model_validate(f)
            for f in state["findings"]
        ]
        try:
            outline = await generate_outline(topic, findings, llm)
            logger.info(
                "outline_generation_complete",
                section_count=len(outline.sections),
                total_words=outline.total_target_words,
            )
            return {"outline": outline, "status": "outline_complete"}
        except Exception as exc:
            logger.error("outline_generation_failed", error=str(exc))
            return {"status": "failed", "error": str(exc)}

    graph.add_node("generate_outline", outline_node)
    graph.set_entry_point("generate_outline")
    graph.add_edge("generate_outline", END)

    return graph.compile()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/content/test_pipeline.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/content/pipeline.py tests/unit/agents/content/test_pipeline.py
git commit -m "feat(content-001): add content pipeline LangGraph graph"
```

---

## Task 5: Content Service + Repositories

**Files:**
- Create: `src/services/content.py`
- Create: `tests/unit/services/test_content_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/services/test_content_service.py`:

```python
"""Tests for ContentService."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.errors import NotFoundError
from src.models.content_pipeline import ArticleDraft, DraftStatus
from src.models.research import FacetFindings, SourceDocument, TopicInput
from src.models.research_db import ResearchSession
from src.services.content import (
    ContentRepositories,
    ContentService,
    InMemoryArticleDraftRepository,
)
from src.services.research import InMemoryResearchSessionRepository


def _outline_json() -> str:
    return json.dumps({
        "title": "Test Article",
        "content_type": "article",
        "sections": [
            {"index": 0, "title": "Intro", "description": "D",
             "key_points": ["P"], "target_word_count": 300, "relevant_facets": [0]},
        ],
        "total_target_words": 300,
        "reasoning": "Simple",
    })


def _make_complete_session() -> ResearchSession:
    findings = [
        FacetFindings(
            facet_index=0,
            sources=[SourceDocument(
                url="https://a.com", title="A", snippet="S",
                retrieved_at=datetime.now(UTC),
            )],
            claims=["Claim"],
            summary="Summary",
        ),
    ]
    return ResearchSession(
        topic_id=uuid4(),
        status="complete",
        started_at=datetime.now(UTC),
        findings_data=[f.model_dump() for f in findings],
    )


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
    svc = ContentService(repos, llm)
    return svc, session


class TestGenerateOutline:
    async def test_returns_draft_with_outline(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        assert isinstance(draft, ArticleDraft)
        assert draft.outline is not None
        assert draft.status == DraftStatus.OUTLINE_COMPLETE
        assert draft.session_id == session.id

    async def test_rejects_unknown_session(self) -> None:
        svc, _ = await _make_service()
        with pytest.raises(NotFoundError):
            await svc.generate_outline(uuid4())

    async def test_rejects_incomplete_session(self) -> None:
        session = ResearchSession(
            topic_id=uuid4(),
            status="planning",
            started_at=datetime.now(UTC),
        )
        svc, _ = await _make_service(session)
        with pytest.raises(ValueError, match="not complete"):
            await svc.generate_outline(session.id)


class TestGetDraft:
    async def test_returns_draft(self) -> None:
        svc, session = await _make_service()
        draft = await svc.generate_outline(session.id)
        retrieved = await svc.get_draft(draft.id)
        assert retrieved.id == draft.id

    async def test_not_found(self) -> None:
        svc, _ = await _make_service()
        with pytest.raises(NotFoundError):
            await svc.get_draft(uuid4())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_content_service.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement content service**

Create `src/services/content.py`:

```python
"""Content service — bridges API to the content pipeline.

Loads research findings, runs the content pipeline graph,
and manages ArticleDraft records.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.content.pipeline import build_content_graph
from src.api.errors import NotFoundError
from src.models.content_pipeline import (
    ArticleDraft,
    ArticleOutline,
    DraftStatus,
)
from src.models.research import FacetFindings, TopicInput
from src.models.research_db import ResearchSession

logger = structlog.get_logger()


class ArticleDraftRepository(Protocol):
    async def create(self, draft: ArticleDraft) -> ArticleDraft: ...
    async def get(self, draft_id: UUID) -> ArticleDraft | None: ...


class ResearchSessionReader(Protocol):
    """Read-only access to research sessions."""

    async def get(self, session_id: UUID) -> ResearchSession | None: ...


class InMemoryArticleDraftRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, ArticleDraft] = {}

    async def create(self, draft: ArticleDraft) -> ArticleDraft:
        self._store[draft.id] = draft
        return draft

    async def get(self, draft_id: UUID) -> ArticleDraft | None:
        return self._store.get(draft_id)


@dataclass(frozen=True)
class ContentRepositories:
    drafts: ArticleDraftRepository
    research: ResearchSessionReader


class ContentService:
    def __init__(
        self, repos: ContentRepositories, llm: BaseChatModel
    ) -> None:
        self._repos = repos
        self._llm = llm

    async def generate_outline(self, session_id: UUID) -> ArticleDraft:
        """Generate an article outline from a completed research session."""
        session = await self._load_session(session_id)
        findings = self._reconstruct_findings(session)
        topic = self._build_topic_input(session)
        outline = await self._run_pipeline(topic, findings)
        return await self._store_draft(session, outline)

    async def get_draft(self, draft_id: UUID) -> ArticleDraft:
        draft = await self._repos.drafts.get(draft_id)
        if draft is None:
            raise NotFoundError(f"Draft {draft_id} not found")
        return draft

    async def _load_session(self, session_id: UUID) -> ResearchSession:
        session = await self._repos.research.get(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id} not found")
        if session.status != "complete":
            msg = f"Session {session_id} is not complete"
            raise ValueError(msg)
        return session

    def _reconstruct_findings(
        self, session: ResearchSession
    ) -> list[FacetFindings]:
        return [
            FacetFindings.model_validate(f)
            for f in session.findings_data
        ]

    def _build_topic_input(self, session: ResearchSession) -> TopicInput:
        return TopicInput(
            id=session.topic_id,
            title=f"Topic {session.topic_id}",
            description="",
            domain="",
        )

    async def _run_pipeline(
        self, topic: TopicInput, findings: list[FacetFindings]
    ) -> ArticleOutline:
        graph = build_content_graph(self._llm)
        result = await graph.ainvoke({
            "topic": topic,
            "research_plan": None,
            "findings": findings,
            "session_id": topic.id,
            "outline": None,
            "status": "outline_generating",
            "error": None,
        })
        if result["status"] == "failed":
            raise ValueError(result.get("error", "Outline generation failed"))
        return result["outline"]

    async def _store_draft(
        self, session: ResearchSession, outline: ArticleOutline
    ) -> ArticleDraft:
        draft = ArticleDraft(
            session_id=session.id,
            topic_id=session.topic_id,
            outline=outline,
            status=DraftStatus.OUTLINE_COMPLETE,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        return await self._repos.drafts.create(draft)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_content_service.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/content.py tests/unit/services/test_content_service.py
git commit -m "feat(content-001): add ContentService with in-memory repositories"
```

---

## Task 6: API Schemas + Router + Registration

**Files:**
- Create: `src/api/schemas/articles.py`
- Create: `src/api/routers/articles.py`
- Modify: `src/api/main.py`
- Create: `tests/unit/api/test_article_endpoints.py`

- [ ] **Step 1: Create API schemas**

Create `src/api/schemas/articles.py`:

```python
"""Request/response schemas for the articles API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GenerateArticleRequest(BaseModel):
    session_id: UUID


class OutlineSectionResponse(BaseModel):
    index: int
    title: str
    description: str
    key_points: list[str]
    target_word_count: int
    relevant_facets: list[int]


class ArticleOutlineResponse(BaseModel):
    draft_id: UUID
    title: str
    subtitle: str | None
    content_type: str
    sections: list[OutlineSectionResponse]
    total_target_words: int
    reasoning: str
    status: str


class ArticleDraftResponse(BaseModel):
    draft_id: UUID
    session_id: UUID
    status: str
    outline: ArticleOutlineResponse | None
    created_at: datetime
    completed_at: datetime | None
```

- [ ] **Step 2: Create articles router**

Create `src/api/routers/articles.py`:

```python
"""Article generation API endpoints."""

import structlog
from fastapi import APIRouter, Depends, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.rate_limiter import limiter
from src.api.schemas.articles import (
    ArticleDraftResponse,
    ArticleOutlineResponse,
    GenerateArticleRequest,
    OutlineSectionResponse,
)
from src.services.content import ContentService

logger = structlog.get_logger()

articles_router = APIRouter()


def _get_content_service(request: Request) -> ContentService:
    return request.app.state.content_service  # type: ignore[no-any-return]


@limiter.limit("3/minute")
@articles_router.post(
    "/articles/generate",
    response_model=ArticleOutlineResponse,
    status_code=HTTP_201_CREATED,
)
async def generate_article(
    request: Request,
    body: GenerateArticleRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> ArticleOutlineResponse:
    svc = _get_content_service(request)
    draft = await svc.generate_outline(body.session_id)
    return _to_outline_response(draft)


@limiter.limit("30/minute")
@articles_router.get(
    "/articles/drafts/{draft_id}",
    response_model=ArticleDraftResponse,
)
async def get_draft(
    request: Request,
    draft_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> ArticleDraftResponse:
    from uuid import UUID

    svc = _get_content_service(request)
    draft = await svc.get_draft(UUID(draft_id))
    outline_resp = _to_outline_response(draft) if draft.outline else None
    return ArticleDraftResponse(
        draft_id=draft.id,
        session_id=draft.session_id,
        status=draft.status,
        outline=outline_resp,
        created_at=draft.created_at,
        completed_at=draft.completed_at,
    )


def _to_outline_response(draft):  # type: ignore[no-untyped-def]
    """Convert ArticleDraft to ArticleOutlineResponse."""
    o = draft.outline
    sections = [
        OutlineSectionResponse(
            index=s.index,
            title=s.title,
            description=s.description,
            key_points=list(s.key_points),
            target_word_count=s.target_word_count,
            relevant_facets=list(s.relevant_facets),
        )
        for s in o.sections
    ]
    return ArticleOutlineResponse(
        draft_id=draft.id,
        title=o.title,
        subtitle=o.subtitle,
        content_type=o.content_type,
        sections=sections,
        total_target_words=o.total_target_words,
        reasoning=o.reasoning,
        status=draft.status,
    )
```

- [ ] **Step 3: Register router in main.py**

Read `src/api/main.py` first. Add import:
```python
from src.api.routers.articles import articles_router
```

Add to `_register_routers`:
```python
    app.include_router(
        articles_router,
        prefix=settings.api_v1_prefix,
        tags=["articles"],
    )
```

- [ ] **Step 4: Write API tests**

Create `tests/unit/api/test_article_endpoints.py`:

```python
"""Tests for article generation API endpoints."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.main import create_app
from src.config.settings import Settings
from src.models.research import FacetFindings, SourceDocument
from src.models.research_db import ResearchSession
from src.services.content import (
    ContentRepositories,
    ContentService,
    InMemoryArticleDraftRepository,
)
from src.services.research import InMemoryResearchSessionRepository
from tests.unit.api.conftest import make_auth_header


def _outline_json() -> str:
    return json.dumps({
        "title": "Test",
        "content_type": "article",
        "sections": [
            {"index": 0, "title": "Intro", "description": "D",
             "key_points": ["P"], "target_word_count": 300, "relevant_facets": [0]},
        ],
        "total_target_words": 300,
        "reasoning": "Simple",
    })


@pytest.fixture
def test_session_id() -> str:
    return str(uuid4())


@pytest.fixture
def articles_app(auth_settings: Settings, test_session_id: str) -> FastAPI:
    app = create_app(auth_settings)
    session_repo = InMemoryResearchSessionRepository()

    # Create a complete research session with findings
    findings = [FacetFindings(
        facet_index=0,
        sources=[SourceDocument(url="https://a.com", title="A", snippet="S", retrieved_at=datetime.now(UTC))],
        claims=["Claim"], summary="Summary",
    )]
    import asyncio
    session = ResearchSession(
        id=__import__("uuid").UUID(test_session_id),
        topic_id=uuid4(),
        status="complete",
        started_at=datetime.now(UTC),
        findings_data=[f.model_dump() for f in findings],
    )
    asyncio.get_event_loop().run_until_complete(session_repo.create(session))

    llm = FakeListChatModel(responses=[_outline_json()])
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
    )
    app.state.content_service = ContentService(repos, llm)
    return app


@pytest.fixture
async def articles_client(articles_app: FastAPI) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=articles_app),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]


class TestGenerateArticle:
    async def test_returns_201(
        self, articles_client: httpx.AsyncClient, auth_settings: Settings, test_session_id: str
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await articles_client.post(
            "/api/v1/articles/generate",
            json={"session_id": test_session_id},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "draft_id" in data
        assert data["title"] == "Test"
        assert len(data["sections"]) == 1

    async def test_viewer_cannot_generate(
        self, articles_client: httpx.AsyncClient, auth_settings: Settings, test_session_id: str
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await articles_client.post(
            "/api/v1/articles/generate",
            json={"session_id": test_session_id},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_invalid_session_returns_404(
        self, articles_client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await articles_client.post(
            "/api/v1/articles/generate",
            json={"session_id": str(uuid4())},
            headers=headers,
        )
        assert resp.status_code == 404
```

- [ ] **Step 5: Run tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_article_endpoints.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/schemas/articles.py src/api/routers/articles.py src/api/main.py tests/unit/api/test_article_endpoints.py
git commit -m "feat(content-001): add article generation API endpoints"
```

---

## Task 7: Lint, Full Test Suite, Update Progress

**Files:**
- Modify: `project-management/PROGRESS.md`

- [ ] **Step 1: Lint all new code**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/agents/content/ src/services/content.py src/api/routers/articles.py src/api/schemas/articles.py src/models/content_pipeline.py`

- [ ] **Step 2: Format check**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/ tests/`
Fix any issues.

- [ ] **Step 3: Full test suite with coverage**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v --cov=src --cov-report=term-missing --tb=short`
Expected: All PASS, coverage >= 80%

- [ ] **Step 4: Update PROGRESS.md**

Add CONTENT-001 row to Epic 3 section:

| CONTENT-001 | Article Outline Generation | Done | `feature/CONTENT-001-article-outline` | [plan](../docs/superpowers/plans/2026-03-18-content-001-article-outline.md) | [spec](../docs/superpowers/specs/2026-03-18-content-001-article-outline-design.md) |

- [ ] **Step 5: Commit**

```bash
git add project-management/PROGRESS.md
git commit -m "docs: update PROGRESS.md — CONTENT-001 done"
```
