# RESEARCH-001: Agent Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LangGraph-based research orchestrator that plans research facets, dispatches stub agents in parallel, evaluates completeness with retry, and exposes API endpoints for session management.

**Architecture:** Linear-with-conditional-loop LangGraph StateGraph. Nodes: plan_research → dispatch_agents → evaluate_completeness → (retry or finalize). Protocol-based task dispatch (asyncio). Hybrid state: LangGraph MemorySaver + in-memory SQLAlchemy-style repositories.

**Tech Stack:** LangGraph, langchain-core, langchain-anthropic, FastAPI, Pydantic, pytest, FakeLLM

**Spec:** [`docs/superpowers/specs/2026-03-17-research-001-agent-orchestrator-design.md`](../specs/2026-03-17-research-001-agent-orchestrator-design.md)

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/models/research.py` | Pydantic models: TopicInput, ResearchFacet, ResearchPlan, SourceDocument, FacetFindings, FacetTask, EvaluationResult |
| `src/models/research_db.py` | Pydantic stand-ins for ResearchSession, AgentStep (in-memory, no SQLAlchemy yet) |
| `src/agents/research/__init__.py` | Package init |
| `src/agents/research/state.py` | ResearchState TypedDict with Annotated reducer |
| `src/agents/research/planner.py` | LLM-based research plan generation |
| `src/agents/research/evaluator.py` | LLM-based completeness evaluation with guardrails |
| `src/agents/research/stub.py` | Stub research agent (placeholder for RESEARCH-002/003) |
| `src/agents/research/orchestrator.py` | LangGraph StateGraph wiring — build_graph() factory |
| `src/agents/research/runner.py` | ResearchOrchestrator protocol + LangGraphResearchOrchestrator |
| `src/services/task_dispatch.py` | TaskDispatcher protocol + AsyncIODispatcher |
| `src/services/research.py` | ResearchService, repository protocols, in-memory repos, ResearchRepositories |
| `src/api/schemas/research.py` | Request/response Pydantic schemas |
| `src/api/routers/research.py` | POST/GET endpoints for research sessions |
| `src/api/main.py` | Register research router (modify) |
| `src/models/__init__.py` | Export research models (modify) |
| `pyproject.toml` | Add langgraph, langchain-core, langchain-anthropic deps (modify) |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add LangGraph and LangChain dependencies to pyproject.toml**

Add to the `dependencies` list in `pyproject.toml`:

```toml
"langgraph>=0.2.0",
"langchain-core>=0.3.0",
"langchain-anthropic>=0.3.0",
```

Also add mypy overrides for langchain/langgraph (they may not ship py.typed):

```toml
[[tool.mypy.overrides]]
module = "langgraph.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "langchain_core.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "langchain_anthropic.*"
ignore_missing_imports = true
```

- [ ] **Step 2: Install dependencies**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pip install -e ".[dev]"`
Expected: All packages install successfully, including langgraph, langchain-core, langchain-anthropic.

- [ ] **Step 3: Verify imports work**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify python -c "from langgraph.graph import StateGraph; from langchain_core.language_models import FakeListChatModel; print('OK')"`
Expected: Prints `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add langgraph and langchain dependencies for RESEARCH-001"
```

---

## Task 2: Pydantic Research Models

**Files:**
- Create: `src/models/research.py`
- Test: `tests/unit/models/test_research_models.py`

- [ ] **Step 1: Write failing tests for research models**

Create `tests/unit/models/test_research_models.py`:

```python
"""Tests for research pipeline Pydantic models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.research import (
    EvaluationResult,
    FacetFindings,
    FacetTask,
    ResearchFacet,
    ResearchPlan,
    SourceDocument,
    TopicInput,
)


class TestTopicInput:
    def test_construct_valid(self) -> None:
        topic = TopicInput(
            id=uuid4(),
            title="AI Security Trends",
            description="Emerging threats",
            domain="cybersecurity",
        )
        assert topic.title == "AI Security Trends"

    def test_frozen(self) -> None:
        topic = TopicInput(
            id=uuid4(),
            title="Test",
            description="Desc",
            domain="tech",
        )
        with pytest.raises(ValidationError):
            topic.title = "Changed"  # type: ignore[misc]


class TestResearchFacet:
    def test_construct_valid(self) -> None:
        facet = ResearchFacet(
            index=0,
            title="Recent incidents",
            description="Major security breaches in 2026",
            search_queries=["2026 security breaches", "recent cyber attacks"],
        )
        assert facet.index == 0
        assert len(facet.search_queries) == 2

    def test_empty_queries(self) -> None:
        facet = ResearchFacet(
            index=0,
            title="Test",
            description="Desc",
            search_queries=[],
        )
        assert facet.search_queries == []


class TestResearchPlan:
    def test_construct_with_facets(self) -> None:
        facets = [
            ResearchFacet(
                index=i,
                title=f"Facet {i}",
                description=f"Description {i}",
                search_queries=[f"query {i}"],
            )
            for i in range(3)
        ]
        plan = ResearchPlan(facets=facets, reasoning="Test reasoning")
        assert len(plan.facets) == 3
        assert plan.reasoning == "Test reasoning"


class TestSourceDocument:
    def test_construct_valid(self) -> None:
        doc = SourceDocument(
            url="https://example.com/article",
            title="Test Article",
            snippet="Relevant content...",
            retrieved_at=datetime.now(UTC),
        )
        assert doc.url == "https://example.com/article"


class TestFacetFindings:
    def test_construct_with_sources(self) -> None:
        findings = FacetFindings(
            facet_index=0,
            sources=[
                SourceDocument(
                    url="https://example.com/1",
                    title="Source 1",
                    snippet="Content",
                    retrieved_at=datetime.now(UTC),
                ),
            ],
            claims=["Claim 1"],
            summary="Summary of findings",
        )
        assert len(findings.sources) == 1
        assert findings.facet_index == 0

    def test_empty_sources(self) -> None:
        findings = FacetFindings(
            facet_index=0,
            sources=[],
            claims=[],
            summary="No findings",
        )
        assert findings.sources == []


class TestFacetTask:
    def test_construct_pending(self) -> None:
        task = FacetTask(facet_index=0, status="pending")
        assert task.started_at is None
        assert task.completed_at is None

    def test_frozen(self) -> None:
        task = FacetTask(facet_index=0, status="pending")
        with pytest.raises(ValidationError):
            task.status = "running"  # type: ignore[misc]


class TestEvaluationResult:
    def test_complete(self) -> None:
        result = EvaluationResult(
            is_complete=True,
            weak_facets=[],
            reasoning="All facets covered",
        )
        assert result.is_complete is True
        assert result.weak_facets == []

    def test_incomplete_with_weak_facets(self) -> None:
        result = EvaluationResult(
            is_complete=False,
            weak_facets=[1, 3],
            reasoning="Facets 1 and 3 lack sources",
        )
        assert result.weak_facets == [1, 3]


class TestSerialization:
    def test_topic_input_roundtrip(self) -> None:
        topic = TopicInput(
            id=uuid4(),
            title="Test",
            description="Desc",
            domain="tech",
        )
        data = topic.model_dump()
        restored = TopicInput.model_validate(data)
        assert restored == topic

    def test_research_plan_roundtrip(self) -> None:
        plan = ResearchPlan(
            facets=[
                ResearchFacet(
                    index=0,
                    title="F",
                    description="D",
                    search_queries=["q"],
                ),
            ],
            reasoning="R",
        )
        data = plan.model_dump()
        restored = ResearchPlan.model_validate(data)
        assert restored == plan
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_research_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.research'`

- [ ] **Step 3: Implement research models**

Create `src/models/research.py`:

```python
"""Research pipeline models — orchestrator state and agent contracts.

These models define the data flowing through the LangGraph research
orchestrator. See the RESEARCH-001 spec for full design context.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TopicInput(BaseModel, frozen=True):
    """Narrowed topic data for the orchestrator (avoids API layer import)."""

    id: UUID
    title: str
    description: str
    domain: str


class ResearchFacet(BaseModel, frozen=True):
    """A single research facet within a research plan."""

    index: int
    title: str
    description: str
    search_queries: list[str]


class ResearchPlan(BaseModel, frozen=True):
    """LLM-generated research plan with 3-5 facets."""

    facets: list[ResearchFacet]
    reasoning: str


class SourceDocument(BaseModel, frozen=True):
    """A document retrieved during research."""

    url: str
    title: str
    snippet: str
    retrieved_at: datetime


class FacetFindings(BaseModel, frozen=True):
    """Results from researching a single facet."""

    facet_index: int
    sources: list[SourceDocument]
    claims: list[str]
    summary: str


class FacetTask(BaseModel, frozen=True):
    """Tracks dispatch status for a single facet."""

    facet_index: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None


class EvaluationResult(BaseModel, frozen=True):
    """LLM completeness evaluation of research findings."""

    is_complete: bool
    weak_facets: list[int]
    reasoning: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_research_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run linter**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/models/research.py && "C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/models/research.py`
Expected: No issues

- [ ] **Step 6: Commit**

```bash
git add src/models/research.py tests/unit/models/test_research_models.py
git commit -m "feat(research-001): add research pipeline Pydantic models"
```

---

## Task 3: Research DB Models (In-Memory Stand-ins)

**Files:**
- Create: `src/models/research_db.py`

- [ ] **Step 1: Create research DB models**

Create `src/models/research_db.py`:

```python
"""Research session and agent step models for business state persistence.

These are Pydantic models (not SQLAlchemy) backed by in-memory repositories
for RESEARCH-001. Real DB migration comes in a future ticket.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ResearchSession(BaseModel):
    """Business state for a research session (visible to API)."""

    id: UUID = Field(default_factory=uuid4)
    topic_id: UUID
    status: str = "planning"
    agent_plan: dict[str, object] = Field(default_factory=dict)
    round_count: int = 0
    findings_count: int = 0
    duration_seconds: float | None = None
    started_at: datetime
    completed_at: datetime | None = None


class AgentStep(BaseModel):
    """Tracks an individual step within a research session."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    step_name: str
    status: str = "running"
    input_data: dict[str, object] = Field(default_factory=dict)
    output_data: dict[str, object] = Field(default_factory=dict)
    duration_ms: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
```

- [ ] **Step 2: Update models __init__.py exports**

Add research model exports to `src/models/__init__.py`:

```python
from src.models.research import (
    EvaluationResult,
    FacetFindings,
    FacetTask,
    ResearchFacet,
    ResearchPlan,
    SourceDocument,
    TopicInput,
)
from src.models.research_db import AgentStep, ResearchSession
```

And add them to `__all__`.

- [ ] **Step 3: Add tests for research DB models**

Add to `tests/unit/models/test_research_models.py`:

```python
from src.models.research_db import AgentStep, ResearchSession


class TestResearchSession:
    def test_construct_with_defaults(self) -> None:
        session = ResearchSession(
            topic_id=uuid4(), started_at=datetime.now(UTC)
        )
        assert session.status == "planning"
        assert session.round_count == 0
        assert session.completed_at is None

    def test_model_copy_update(self) -> None:
        session = ResearchSession(
            topic_id=uuid4(), started_at=datetime.now(UTC)
        )
        updated = session.model_copy(update={"status": "complete"})
        assert updated.status == "complete"
        assert session.status == "planning"  # original unchanged


class TestAgentStep:
    def test_construct_with_defaults(self) -> None:
        step = AgentStep(
            session_id=uuid4(),
            step_name="plan_research",
            started_at=datetime.now(UTC),
        )
        assert step.status == "running"
        assert step.duration_ms is None
```

- [ ] **Step 4: Run all model tests**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/models/test_research_models.py -v`
Expected: All tests PASS (including new DB model tests)

- [ ] **Step 5: Commit**

```bash
git add src/models/research_db.py src/models/__init__.py tests/unit/models/test_research_models.py
git commit -m "feat(research-001): add research session and agent step models"
```

---

## Task 4: LangGraph State + Stub Agent

**Files:**
- Create: `src/agents/research/__init__.py`
- Create: `src/agents/research/state.py`
- Create: `src/agents/research/stub.py`
- Test: `tests/unit/agents/research/test_stub.py` (new dir structure)

- [ ] **Step 1: Write failing test for stub agent**

Create `tests/unit/agents/__init__.py` (empty), `tests/unit/agents/research/__init__.py` (empty), and `tests/unit/agents/research/test_stub.py`:

```python
"""Tests for the stub research agent."""

from src.agents.research.stub import stub_research_agent
from src.models.research import FacetFindings, ResearchFacet


class TestStubResearchAgent:
    async def test_returns_findings_for_facet(self) -> None:
        facet = ResearchFacet(
            index=0,
            title="Security trends",
            description="Recent cybersecurity trends",
            search_queries=["cyber trends 2026"],
        )
        result = await stub_research_agent(facet)
        assert isinstance(result, FacetFindings)
        assert result.facet_index == 0
        assert len(result.sources) >= 1
        assert len(result.claims) >= 1
        assert result.summary != ""

    async def test_uses_facet_title_in_output(self) -> None:
        facet = ResearchFacet(
            index=2,
            title="AI regulation",
            description="Government AI policies",
            search_queries=["AI regulation 2026"],
        )
        result = await stub_research_agent(facet)
        assert "AI regulation" in result.summary
        assert result.facet_index == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_stub.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create the agent package and state module**

Create `src/agents/research/__init__.py` (empty).

Create `src/agents/research/state.py`:

```python
"""LangGraph state definition for the research orchestrator."""

import operator
from typing import Annotated, TypedDict
from uuid import UUID

from src.models.research import (
    EvaluationResult,
    FacetFindings,
    FacetTask,
    ResearchPlan,
    TopicInput,
)


class ResearchState(TypedDict):
    """State flowing through the research orchestrator graph.

    Node return semantics: nodes return partial dicts with only changed keys.
    The ``findings`` field uses an additive reducer so that retry rounds
    accumulate rather than replace previous results.
    """

    topic: TopicInput
    research_plan: ResearchPlan | None
    dispatched_tasks: list[FacetTask]
    findings: Annotated[list[FacetFindings], operator.add]
    evaluation: EvaluationResult | None
    round_number: int
    session_id: UUID  # Passed as UUID, LangGraph MemorySaver preserves it
    status: str
    error: str | None
```

- [ ] **Step 4: Implement stub research agent**

Create `src/agents/research/stub.py`:

```python
"""Stub research agent — placeholder for RESEARCH-002/003.

Returns realistic-shaped fake findings. Replace with real web search
(RESEARCH-002) and RAG pipeline (RESEARCH-003) agents.
"""

import asyncio
from datetime import UTC, datetime

from src.models.research import (
    FacetFindings,
    ResearchFacet,
    SourceDocument,
)


async def stub_research_agent(facet: ResearchFacet) -> FacetFindings:
    """Return fake findings shaped like real research output."""
    await asyncio.sleep(0.1)
    return FacetFindings(
        facet_index=facet.index,
        sources=[
            SourceDocument(
                url=f"https://example.com/source-{facet.index}-1",
                title=f"Source for {facet.title}",
                snippet=f"Relevant content about {facet.title}...",
                retrieved_at=datetime.now(UTC),
            ),
        ],
        claims=[f"Key finding about {facet.title}"],
        summary=f"Research summary for facet: {facet.title}",
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_stub.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/agents/research/ tests/unit/agents/
git commit -m "feat(research-001): add LangGraph state schema and stub research agent"
```

---

## Task 5: Task Dispatch Protocol + AsyncIODispatcher

**Files:**
- Create: `src/services/task_dispatch.py`
- Test: `tests/unit/services/test_task_dispatch.py`

- [ ] **Step 1: Write failing tests for task dispatch**

Create `tests/unit/services/test_task_dispatch.py`:

```python
"""Tests for the TaskDispatcher protocol and AsyncIODispatcher."""

import asyncio
import time

import pytest

from src.models.research import FacetFindings, ResearchFacet, SourceDocument
from src.services.task_dispatch import AsyncIODispatcher


def _make_facet(index: int) -> ResearchFacet:
    return ResearchFacet(
        index=index,
        title=f"Facet {index}",
        description=f"Description {index}",
        search_queries=[f"query {index}"],
    )


class TestAsyncIODispatcher:
    async def test_dispatches_all_facets(self) -> None:
        async def agent(facet: ResearchFacet) -> FacetFindings:
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="done",
            )

        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(i) for i in range(3)]
        results = await dispatcher.dispatch(facets, agent)
        assert len(results) == 3
        indices = {r.facet_index for r in results}
        assert indices == {0, 1, 2}

    async def test_runs_in_parallel(self) -> None:
        async def slow_agent(facet: ResearchFacet) -> FacetFindings:
            await asyncio.sleep(0.2)
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="done",
            )

        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(i) for i in range(3)]
        start = time.monotonic()
        await dispatcher.dispatch(facets, slow_agent)
        elapsed = time.monotonic() - start
        # 3 tasks at 0.2s each; parallel should be ~0.2s, not ~0.6s
        assert elapsed < 0.5

    async def test_timeout_returns_empty_findings(self) -> None:
        async def hanging_agent(facet: ResearchFacet) -> FacetFindings:
            await asyncio.sleep(10)
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="done",
            )

        dispatcher = AsyncIODispatcher(timeout_seconds=0.3)
        facets = [_make_facet(0)]
        results = await dispatcher.dispatch(facets, hanging_agent)
        assert len(results) == 1
        assert results[0].sources == []
        assert results[0].summary == ""

    async def test_partial_failure(self) -> None:
        call_count = 0

        async def flaky_agent(facet: ResearchFacet) -> FacetFindings:
            nonlocal call_count
            call_count += 1
            if facet.index == 1:
                raise RuntimeError("Agent crashed")
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=["claim"],
                summary="done",
            )

        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(i) for i in range(3)]
        results = await dispatcher.dispatch(facets, flaky_agent)
        assert len(results) == 3
        # Failed facet gets empty findings
        failed = next(r for r in results if r.facet_index == 1)
        assert failed.sources == []
        assert failed.summary == ""
        # Successful facets are intact
        ok = [r for r in results if r.facet_index != 1]
        assert all(r.claims == ["claim"] for r in ok)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_task_dispatch.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement task dispatch**

Create `src/services/task_dispatch.py`:

```python
"""Task dispatch protocol and implementations.

Provides a protocol for dispatching research facets to agent functions
in parallel. AsyncIODispatcher uses asyncio.gather; future CeleryDispatcher
will use Celery task queues (same protocol).
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol

import structlog

from src.models.research import FacetFindings, ResearchFacet

logger = structlog.get_logger()

AgentFunction = Callable[[ResearchFacet], Awaitable[FacetFindings]]


class TaskDispatcher(Protocol):
    """Protocol for dispatching research facets to agent functions."""

    async def dispatch(
        self, facets: list[ResearchFacet], agent_fn: AgentFunction
    ) -> list[FacetFindings]: ...


class AsyncIODispatcher:
    """Dispatches facets in parallel using asyncio.gather."""

    def __init__(self, timeout_seconds: float = 300.0) -> None:
        self._timeout = timeout_seconds

    async def dispatch(
        self, facets: list[ResearchFacet], agent_fn: AgentFunction
    ) -> list[FacetFindings]:
        tasks = [self._run_one(facet, agent_fn) for facet in facets]
        return list(await asyncio.gather(*tasks))

    async def _run_one(
        self, facet: ResearchFacet, agent_fn: AgentFunction
    ) -> FacetFindings:
        try:
            return await asyncio.wait_for(
                agent_fn(facet), timeout=self._timeout
            )
        except (TimeoutError, Exception) as exc:
            logger.warning(
                "facet_dispatch_failed",
                facet_index=facet.index,
                error=str(exc),
            )
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="",
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_task_dispatch.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/task_dispatch.py tests/unit/services/test_task_dispatch.py
git commit -m "feat(research-001): add TaskDispatcher protocol and AsyncIODispatcher"
```

---

## Task 6: Research Planner (LLM-based)

**Files:**
- Create: `src/agents/research/planner.py`
- Test: `tests/unit/agents/research/test_planner.py`

- [ ] **Step 1: Write failing tests for planner**

Create `tests/unit/agents/research/test_planner.py`:

```python
"""Tests for the LLM-based research planner."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.planner import generate_research_plan
from src.models.research import ResearchPlan, TopicInput
from uuid import uuid4


def _make_topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="AI Security Trends in 2026",
        description="Emerging threats and defenses in AI systems",
        domain="cybersecurity",
    )


def _plan_json(num_facets: int = 3) -> str:
    facets = [
        {
            "index": i,
            "title": f"Facet {i}",
            "description": f"Description {i}",
            "search_queries": [f"query {i}a", f"query {i}b"],
        }
        for i in range(num_facets)
    ]
    return json.dumps({"facets": facets, "reasoning": "Test reasoning"})


class TestGenerateResearchPlan:
    async def test_returns_plan_with_facets(self) -> None:
        llm = FakeListChatModel(responses=[_plan_json(3)])
        plan = await generate_research_plan(_make_topic(), llm)
        assert isinstance(plan, ResearchPlan)
        assert len(plan.facets) == 3
        assert plan.reasoning == "Test reasoning"

    async def test_each_facet_has_required_fields(self) -> None:
        llm = FakeListChatModel(responses=[_plan_json(4)])
        plan = await generate_research_plan(_make_topic(), llm)
        for facet in plan.facets:
            assert facet.title != ""
            assert facet.description != ""
            assert len(facet.search_queries) >= 1

    async def test_handles_malformed_json(self) -> None:
        llm = FakeListChatModel(responses=["not valid json", _plan_json(3)])
        plan = await generate_research_plan(_make_topic(), llm)
        # Should retry once and succeed on second response
        assert isinstance(plan, ResearchPlan)

    async def test_raises_on_repeated_malformed_json(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        with pytest.raises(ValueError, match="Failed to generate"):
            await generate_research_plan(_make_topic(), llm)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_planner.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement planner**

Create `src/agents/research/planner.py`:

```python
"""LLM-based research plan generation.

Calls Claude Sonnet to decompose a topic into 3-5 research facets
with search queries per facet.
"""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.research import ResearchPlan, TopicInput

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You are a research planning assistant. Given a topic, generate a "
    "research plan with 3-5 facets. Each facet should cover a distinct "
    "angle of the topic. Respond with valid JSON only."
)

_USER_TEMPLATE = (
    "Plan research for this topic:\n"
    "Title: {title}\n"
    "Description: {description}\n"
    "Domain: {domain}\n\n"
    "Return JSON: {{\"facets\": [{{\"index\": 0, \"title\": \"...\", "
    "\"description\": \"...\", \"search_queries\": [\"...\"]}}], "
    "\"reasoning\": \"...\"}}"
)

_MAX_RETRIES = 2


async def generate_research_plan(
    topic: TopicInput, llm: BaseChatModel
) -> ResearchPlan:
    """Generate a research plan from a topic via LLM."""
    user_msg = _USER_TEMPLATE.format(
        title=topic.title,
        description=topic.description,
        domain=topic.domain,
    )
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_msg)]

    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = json.loads(response.content)
            return ResearchPlan.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "plan_parse_failed",
                attempt=attempt + 1,
                error=str(exc),
            )

    msg = f"Failed to generate research plan after {_MAX_RETRIES} attempts"
    raise ValueError(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_planner.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/research/planner.py tests/unit/agents/research/test_planner.py
git commit -m "feat(research-001): add LLM-based research planner"
```

---

## Task 7: Research Evaluator (LLM-based with Guardrails)

**Files:**
- Create: `src/agents/research/evaluator.py`
- Test: `tests/unit/agents/research/test_evaluator.py`

- [ ] **Step 1: Write failing tests for evaluator**

Create `tests/unit/agents/research/test_evaluator.py`:

```python
"""Tests for the LLM-based completeness evaluator."""

import json
from datetime import UTC, datetime

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.evaluator import EvaluationContext, evaluate_completeness
from src.models.research import (
    EvaluationResult,
    FacetFindings,
    SourceDocument,
    TopicInput,
)
from uuid import uuid4


def _make_topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="Test Topic",
        description="Test",
        domain="tech",
    )


def _make_findings(
    facet_index: int, num_sources: int = 2
) -> FacetFindings:
    sources = [
        SourceDocument(
            url=f"https://example.com/{facet_index}/{i}",
            title=f"Source {i}",
            snippet="Content",
            retrieved_at=datetime.now(UTC),
        )
        for i in range(num_sources)
    ]
    return FacetFindings(
        facet_index=facet_index,
        sources=sources,
        claims=["claim"],
        summary="summary",
    )


def _eval_json(
    is_complete: bool, weak_facets: list[int] | None = None
) -> str:
    return json.dumps({
        "is_complete": is_complete,
        "weak_facets": weak_facets or [],
        "reasoning": "Test reasoning",
    })


class TestEvaluateCompleteness:
    async def test_returns_complete(self) -> None:
        llm = FakeListChatModel(responses=[_eval_json(True)])
        findings = [_make_findings(0), _make_findings(1)]
        ctx = EvaluationContext(
            topic=_make_topic(), findings=findings, round_number=1
        )
        result = await evaluate_completeness(ctx, llm=llm)
        assert isinstance(result, EvaluationResult)
        assert result.is_complete is True

    async def test_identifies_weak_facets(self) -> None:
        llm = FakeListChatModel(
            responses=[_eval_json(False, [1])]
        )
        findings = [_make_findings(0), _make_findings(1)]
        ctx = EvaluationContext(
            topic=_make_topic(), findings=findings, round_number=1
        )
        result = await evaluate_completeness(ctx, llm=llm)
        assert result.is_complete is False
        assert 1 in result.weak_facets

    async def test_guardrail_forces_complete_at_max_rounds(self) -> None:
        # LLM says incomplete, but round 2 guardrail forces complete
        llm = FakeListChatModel(
            responses=[_eval_json(False, [0, 1])]
        )
        findings = [_make_findings(0), _make_findings(1)]
        ctx = EvaluationContext(
            topic=_make_topic(), findings=findings, round_number=2
        )
        result = await evaluate_completeness(ctx, llm=llm)
        assert result.is_complete is True

    async def test_guardrail_zero_sources_always_weak(self) -> None:
        # Facet 1 has zero sources — should be marked weak
        llm = FakeListChatModel(responses=[_eval_json(True)])
        findings = [
            _make_findings(0, num_sources=2),
            FacetFindings(
                facet_index=1, sources=[], claims=[], summary=""
            ),
        ]
        ctx = EvaluationContext(
            topic=_make_topic(), findings=findings, round_number=1
        )
        result = await evaluate_completeness(ctx, llm=llm)
        # Even though LLM says complete, zero-source guardrail overrides
        assert result.is_complete is False
        assert 1 in result.weak_facets
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_evaluator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement evaluator**

Create `src/agents/research/evaluator.py`:

```python
"""LLM-based completeness evaluation with heuristic guardrails.

Calls Claude Sonnet to judge whether research findings are sufficient.
Hard guardrails enforce max 2 rounds and flag zero-source facets.
"""

import json
from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.research import (
    EvaluationResult,
    FacetFindings,
    TopicInput,
)

logger = structlog.get_logger()

_MAX_ROUNDS = 2

_SYSTEM_PROMPT = (
    "You are a research completeness evaluator. Given a topic and "
    "research findings, determine if the findings are sufficient for "
    "a comprehensive article. Respond with valid JSON only."
)

_USER_TEMPLATE = (
    "Topic: {title} ({domain})\n\n"
    "Findings per facet:\n{findings_summary}\n\n"
    "Are these findings sufficient? Identify weak facets by index.\n"
    "Return JSON: {{\"is_complete\": bool, \"weak_facets\": [int], "
    "\"reasoning\": \"...\"}}"
)


def _summarize_findings(findings: list[FacetFindings]) -> str:
    lines = []
    for f in findings:
        lines.append(
            f"Facet {f.facet_index}: {len(f.sources)} sources, "
            f"{len(f.claims)} claims — {f.summary[:100]}"
        )
    return "\n".join(lines)


def _apply_guardrails(
    result: EvaluationResult,
    findings: list[FacetFindings],
    round_number: int,
) -> EvaluationResult:
    # Guardrail: force complete at max rounds
    if round_number >= _MAX_ROUNDS:
        return EvaluationResult(
            is_complete=True,
            weak_facets=[],
            reasoning=f"Forced complete at round {round_number}",
        )

    # Guardrail: zero-source facets are always weak
    zero_source = [
        f.facet_index for f in findings if len(f.sources) == 0
    ]
    if zero_source:
        all_weak = list(set(result.weak_facets) | set(zero_source))
        return EvaluationResult(
            is_complete=False,
            weak_facets=all_weak,
            reasoning=result.reasoning,
        )

    return result


@dataclass(frozen=True)
class EvaluationContext:
    """Bundles evaluation inputs to respect 3-param limit."""
    topic: TopicInput
    findings: list[FacetFindings]
    round_number: int


async def evaluate_completeness(
    ctx: EvaluationContext, llm: BaseChatModel
) -> EvaluationResult:
    """Evaluate research completeness via LLM + guardrails."""
    user_msg = _USER_TEMPLATE.format(
        title=ctx.topic.title,
        domain=ctx.topic.domain,
        findings_summary=_summarize_findings(ctx.findings),
    )
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_msg)]
    response = await llm.ainvoke(messages)

    try:
        data = json.loads(response.content)
        result = EvaluationResult.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("evaluation_parse_failed", error=str(exc))
        result = EvaluationResult(
            is_complete=False,
            weak_facets=[],
            reasoning=f"Parse error: {exc}",
        )

    return _apply_guardrails(result, ctx.findings, ctx.round_number)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_evaluator.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/research/evaluator.py tests/unit/agents/research/test_evaluator.py
git commit -m "feat(research-001): add LLM-based completeness evaluator with guardrails"
```

---

## Task 8: LangGraph Orchestrator + Runner

**Files:**
- Create: `src/agents/research/orchestrator.py`
- Create: `src/agents/research/runner.py`
- Test: `tests/unit/agents/research/test_orchestrator.py`

- [ ] **Step 1: Write failing tests for orchestrator**

Create `tests/unit/agents/research/test_orchestrator.py`:

```python
"""Tests for the LangGraph research orchestrator.

Uses FakeLLM for deterministic plan/evaluate responses and
stub agents for dispatch. Tests graph topology and state transitions.
"""

import json
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.orchestrator import build_graph
from src.agents.research.runner import LangGraphResearchOrchestrator
from src.agents.research.stub import stub_research_agent
from src.models.research import TopicInput
from src.services.task_dispatch import AsyncIODispatcher


def _make_topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="AI Security Trends",
        description="Emerging threats",
        domain="cybersecurity",
    )


def _plan_json(num_facets: int = 3) -> str:
    facets = [
        {
            "index": i,
            "title": f"Facet {i}",
            "description": f"Desc {i}",
            "search_queries": [f"q{i}"],
        }
        for i in range(num_facets)
    ]
    return json.dumps({"facets": facets, "reasoning": "Plan reasoning"})


def _eval_json(is_complete: bool, weak: list[int] | None = None) -> str:
    return json.dumps({
        "is_complete": is_complete,
        "weak_facets": weak or [],
        "reasoning": "Eval reasoning",
    })


class TestOrchestrator:
    def _initial_state(self) -> dict:
        return {
            "topic": _make_topic(),
            "research_plan": None,
            "dispatched_tasks": [],
            "findings": [],
            "evaluation": None,
            "round_number": 0,
            "session_id": uuid4(),
            "status": "initial",
            "error": None,
        }

    async def test_happy_path_completes(self) -> None:
        """Topic → plan → dispatch → evaluate (complete) → finalize."""
        llm = FakeListChatModel(responses=[_plan_json(3), _eval_json(True)])
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent)
        result = await graph.ainvoke(self._initial_state())
        assert result["status"] == "complete"
        assert len(result["findings"]) == 3
        assert result["round_number"] == 1

    async def test_retry_path(self) -> None:
        """Evaluate incomplete → retry weak facets → complete."""
        llm = FakeListChatModel(responses=[
            _plan_json(3),
            _eval_json(False, [1]),  # Round 1: facet 1 weak
            _eval_json(True),         # Round 2: complete
        ])
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent)
        result = await graph.ainvoke(self._initial_state())
        assert result["status"] == "complete"
        # Round 1: 3 facets + Round 2: 1 weak facet retried = 4
        assert len(result["findings"]) == 4
        assert result["round_number"] == 2

    async def test_max_rounds_stops_at_two(self) -> None:
        """Guardrail: stops at round 2 even if LLM says incomplete."""
        llm = FakeListChatModel(responses=[
            _plan_json(3),
            _eval_json(False, [0, 1, 2]),  # Round 1: all weak
            _eval_json(False, [0, 1, 2]),  # Round 2: guardrail forces complete
        ])
        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        graph = build_graph(llm, dispatcher, stub_research_agent)
        result = await graph.ainvoke(self._initial_state())
        assert result["status"] == "complete"
        assert result["round_number"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement orchestrator graph wiring**

Create `src/agents/research/orchestrator.py`:

```python
"""LangGraph StateGraph wiring for the research orchestrator.

Contains only the build_graph() factory — no business logic.
Node functions delegate to planner.py, evaluator.py, and the dispatcher.
"""

from datetime import UTC, datetime

import structlog
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.research.evaluator import EvaluationContext, evaluate_completeness
from src.agents.research.planner import generate_research_plan
from src.agents.research.state import ResearchState
from src.models.research import (
    EvaluationResult,
    FacetFindings,
    FacetTask,
    ResearchFacet,
    ResearchPlan,
    TopicInput,
)
from src.services.task_dispatch import AgentFunction, TaskDispatcher

logger = structlog.get_logger()


def _validate_topic(state: ResearchState) -> TopicInput:
    raw = state["topic"]
    return raw if isinstance(raw, TopicInput) else TopicInput.model_validate(raw)


def _validate_plan(state: ResearchState) -> ResearchPlan:
    raw = state["research_plan"]
    return raw if isinstance(raw, ResearchPlan) else ResearchPlan.model_validate(raw)


def _validate_evaluation(state: ResearchState) -> EvaluationResult | None:
    raw = state.get("evaluation")
    if raw is None:
        return None
    return raw if isinstance(raw, EvaluationResult) else EvaluationResult.model_validate(raw)


def _validate_findings(state: ResearchState) -> list[FacetFindings]:
    return [
        f if isinstance(f, FacetFindings) else FacetFindings.model_validate(f)
        for f in state["findings"]
    ]


def build_graph(
    llm: BaseChatModel,
    dispatcher: TaskDispatcher,
    agent_fn: AgentFunction,
) -> CompiledStateGraph:
    """Build and compile the research orchestrator graph."""
    graph = StateGraph(ResearchState)

    async def plan_research(state: ResearchState) -> dict:  # type: ignore[type-arg]
        topic = _validate_topic(state)
        plan = await generate_research_plan(topic, llm)
        return {"research_plan": plan, "status": "planning"}

    async def dispatch_agents(state: ResearchState) -> dict:  # type: ignore[type-arg]
        plan = _validate_plan(state)
        evaluation = _validate_evaluation(state)
        if evaluation and evaluation.weak_facets:
            weak = set(evaluation.weak_facets)
            facets = [f for f in plan.facets if f.index in weak]
        else:
            facets = list(plan.facets)

        results = await dispatcher.dispatch(facets, agent_fn)

        now = datetime.now(UTC)
        tasks = [
            FacetTask(
                facet_index=f.index,
                status="completed",
                started_at=now,
                completed_at=now,
            )
            for f in facets
        ]
        return {
            "findings": results,
            "dispatched_tasks": tasks,
            "round_number": state["round_number"] + 1,
            "status": "researching",
        }

    async def evaluate(state: ResearchState) -> dict:  # type: ignore[type-arg]
        topic = _validate_topic(state)
        findings = _validate_findings(state)
        ctx = EvaluationContext(
            topic=topic, findings=findings, round_number=state["round_number"]
        )
        result = await evaluate_completeness(ctx, llm)
        return {"evaluation": result, "status": "evaluating"}

    def should_retry(state: ResearchState) -> str:
        evaluation = _validate_evaluation(state)
        if evaluation and not evaluation.is_complete and state["round_number"] < 2:
            return "retry"
        return "finalize"

    async def finalize(state: ResearchState) -> dict:  # type: ignore[type-arg]
        return {"status": "complete"}

    graph.add_node("plan_research", plan_research)
    graph.add_node("dispatch_agents", dispatch_agents)
    graph.add_node("evaluate_completeness", evaluate)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("plan_research")
    graph.add_edge("plan_research", "dispatch_agents")
    graph.add_edge("dispatch_agents", "evaluate_completeness")
    graph.add_conditional_edges(
        "evaluate_completeness",
        should_retry,
        {"retry": "dispatch_agents", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()
```

- [ ] **Step 4: Implement runner protocol**

Create `src/agents/research/runner.py`:

```python
"""ResearchOrchestrator protocol and LangGraph implementation.

The runner wraps the compiled graph and manages session lifecycle.
The service layer depends on the protocol, not the concrete class.
"""

from typing import Protocol
from uuid import UUID

from langgraph.graph.state import CompiledStateGraph

from src.agents.research.state import ResearchState
from src.models.research import TopicInput


class ResearchOrchestrator(Protocol):
    """Protocol for running research orchestration."""

    async def run(
        self, session_id: UUID, topic: TopicInput
    ) -> ResearchState: ...


class LangGraphResearchOrchestrator:
    """Runs the compiled LangGraph research graph."""

    def __init__(self, compiled_graph: CompiledStateGraph) -> None:
        self._graph = compiled_graph

    async def run(
        self, session_id: UUID, topic: TopicInput
    ) -> ResearchState:
        initial_state: ResearchState = {
            "topic": topic,
            "research_plan": None,
            "dispatched_tasks": [],
            "findings": [],
            "evaluation": None,
            "round_number": 0,
            "session_id": session_id,
            "status": "initial",
            "error": None,
        }
        result = await self._graph.ainvoke(initial_state)
        return result  # type: ignore[return-value]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/agents/research/test_orchestrator.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/agents/research/orchestrator.py src/agents/research/runner.py tests/unit/agents/research/test_orchestrator.py
git commit -m "feat(research-001): add LangGraph orchestrator graph and runner"
```

---

## Task 9: Research Service + Repositories

**Files:**
- Create: `src/services/research.py`
- Test: `tests/unit/services/test_research_service.py`

- [ ] **Step 1: Write failing tests for research service**

Create `tests/unit/services/test_research_service.py`:

```python
"""Tests for the ResearchService."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.research import TopicInput
from src.models.research_db import AgentStep, ResearchSession
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
from src.api.errors import NotFoundError


class FakeOrchestrator:
    """Test double for ResearchOrchestrator."""

    def __init__(self, should_fail: bool = False) -> None:
        self.calls: list[tuple] = []
        self._should_fail = should_fail

    async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
        self.calls.append((session_id, topic))
        if self._should_fail:
            raise RuntimeError("Orchestrator failed")
        return {"status": "complete"}


def _make_repos(
    topic_ids: list | None = None,
) -> ResearchRepositories:
    topics = InMemoryTopicRepository()
    for tid in topic_ids or []:
        topics.seed(TopicInput(
            id=tid,
            title="Test",
            description="Desc",
            domain="tech",
        ))
    return ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=topics,
    )


class TestStartSession:
    async def test_creates_session(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator())
        session = await svc.start_session(topic_id)
        assert session.topic_id == topic_id
        assert session.status == "planning"

    async def test_rejects_invalid_topic(self) -> None:
        repos = _make_repos([])
        svc = ResearchService(repos, FakeOrchestrator())
        with pytest.raises(NotFoundError):
            await svc.start_session(uuid4())


class TestGetSession:
    async def test_returns_session_with_steps(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator())
        session = await svc.start_session(topic_id)
        detail = await svc.get_session(session.id)
        assert detail.session.id == session.id

    async def test_not_found(self) -> None:
        repos = _make_repos([])
        svc = ResearchService(repos, FakeOrchestrator())
        with pytest.raises(NotFoundError):
            await svc.get_session(uuid4())


class TestListSessions:
    async def test_returns_paginated(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator())
        await svc.start_session(topic_id)
        await svc.start_session(topic_id)
        result = await svc.list_sessions(None, page=1, size=10)
        assert result.total == 2
        assert len(result.items) == 2

    async def test_filters_by_status(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator())
        await svc.start_session(topic_id)
        result = await svc.list_sessions("complete", page=1, size=10)
        assert result.total == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_research_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement research service and in-memory repos**

Create `src/services/research.py`:

```python
"""Research service — bridges API layer to the orchestrator.

Contains repository protocols, in-memory implementations, and
the ResearchService that manages session lifecycle.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel

from src.agents.research.runner import ResearchOrchestrator
from src.api.errors import NotFoundError
from src.models.research import TopicInput
from src.models.research_db import AgentStep, ResearchSession

logger = structlog.get_logger()


# --- Repository protocols ---

class ResearchSessionRepository(Protocol):
    async def create(self, session: ResearchSession) -> ResearchSession: ...
    async def get(self, session_id: UUID) -> ResearchSession | None: ...
    async def update(self, session: ResearchSession) -> ResearchSession: ...
    async def list(
        self, status: str | None, page: int, size: int
    ) -> tuple[list[ResearchSession], int]: ...


class AgentStepRepository(Protocol):
    async def create(self, step: AgentStep) -> AgentStep: ...
    async def list_by_session(self, session_id: UUID) -> list[AgentStep]: ...


class TopicRepository(Protocol):
    async def exists(self, topic_id: UUID) -> bool: ...
    async def get(self, topic_id: UUID) -> TopicInput | None: ...


# --- In-memory implementations ---

class InMemoryResearchSessionRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, ResearchSession] = {}

    async def create(self, session: ResearchSession) -> ResearchSession:
        self._store[session.id] = session
        return session

    async def get(self, session_id: UUID) -> ResearchSession | None:
        return self._store.get(session_id)

    async def update(self, session: ResearchSession) -> ResearchSession:
        self._store[session.id] = session
        return session

    async def list(
        self, status: str | None, page: int, size: int
    ) -> tuple[list[ResearchSession], int]:
        items = list(self._store.values())
        if status:
            items = [s for s in items if s.status == status]
        total = len(items)
        start = (page - 1) * size
        return items[start : start + size], total


class InMemoryAgentStepRepository:
    def __init__(self) -> None:
        self._store: list[AgentStep] = []

    async def create(self, step: AgentStep) -> AgentStep:
        self._store.append(step)
        return step

    async def list_by_session(self, session_id: UUID) -> list[AgentStep]:
        return [s for s in self._store if s.session_id == session_id]


class InMemoryTopicRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, TopicInput] = {}

    def seed(self, topic: TopicInput) -> None:
        self._store[topic.id] = topic

    async def exists(self, topic_id: UUID) -> bool:
        return topic_id in self._store

    async def get(self, topic_id: UUID) -> TopicInput | None:
        return self._store.get(topic_id)


# --- Service ---

@dataclass(frozen=True)
class ResearchRepositories:
    sessions: ResearchSessionRepository
    steps: AgentStepRepository
    topics: TopicRepository


class SessionDetail(BaseModel):
    session: ResearchSession
    steps: list[AgentStep]


class PaginatedSessions(BaseModel):
    items: list[ResearchSession]
    total: int
    page: int
    size: int


class ResearchService:
    def __init__(
        self,
        repos: ResearchRepositories,
        orchestrator: ResearchOrchestrator,
    ) -> None:
        self._repos = repos
        self._orchestrator = orchestrator

    async def start_session(self, topic_id: UUID) -> ResearchSession:
        if not await self._repos.topics.exists(topic_id):
            raise NotFoundError(f"Topic {topic_id} not found")
        session = ResearchSession(
            topic_id=topic_id, started_at=datetime.now(UTC)
        )
        return await self._repos.sessions.create(session)

    async def get_topic(self, topic_id: UUID) -> TopicInput:
        """Fetch a topic by ID. Raises NotFoundError if missing."""
        topic = await self._repos.topics.get(topic_id)
        if topic is None:
            raise NotFoundError(f"Topic {topic_id} not found")
        return topic

    async def get_session(self, session_id: UUID) -> SessionDetail:
        session = await self._repos.sessions.get(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id} not found")
        steps = await self._repos.steps.list_by_session(session_id)
        return SessionDetail(session=session, steps=steps)

    async def list_sessions(
        self, status: str | None, page: int, size: int
    ) -> PaginatedSessions:
        items, total = await self._repos.sessions.list(status, page, size)
        return PaginatedSessions(
            items=items, total=total, page=page, size=size
        )

    async def run_and_finalize(
        self, session_id: UUID, topic: TopicInput
    ) -> None:
        try:
            await self._orchestrator.run(session_id, topic)
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/services/test_research_service.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/research.py tests/unit/services/test_research_service.py
git commit -m "feat(research-001): add ResearchService with in-memory repositories"
```

---

## Task 10: API Schemas + Router + Registration

**Files:**
- Create: `src/api/schemas/research.py`
- Create: `src/api/routers/research.py`
- Modify: `src/api/main.py`
- Test: `tests/unit/api/test_research_endpoints.py`

- [ ] **Step 1: Write failing tests for API endpoints**

Create `tests/unit/api/test_research_endpoints.py`:

```python
"""Tests for the research session API endpoints."""

from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.models.research import TopicInput
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
from tests.unit.api.conftest import make_auth_header


class FakeOrchestrator:
    async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
        return {"status": "complete"}


@pytest.fixture
def test_topic_id() -> str:
    return str(uuid4())


@pytest.fixture
def research_app(auth_settings: Settings, test_topic_id: str) -> FastAPI:
    app = create_app(auth_settings)
    topic_repo = InMemoryTopicRepository()
    from uuid import UUID
    topic_repo.seed(TopicInput(
        id=UUID(test_topic_id),
        title="Test Topic",
        description="Desc",
        domain="tech",
    ))
    repos = ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=topic_repo,
    )
    svc = ResearchService(repos, FakeOrchestrator())
    app.state.research_service = svc
    return app


@pytest.fixture
async def research_client(
    research_app: FastAPI,
) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=research_app),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]


class TestCreateSession:
    async def test_returns_201(
        self, research_client: httpx.AsyncClient, auth_settings: Settings, test_topic_id: str
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": test_topic_id},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert data["status"] == "planning"

    async def test_viewer_cannot_create(
        self, research_client: httpx.AsyncClient, auth_settings: Settings, test_topic_id: str
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": test_topic_id},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_invalid_topic_returns_404(
        self, research_client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": str(uuid4())},
            headers=headers,
        )
        assert resp.status_code == 404


class TestGetSession:
    async def test_returns_session(
        self, research_client: httpx.AsyncClient, auth_settings: Settings, test_topic_id: str
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        create_resp = await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": test_topic_id},
            headers=headers,
        )
        session_id = create_resp.json()["session_id"]
        resp = await research_client.get(
            f"/api/v1/research/sessions/{session_id}",
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session_id

    async def test_not_found(
        self, research_client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await research_client.get(
            f"/api/v1/research/sessions/{uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 404


class TestListSessions:
    async def test_returns_paginated_list(
        self, research_client: httpx.AsyncClient, auth_settings: Settings, test_topic_id: str
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": test_topic_id},
            headers=headers,
        )
        resp = await research_client.get(
            "/api/v1/research/sessions",
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_research_endpoints.py -v`
Expected: FAIL

- [ ] **Step 3: Create API schemas**

Create `src/api/schemas/research.py`:

```python
"""Request/response schemas for the research sessions API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateResearchSessionRequest(BaseModel):
    topic_id: UUID


class CreateResearchSessionResponse(BaseModel):
    session_id: UUID
    status: str
    started_at: datetime


class AgentStepResponse(BaseModel):
    step_name: str
    status: str
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None


class ResearchSessionResponse(BaseModel):
    session_id: UUID
    status: str
    round_count: int
    findings_count: int
    duration_seconds: float | None
    started_at: datetime
    completed_at: datetime | None
    steps: list[AgentStepResponse]


class ResearchSessionSummary(BaseModel):
    session_id: UUID
    topic_id: UUID
    status: str
    round_count: int
    findings_count: int
    started_at: datetime


class PaginatedResearchSessions(BaseModel):
    items: list[ResearchSessionSummary]
    total: int
    page: int
    size: int
```

- [ ] **Step 4: Create research router**

Create `src/api/routers/research.py`:

```python
"""Research session API endpoints."""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.rate_limiter import limiter
from src.api.schemas.research import (
    AgentStepResponse,
    CreateResearchSessionRequest,
    CreateResearchSessionResponse,
    PaginatedResearchSessions,
    ResearchSessionResponse,
    ResearchSessionSummary,
)
from src.services.research import ResearchService

logger = structlog.get_logger()

research_router = APIRouter()


def _get_research_service(request: Request) -> ResearchService:
    return request.app.state.research_service  # type: ignore[no-any-return]


@limiter.limit("3/minute")
@research_router.post(
    "/research/sessions",
    response_model=CreateResearchSessionResponse,
    status_code=HTTP_201_CREATED,
)
async def create_research_session(
    request: Request,
    body: CreateResearchSessionRequest,
    background_tasks: BackgroundTasks,
    user: TokenPayload = Depends(require_editor_or_above),
) -> CreateResearchSessionResponse:
    svc = _get_research_service(request)
    session = await svc.start_session(body.topic_id)
    topic = await svc.get_topic(body.topic_id)
    background_tasks.add_task(svc.run_and_finalize, session.id, topic)
    return CreateResearchSessionResponse(
        session_id=session.id,
        status=session.status,
        started_at=session.started_at,
    )


@limiter.limit("30/minute")
@research_router.get(
    "/research/sessions/{session_id}",
    response_model=ResearchSessionResponse,
)
async def get_research_session(
    request: Request,
    session_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> ResearchSessionResponse:
    from uuid import UUID
    svc = _get_research_service(request)
    detail = await svc.get_session(UUID(session_id))
    s = detail.session
    steps = [
        AgentStepResponse(
            step_name=st.step_name,
            status=st.status,
            duration_ms=st.duration_ms,
            started_at=st.started_at,
            completed_at=st.completed_at,
        )
        for st in detail.steps
    ]
    return ResearchSessionResponse(
        session_id=s.id,
        status=s.status,
        round_count=s.round_count,
        findings_count=s.findings_count,
        duration_seconds=s.duration_seconds,
        started_at=s.started_at,
        completed_at=s.completed_at,
        steps=steps,
    )


@limiter.limit("30/minute")
@research_router.get(
    "/research/sessions",
    response_model=PaginatedResearchSessions,
)
async def list_research_sessions(
    request: Request,
    user: TokenPayload = Depends(require_viewer_or_above),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResearchSessions:
    svc = _get_research_service(request)
    result = await svc.list_sessions(status, page, size)
    items = [
        ResearchSessionSummary(
            session_id=s.id,
            topic_id=s.topic_id,
            status=s.status,
            round_count=s.round_count,
            findings_count=s.findings_count,
            started_at=s.started_at,
        )
        for s in result.items
    ]
    return PaginatedResearchSessions(
        items=items, total=result.total, page=result.page, size=result.size
    )
```

- [ ] **Step 5: Register research router in main.py**

Add to `src/api/main.py` imports:

```python
from src.api.routers.research import research_router
```

Add to `_register_routers`:

```python
app.include_router(
    research_router,
    prefix=settings.api_v1_prefix,
    tags=["research"],
)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/unit/api/test_research_endpoints.py -v`
Expected: All tests PASS

- [ ] **Step 7: Run full test suite for regressions**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/api/schemas/research.py src/api/routers/research.py src/api/main.py tests/unit/api/test_research_endpoints.py
git commit -m "feat(research-001): add research session API endpoints"
```

---

## Task 11: Integration Test

**Files:**
- Create: `tests/integration/test_research_flow.py`

- [ ] **Step 1: Write integration test**

Create `tests/integration/test_research_flow.py`:

```python
"""Integration test: full research flow through API → service → orchestrator."""

import json
from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.orchestrator import build_graph
from src.agents.research.runner import LangGraphResearchOrchestrator
from src.agents.research.stub import stub_research_agent
from src.api.main import create_app
from src.config.settings import Settings
from src.models.research import TopicInput
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
from tests.unit.api.conftest import make_auth_header


def _generate_test_keys() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


_PRIVATE_KEY, _PUBLIC_KEY = _generate_test_keys()


def _plan_json() -> str:
    facets = [
        {"index": i, "title": f"F{i}", "description": f"D{i}", "search_queries": [f"q{i}"]}
        for i in range(3)
    ]
    return json.dumps({"facets": facets, "reasoning": "Plan"})


def _eval_json() -> str:
    return json.dumps({"is_complete": True, "weak_facets": [], "reasoning": "Good"})


@pytest.fixture
def integration_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def integration_app(integration_settings: Settings) -> FastAPI:
    app = create_app(integration_settings)

    llm = FakeListChatModel(responses=[_plan_json(), _eval_json()])
    from src.services.task_dispatch import AsyncIODispatcher
    dispatcher = AsyncIODispatcher(timeout_seconds=10)
    graph = build_graph(llm, dispatcher, stub_research_agent)
    orchestrator = LangGraphResearchOrchestrator(graph)

    topic_id = uuid4()
    topic_repo = InMemoryTopicRepository()
    topic_repo.seed(TopicInput(id=topic_id, title="Test", description="D", domain="tech"))

    repos = ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=topic_repo,
    )
    svc = ResearchService(repos, orchestrator)
    app.state.research_service = svc
    app.state._test_topic_id = str(topic_id)
    return app


@pytest.fixture
async def integration_client(
    integration_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestResearchFlow:
    async def test_create_and_get_session(
        self, integration_client: httpx.AsyncClient, integration_settings: Settings, integration_app: FastAPI
    ) -> None:
        topic_id = integration_app.state._test_topic_id
        headers = make_auth_header("editor", integration_settings)

        # Create session
        resp = await integration_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": topic_id},
            headers=headers,
        )
        assert resp.status_code == 201
        session_id = resp.json()["session_id"]

        # Get session
        resp = await integration_client.get(
            f"/api/v1/research/sessions/{session_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session_id
```

- [ ] **Step 2: Run integration test**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/integration/test_research_flow.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_research_flow.py
git commit -m "test(research-001): add integration test for full research flow"
```

---

## Task 12: Lint, Full Test Suite, Update Progress

**Files:**
- Modify: `project-management/PROGRESS.md`

- [ ] **Step 1: Run linter on all new code**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff check src/agents/ src/services/task_dispatch.py src/services/research.py src/api/routers/research.py src/api/schemas/research.py src/models/research.py src/models/research_db.py`
Expected: No issues. Fix any that arise.

- [ ] **Step 2: Run formatter check**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ruff format --check src/ tests/`
Expected: No formatting issues. Fix any that arise.

- [ ] **Step 3: Run full test suite with coverage**

Run: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest tests/ -v --cov=src --cov-report=term-missing --tb=short`
Expected: All tests PASS, coverage ≥ 80% on new code

- [ ] **Step 4: Update PROGRESS.md**

Update the RESEARCH-001 row in `project-management/PROGRESS.md`:

| RESEARCH-001 | Agent Orchestrator (LangGraph) | Done | `feature/RESEARCH-001-agent-orchestrator` | [plan](../docs/superpowers/plans/2026-03-17-research-001-agent-orchestrator.md) | [spec](../docs/superpowers/specs/2026-03-17-research-001-agent-orchestrator-design.md) |

Also add stub tracking notes under RESEARCH-002 and RESEARCH-003:

Under RESEARCH-002 row, add note: `Replaces stub_research_agent in src/agents/research/stub.py (from RESEARCH-001)`

Under RESEARCH-003 row, add note: `Replaces stub_research_agent in src/agents/research/stub.py (from RESEARCH-001). Also replaces AsyncIODispatcher with CeleryDispatcher.`

- [ ] **Step 5: Commit progress update**

```bash
git add project-management/PROGRESS.md
git commit -m "docs: update PROGRESS.md — RESEARCH-001 done with stub tracking"
```
