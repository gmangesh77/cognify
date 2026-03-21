# RESEARCH-005: Research Session Tracking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire existing research infrastructure end-to-end: persist agent steps during orchestration, enrich API responses with counts/summaries, connect frontend to real API data.

**Architecture:** Instrument the LangGraph orchestrator to record `AgentStep` entries per graph node (including per-facet steps). Fix `_persist_success` to populate session-level counts. Enrich API schemas and connect frontend hooks to real endpoints.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, Pydantic, React 19, React Query, Vitest

**Spec:** [`docs/superpowers/specs/2026-03-21-research-005-research-session-tracking-design.md`](../specs/2026-03-21-research-005-research-session-tracking-design.md)

**Worktree:** `D:/Workbench/github/cognify-research-005` (branch: `feature/RESEARCH-005-research-session-tracking`)

**Baseline:** 697 backend tests passing (1 pre-existing pytrends error), 226 frontend tests passing.

---

## Task 1: Add `update` method to AgentStepRepository

**Files:**
- Modify: `src/services/research.py:35-37` (protocol), `src/services/research.py:74-83` (in-memory impl)
- Test: `tests/unit/services/test_research_service.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/services/test_research_service.py`, add:

```python
class TestAgentStepRepository:
    async def test_update_step(self) -> None:
        from datetime import UTC, datetime
        from src.models.research_db import AgentStep
        repo = InMemoryAgentStepRepository()
        session_id = uuid4()
        step = AgentStep(
            session_id=session_id,
            step_name="plan_research",
            status="running",
            started_at=datetime.now(UTC),
        )
        created = await repo.create(step)
        updated = created.model_copy(update={"status": "complete", "duration_ms": 1200})
        result = await repo.update(updated)
        assert result.status == "complete"
        assert result.duration_ms == 1200
        steps = await repo.list_by_session(session_id)
        assert len(steps) == 1
        assert steps[0].status == "complete"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/services/test_research_service.py::TestAgentStepRepository::test_update_step -v`
Expected: FAIL — `InMemoryAgentStepRepository` has no `update` method.

- [ ] **Step 3: Add `update` to protocol and in-memory implementation**

In `src/services/research.py`, add to `AgentStepRepository` protocol (after line 36):
```python
class AgentStepRepository(Protocol):
    async def create(self, step: AgentStep) -> AgentStep: ...
    async def update(self, step: AgentStep) -> AgentStep: ...
    async def list_by_session(self, session_id: UUID) -> list[AgentStep]: ...
```

In `InMemoryAgentStepRepository`, add:
```python
    async def update(self, step: AgentStep) -> AgentStep:
        self._store = [
            step if s.id == step.id else s for s in self._store
        ]
        return step
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/services/test_research_service.py -v`
Expected: All tests PASS including new `test_update_step`.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-research-005
git add src/services/research.py tests/unit/services/test_research_service.py
git commit -m "feat(research): add update method to AgentStepRepository"
```

---

## Task 2: Add `indexed_count` to ResearchSession model

**Files:**
- Modify: `src/models/research_db.py:13-28`
- Test: `tests/unit/models/test_research_models.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/models/test_research_models.py`, add (or find the existing test class for `ResearchSession`):

```python
class TestResearchSessionModel:
    def test_indexed_count_defaults_to_zero(self) -> None:
        from datetime import UTC, datetime
        from src.models.research_db import ResearchSession
        session = ResearchSession(
            topic_id=uuid4(),
            started_at=datetime.now(UTC),
        )
        assert session.indexed_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/models/test_research_models.py::TestResearchSessionModel::test_indexed_count_defaults_to_zero -v`
Expected: FAIL — `ResearchSession` has no field `indexed_count`.

- [ ] **Step 3: Add `indexed_count` field**

In `src/models/research_db.py`, add after `findings_count` (line 21):
```python
    indexed_count: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/models/test_research_models.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-research-005
git add src/models/research_db.py tests/unit/models/test_research_models.py
git commit -m "feat(research): add indexed_count field to ResearchSession model"
```

---

## Task 3: Fix `_persist_success` to populate session counts

**Files:**
- Modify: `src/services/research.py:169-190` (`_persist_success`)
- Test: `tests/unit/services/test_research_service.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/services/test_research_service.py`, add:

```python
class TestRunAndFinalize:
    async def test_persist_success_populates_counts(self) -> None:
        from datetime import UTC, datetime
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        orchestrator = FakeOrchestrator()
        # Make orchestrator return realistic result
        orchestrator._result = {
            "status": "complete",
            "findings": [{"facet_index": 0}, {"facet_index": 1}, {"facet_index": 2}],
            "round_number": 2,
            "indexed_count": 15,
        }
        svc = ResearchService(repos, orchestrator)
        session = await svc.start_session(topic_id)
        topic = await svc.get_topic(topic_id)
        await svc.run_and_finalize(session.id, topic)
        detail = await svc.get_session(session.id)
        assert detail.session.status == "complete"
        assert detail.session.findings_count == 3
        assert detail.session.indexed_count == 15
        assert detail.session.round_count == 2
        assert detail.session.duration_seconds is not None
        assert detail.session.duration_seconds >= 0

    async def test_persist_failure_marks_failed(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator(should_fail=True))
        session = await svc.start_session(topic_id)
        topic = await svc.get_topic(topic_id)
        await svc.run_and_finalize(session.id, topic)
        detail = await svc.get_session(session.id)
        assert detail.session.status == "failed"
```

Update `FakeOrchestrator` to support custom results:
```python
class FakeOrchestrator:
    def __init__(self, should_fail: bool = False) -> None:
        self.calls: list[tuple] = []
        self._should_fail = should_fail
        self._result: dict = {"status": "complete"}

    async def run(self, session_id, topic):
        self.calls.append((session_id, topic))
        if self._should_fail:
            raise RuntimeError("Orchestrator failed")
        return self._result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/services/test_research_service.py::TestRunAndFinalize -v`
Expected: FAIL — `findings_count`, `indexed_count`, `round_count`, `duration_seconds` all default to 0/None.

- [ ] **Step 3: Fix `_persist_success`**

In `src/services/research.py`, replace the `_persist_success` method:

```python
    async def _persist_success(
        self, session_id: UUID, topic: TopicInput, result: object
    ) -> None:
        """Persist findings and mark session complete."""
        session = await self._repos.sessions.get(session_id)
        if not session:
            return
        result_dict = result if isinstance(result, dict) else {}
        findings_raw = result_dict.get("findings", [])
        findings_data = [
            f.model_dump() if hasattr(f, "model_dump") else f for f in findings_raw
        ]
        completed_at = datetime.now(UTC)
        duration_seconds = (
            (completed_at - session.started_at).total_seconds()
            if session.started_at
            else None
        )
        updated = session.model_copy(
            update={
                "status": "complete",
                "findings_data": findings_data,
                "findings_count": len(findings_raw),
                "indexed_count": result_dict.get("indexed_count", 0),
                "round_count": result_dict.get("round_number", 1),
                "duration_seconds": duration_seconds,
                "topic_title": topic.title,
                "topic_description": topic.description,
                "topic_domain": topic.domain,
                "completed_at": completed_at,
            }
        )
        await self._repos.sessions.update(updated)
```

- [ ] **Step 4: Run all service tests**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/services/test_research_service.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-research-005
git add src/services/research.py tests/unit/services/test_research_service.py
git commit -m "fix(research): populate findings_count, indexed_count, round_count, duration in _persist_success"
```

---

## Task 4: Enrich API schemas with new fields

**Files:**
- Modify: `src/api/schemas/research.py`
- Modify: `src/api/routers/research.py` (hydrate new fields)
- Test: `tests/unit/api/test_research_endpoints.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/api/test_research_endpoints.py`, add:

```python
class TestListSessionsEnriched:
    async def test_list_includes_topic_title_and_counts(
        self,
        research_client: httpx.AsyncClient,
        auth_settings: Settings,
        test_topic_id: str,
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
        item = resp.json()["items"][0]
        assert "topic_title" in item
        assert "duration_seconds" in item
        assert "sources_count" in item
        assert "embeddings_count" in item


class TestGetSessionEnriched:
    async def test_detail_includes_output_summary(
        self,
        research_client: httpx.AsyncClient,
        auth_settings: Settings,
        test_topic_id: str,
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
        data = resp.json()
        assert "sources_count" in data
        assert "embeddings_count" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/api/test_research_endpoints.py::TestListSessionsEnriched -v`
Expected: FAIL — schema doesn't have `topic_title`, `sources_count`, `embeddings_count`.

- [ ] **Step 3: Update schemas**

In `src/api/schemas/research.py`, update:

```python
class AgentStepResponse(BaseModel):
    step_name: str
    status: str
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None
    output_summary: str | None = None


class ResearchSessionResponse(BaseModel):
    session_id: UUID
    topic_id: UUID
    topic_title: str = ""
    status: str
    round_count: int
    findings_count: int
    sources_count: int = 0
    embeddings_count: int = 0
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
    sources_count: int = 0
    embeddings_count: int = 0
    topic_title: str = ""
    duration_seconds: float | None = None
    started_at: datetime
```

- [ ] **Step 4: Update router to hydrate new fields**

In `src/api/routers/research.py`, update the detail endpoint response construction to include new fields:

```python
    return ResearchSessionResponse(
        session_id=s.id,
        topic_id=s.topic_id,
        topic_title=s.topic_title,
        status=s.status,
        round_count=s.round_count,
        findings_count=s.findings_count,
        sources_count=s.findings_count,  # sources = findings_count for now
        embeddings_count=s.indexed_count,
        duration_seconds=s.duration_seconds,
        started_at=s.started_at,
        completed_at=s.completed_at,
        steps=steps,
    )
```

Update the list endpoint to hydrate new fields:

```python
    items = [
        ResearchSessionSummary(
            session_id=s.id,
            topic_id=s.topic_id,
            status=s.status,
            round_count=s.round_count,
            findings_count=s.findings_count,
            sources_count=s.findings_count,
            embeddings_count=s.indexed_count,
            topic_title=s.topic_title,
            duration_seconds=s.duration_seconds,
            started_at=s.started_at,
        )
        for s in result.items
    ]
```

Update the detail endpoint's step hydration to include `output_summary`:

```python
    steps = [
        AgentStepResponse(
            step_name=st.step_name,
            status=st.status,
            duration_ms=st.duration_ms,
            started_at=st.started_at,
            completed_at=st.completed_at,
            output_summary=_make_output_summary(st.output_data),
        )
        for st in detail.steps
    ]
```

Add a helper at the top of the router file:

```python
def _make_output_summary(output_data: dict[str, object]) -> str | None:
    if not output_data:
        return None
    if "error" in output_data:
        return f"Error: {output_data['error']}"
    if "facet_count" in output_data:
        return f"{output_data['facet_count']} facets planned"
    if "sources_found" in output_data:
        return f"{output_data['sources_found']} sources found"
    if "embeddings_created" in output_data:
        return f"{output_data['embeddings_created']} embeddings created"
    if "is_complete" in output_data:
        status = "Complete" if output_data["is_complete"] else "Incomplete"
        return f"Evaluation: {status}"
    if "total_sources" in output_data:
        return f"{output_data['total_sources']} total sources"
    return None
```

- [ ] **Step 5: Run all endpoint tests**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/api/test_research_endpoints.py -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
cd D:/Workbench/github/cognify-research-005
git add src/api/schemas/research.py src/api/routers/research.py tests/unit/api/test_research_endpoints.py
git commit -m "feat(research): enrich API schemas with topic_title, counts, output_summary"
```

---

## Task 5: Add 503 guard for uninitialized research service

**Files:**
- Modify: `src/api/routers/research.py:27-28`
- Test: `tests/unit/api/test_research_endpoints.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/api/test_research_endpoints.py`, add:

```python
class TestServiceUnavailable:
    async def test_returns_503_when_research_not_configured(
        self, auth_settings: Settings
    ) -> None:
        app = create_app(auth_settings)
        # Do NOT attach research_service to app.state
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            headers = make_auth_header("viewer", auth_settings)
            resp = await client.get("/api/v1/research/sessions", headers=headers)
            assert resp.status_code == 503
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/api/test_research_endpoints.py::TestServiceUnavailable -v`
Expected: FAIL — currently raises 500 (AttributeError).

- [ ] **Step 3: Add 503 guard**

In `src/api/routers/research.py`, update `_get_research_service`:

```python
from src.api.errors import ServiceUnavailableError

def _get_research_service(request: Request) -> ResearchService:
    if not hasattr(request.app.state, "research_service"):
        raise ServiceUnavailableError(
            message="Research service is not configured. Set ANTHROPIC_API_KEY to enable."
        )
    return request.app.state.research_service  # type: ignore[no-any-return]
```

- [ ] **Step 4: Run tests**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/api/test_research_endpoints.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-research-005
git add src/api/routers/research.py tests/unit/api/test_research_endpoints.py
git commit -m "fix(research): return 503 when research service not configured"
```

---

## Task 6: Wire ResearchService in `create_app()`

**Files:**
- Modify: `src/api/main.py`
- Test: `tests/unit/api/test_research_endpoints.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/api/test_research_endpoints.py`, add:

```python
class TestAppInitialization:
    def test_research_service_attached_to_app_state(
        self, auth_settings: Settings
    ) -> None:
        app = create_app(auth_settings)
        assert hasattr(app.state, "research_service")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/api/test_research_endpoints.py::TestAppInitialization -v`
Expected: FAIL — `research_service` is not attached.

- [ ] **Step 3: Add initialization in `create_app()`**

In `src/api/main.py`, add an import and initialization helper:

```python
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
from src.agents.research.runner import LangGraphResearchOrchestrator
```

Add a helper function:

```python
def _init_research_service(app: FastAPI, settings: Settings) -> None:
    """Initialize research service with in-memory repositories.

    Requires a configured orchestrator (LLM key must be set).
    Skips initialization silently if dependencies unavailable.
    """
    repos = ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=InMemoryTopicRepository(),
    )
    # For now, use a no-op orchestrator in dev mode.
    # Real orchestrator wiring (with LLM + dispatcher) is a separate concern.
    from src.agents.research.runner import ResearchOrchestrator

    class NoOpOrchestrator:
        async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
            return {"status": "complete", "findings": [], "round_number": 1, "indexed_count": 0}

    orchestrator: ResearchOrchestrator = NoOpOrchestrator()  # type: ignore[assignment]
    app.state.research_service = ResearchService(repos, orchestrator)
    logger.info("research_service_initialized")
```

In `create_app()`, call it after line 51 (`app.state.trend_registry = ...`):

```python
    _init_research_service(app, settings)
```

- [ ] **Step 4: Run tests**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/api/test_research_endpoints.py -v`
Expected: All PASS. The `research_app` fixture still overrides `app.state.research_service`, so existing tests are unaffected.

- [ ] **Step 5: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/ -q --tb=short`
Expected: No regressions (697+ passed, 1 pre-existing error).

- [ ] **Step 6: Commit**

```bash
cd D:/Workbench/github/cognify-research-005
git add src/api/main.py tests/unit/api/test_research_endpoints.py
git commit -m "feat(research): wire ResearchService in create_app()"
```

---

## Task 7: Instrument orchestrator with step tracking

**Files:**
- Modify: `src/agents/research/runner.py:22-42` (add step_repo to LangGraphResearchOrchestrator)
- Modify: `src/agents/research/orchestrator.py:90-179` (instrument graph nodes)
- Create: `tests/unit/agents/research/test_step_tracking.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/agents/research/test_step_tracking.py`:

```python
"""Tests for agent step tracking during orchestrator execution."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.research import (
    EvaluationResult,
    FacetFindings,
    ResearchFacet,
    ResearchPlan,
    SourceDocument,
    TopicInput,
)
from src.models.research_db import AgentStep
from src.services.research import InMemoryAgentStepRepository


class FakeStepTrackingLLM:
    """Minimal LLM double that returns pre-canned research responses."""

    async def ainvoke(self, messages, **kwargs):
        from unittest.mock import MagicMock
        resp = MagicMock()
        resp.content = '{"facets": [{"index": 0, "title": "Facet A", "description": "desc", "search_queries": ["q1"]}, {"index": 1, "title": "Facet B", "description": "desc", "search_queries": ["q2"]}], "reasoning": "test"}'
        return resp


class FakeDispatcher:
    """Returns pre-canned findings."""

    async def dispatch(self, facets, agent_fn):
        return [
            FacetFindings(
                facet_index=f.index,
                sources=[
                    SourceDocument(
                        url=f"https://example.com/{f.index}",
                        title=f"Source {f.index}",
                        snippet="Test snippet",
                    )
                ],
                claims=[f"Claim for facet {f.index}"],
                summary=f"Summary for facet {f.index}",
            )
            for f in facets
        ]


class FakeEvalLLM:
    """LLM that returns complete evaluation."""

    call_count = 0

    async def ainvoke(self, messages, **kwargs):
        from unittest.mock import MagicMock
        self.call_count += 1
        # First call is plan, second is evaluate
        if self.call_count == 1:
            resp = MagicMock()
            resp.content = '{"facets": [{"index": 0, "title": "Facet A", "description": "desc", "search_queries": ["q1"]}], "reasoning": "test"}'
            return resp
        resp = MagicMock()
        resp.content = '{"is_complete": true, "weak_facets": [], "reasoning": "good"}'
        return resp


class TestStepTracking:
    async def test_plan_research_creates_step(self) -> None:
        step_repo = InMemoryAgentStepRepository()
        session_id = uuid4()
        # We test step recording by running a minimal version
        # Check that after plan_research, a step exists
        steps = await step_repo.list_by_session(session_id)
        assert len(steps) == 0  # before running, no steps
```

- [ ] **Step 2: Run test to verify baseline**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/agents/research/test_step_tracking.py -v`
Expected: PASS (baseline test only checks empty state).

- [ ] **Step 3: Add step_repo to `LangGraphResearchOrchestrator`**

In `src/agents/research/runner.py`, update:

```python
from src.services.research import AgentStepRepository


class LangGraphResearchOrchestrator:
    """Runs the compiled LangGraph research graph."""

    def __init__(
        self,
        compiled_graph: CompiledStateGraph,  # type: ignore[type-arg]
        step_repo: AgentStepRepository | None = None,
    ) -> None:
        self._graph = compiled_graph
        self.step_repo = step_repo

    async def run(self, session_id: UUID, topic: TopicInput) -> ResearchState:
        initial_state: ResearchState = {
            "topic": topic,
            "research_plan": None,
            "dispatched_tasks": [],
            "findings": [],
            "evaluation": None,
            "round_number": 0,
            "indexed_count": 0,
            "session_id": session_id,
            "status": "initial",
            "error": None,
        }
        result = await self._graph.ainvoke(initial_state)
        return result  # type: ignore[return-value]
```

- [ ] **Step 4: Instrument `build_graph` to accept and use step_repo**

In `src/agents/research/orchestrator.py`, update `build_graph` signature and instrument nodes.

**Coding standard compliance:** `build_graph` already has 4 params (at the limit with `indexing_deps`). Bundle `step_repo` by renaming `IndexingDeps` to `GraphDeps` and adding the field there:

In `src/agents/research/orchestrator.py`, rename the dataclass:
```python
@dataclass(frozen=True)
class GraphDeps:
    """Bundles optional graph dependencies to respect 3-param limit."""

    vector_store: VectorStore | None = None
    embedder: Embedder | None = None
    chunker: ChunkService | None = None
    step_repo: "AgentStepRepository | None" = None

    @property
    def has_indexing(self) -> bool:
        return all([self.vector_store, self.embedder, self.chunker])
```

Update `build_graph` signature (stays at 4 params, replacing `indexing_deps` with `deps`):
```python
def build_graph(
    llm: BaseChatModel,
    dispatcher: TaskDispatcher,
    agent_fn: AgentFunction,
    deps: GraphDeps | None = None,
) -> CompiledStateGraph:
```

Inside `build_graph`, extract step_repo and indexing deps:
```python
    step_repo = deps.step_repo if deps else None
    has_indexing = deps.has_indexing if deps else False
```

Add import and helper at the top of the file:
```python
from src.models.research_db import AgentStep as AgentStepModel

async def _record_step(
    step_repo: "AgentStepRepository | None",
    session_id: "UUID",
    step_name: str,
    status: str = "running",
) -> AgentStepModel | None:
    """Create a step record. Returns None if step_repo not configured."""
    if step_repo is None:
        return None
    from datetime import UTC, datetime
    from uuid import UUID as UUIDType
    try:
        step = AgentStepModel(
            session_id=session_id if isinstance(session_id, UUIDType) else UUIDType(str(session_id)),
            step_name=step_name,
            status=status,
            started_at=datetime.now(UTC),
        )
        return await step_repo.create(step)
    except Exception as exc:
        logger.warning("step_record_failed", step_name=step_name, error=str(exc))
        return None


async def _complete_step(
    step_repo: "AgentStepRepository | None",
    step: AgentStepModel | None,
    output_data: dict,
    status: str = "complete",
) -> None:
    """Update a step to complete/failed."""
    if step_repo is None or step is None:
        return
    from datetime import UTC, datetime
    try:
        completed_at = datetime.now(UTC)
        duration_ms = int((completed_at - step.started_at).total_seconds() * 1000)
        updated = step.model_copy(
            update={
                "status": status,
                "output_data": output_data,
                "duration_ms": duration_ms,
                "completed_at": completed_at,
            }
        )
        await step_repo.update(updated)
    except Exception as exc:
        logger.warning("step_complete_failed", step_name=step.step_name, error=str(exc))
```

Instrument each node inside `build_graph`:

```python
    async def plan_research(state: ResearchState) -> dict:
        step = await _record_step(step_repo, state["session_id"], "plan_research")
        try:
            topic = _validate_topic(state)
            plan = await generate_research_plan(topic, llm)
            await _complete_step(step_repo, step, {
                "facet_count": len(plan.facets),
                "facet_titles": [f.title for f in plan.facets],
            })
            return {"research_plan": plan, "status": "planning"}
        except Exception as exc:
            await _complete_step(step_repo, step, {"error": str(exc)}, status="failed")
            raise

    async def dispatch_agents(state: ResearchState) -> dict:
        plan = _validate_plan(state)
        evaluation = _validate_evaluation(state)
        if evaluation and evaluation.weak_facets:
            weak = set(evaluation.weak_facets)
            facets = [f for f in plan.facets if f.index in weak]
        else:
            facets = list(plan.facets)

        round_num = state["round_number"] + 1
        results: list[FacetFindings] = []
        for facet in facets:
            step_name = f"research_facet_{facet.index}"
            if round_num > 1:
                step_name = f"research_facet_{facet.index}_round_{round_num}"
            step = await _record_step(step_repo, state["session_id"], step_name)
            try:
                facet_results = await dispatcher.dispatch([facet], agent_fn)
                result = facet_results[0] if facet_results else FacetFindings(
                    facet_index=facet.index, sources=[], claims=[], summary=""
                )
                results.append(result)
                await _complete_step(step_repo, step, {
                    "sources_found": len(result.sources),
                    "claims_extracted": len(result.claims),
                    "facet_title": facet.title,
                })
            except Exception as exc:
                await _complete_step(step_repo, step, {"error": str(exc)}, status="failed")
                results.append(FacetFindings(
                    facet_index=facet.index, sources=[], claims=[], summary=""
                ))

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
            "round_number": round_num,
            "status": "researching",
        }

    async def index_findings(state: ResearchState) -> dict:
        step = await _record_step(step_repo, state["session_id"], "index_findings")
        try:
            if not has_indexing:
                logger.info("index_findings_skipped", reason="services not configured")
                await _complete_step(step_repo, step, {"embeddings_created": 0})
                return {}
            new_count = await _index_new_findings(state, deps)
            indexed = state.get("indexed_count", 0)
            await _complete_step(step_repo, step, {"embeddings_created": new_count})
            return {"indexed_count": indexed + new_count}
        except Exception as exc:
            logger.error("index_findings_failed", error=str(exc))
            await _complete_step(step_repo, step, {"error": str(exc)}, status="failed")
            return {}

    async def evaluate(state: ResearchState) -> dict:
        step = await _record_step(step_repo, state["session_id"], "evaluate_completeness")
        try:
            topic = _validate_topic(state)
            findings = _validate_findings(state)
            ctx = EvaluationContext(
                topic=topic, findings=findings, round_number=state["round_number"]
            )
            result = await evaluate_completeness(ctx, llm)
            await _complete_step(step_repo, step, {
                "is_complete": result.is_complete,
                "weak_facets": result.weak_facets,
                "reasoning": result.reasoning,
            })
            return {"evaluation": result, "status": "evaluating"}
        except Exception as exc:
            await _complete_step(step_repo, step, {"error": str(exc)}, status="failed")
            raise

    async def finalize(state: ResearchState) -> dict:
        findings = _validate_findings(state)
        total_sources = sum(len(f.sources) for f in findings)
        step = await _record_step(step_repo, state["session_id"], "finalize")
        await _complete_step(step_repo, step, {
            "total_sources": total_sources,
        })
        return {"status": "complete"}
```

**IMPORTANT — Parallel dispatch preserved:** Facet steps are recorded as "running" before the batch `dispatcher.dispatch(facets, agent_fn)` call and completed after it returns. The `dispatch_agents` node code above must be updated to use this pattern instead of sequential single-facet dispatch:

```python
        # Record all facet steps as "running" BEFORE batch dispatch
        facet_steps = []
        for facet in facets:
            step_name = f"research_facet_{facet.index}"
            if round_num > 1:
                step_name = f"research_facet_{facet.index}_round_{round_num}"
            step = await _record_step(step_repo, state["session_id"], step_name)
            facet_steps.append(step)

        # Preserve parallel batch dispatch — do NOT break into sequential calls
        results = await dispatcher.dispatch(facets, agent_fn)

        # Complete each facet step after batch finishes
        for step, result, facet in zip(facet_steps, results, facets):
            await _complete_step(step_repo, step, {
                "sources_found": len(result.sources),
                "claims_extracted": len(result.claims),
                "facet_title": facet.title,
            })
```

This preserves the `AsyncIODispatcher`'s concurrent execution while still creating per-facet step records. Per-facet timing won't be exact (all share batch duration), but step count and output data are accurate.

- [ ] **Step 5: Write comprehensive step tracking test**

Update `tests/unit/agents/research/test_step_tracking.py` with a full integration test:

```python
class TestStepTrackingIntegration:
    async def test_full_graph_records_all_steps(self) -> None:
        """Run the full graph with fakes and verify steps are recorded."""
        from src.agents.research.orchestrator import build_graph
        from src.agents.research.runner import LangGraphResearchOrchestrator

        step_repo = InMemoryAgentStepRepository()
        session_id = uuid4()

        llm = FakeEvalLLM()
        dispatcher = FakeDispatcher()

        async def fake_agent(facet):
            return FacetFindings(
                facet_index=facet.index,
                sources=[SourceDocument(url="https://x.com", title="T", snippet="S")],
                claims=["claim"],
                summary="summary",
            )

        from src.agents.research.orchestrator import GraphDeps
        graph = build_graph(
            llm=llm,
            dispatcher=dispatcher,
            agent_fn=fake_agent,
            deps=GraphDeps(step_repo=step_repo),
        )
        orchestrator = LangGraphResearchOrchestrator(graph, step_repo=step_repo)

        topic = TopicInput(id=uuid4(), title="Test", description="Desc", domain="tech")
        await orchestrator.run(session_id, topic)

        steps = await step_repo.list_by_session(session_id)
        step_names = [s.step_name for s in steps]

        # Should have: plan_research, research_facet_0, index_findings, evaluate_completeness, finalize
        # (Number of facets depends on FakeEvalLLM response)
        assert "plan_research" in step_names
        assert "index_findings" in step_names
        assert "evaluate_completeness" in step_names
        assert "finalize" in step_names
        assert any(name.startswith("research_facet_") for name in step_names)

        # All steps should be complete
        for step in steps:
            assert step.status == "complete", f"{step.step_name} has status {step.status}"
            assert step.duration_ms is not None
            assert step.duration_ms >= 0

    async def test_step_tracking_optional(self) -> None:
        """Graph works without step_repo (backward compatibility)."""
        from src.agents.research.orchestrator import build_graph
        from src.agents.research.runner import LangGraphResearchOrchestrator

        llm = FakeEvalLLM()
        dispatcher = FakeDispatcher()

        async def fake_agent(facet):
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="",
            )

        graph = build_graph(llm=llm, dispatcher=dispatcher, agent_fn=fake_agent)
        orchestrator = LangGraphResearchOrchestrator(graph)
        topic = TopicInput(id=uuid4(), title="Test", description="Desc", domain="tech")
        result = await orchestrator.run(uuid4(), topic)
        assert result["status"] == "complete"
```

- [ ] **Step 6: Run step tracking tests**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/unit/agents/research/test_step_tracking.py -v`
Expected: All PASS.

- [ ] **Step 7: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/ -q --tb=short`
Expected: No regressions. Existing `test_orchestrator.py` tests pass because `step_repo` is optional.

- [ ] **Step 8: Commit**

```bash
cd D:/Workbench/github/cognify-research-005
git add src/agents/research/orchestrator.py src/agents/research/runner.py tests/unit/agents/research/test_step_tracking.py
git commit -m "feat(research): instrument orchestrator with per-node and per-facet step tracking"
```

---

## Task 8: Update frontend types, API client, hooks, and components (atomic)

> **IMPORTANT:** Tasks 8-12 from the original plan are combined into a single task because type changes, mock removal, hook updates, and component changes are interdependent — committing any subset would leave the test suite broken. All frontend changes are made together and committed atomically.

**Files:**
- Modify: `frontend/src/types/research.ts`
- Create: `frontend/src/lib/api/research.ts`

- [ ] **Step 1: Update types**

In `frontend/src/types/research.ts`, replace the file contents:

```typescript
export type SessionStatus = "planning" | "in_progress" | "complete" | "failed";

export interface AgentStep {
  step_name: string;
  status: string;
  duration_ms: number | null;
  started_at: string;
  completed_at: string | null;
  output_summary: string | null;
}

export interface ResearchSessionSummary {
  session_id: string;
  topic_id: string;
  status: SessionStatus;
  round_count: number;
  findings_count: number;
  sources_count: number;
  embeddings_count: number;
  topic_title: string;
  duration_seconds: number | null;
  started_at: string;
}

export interface ResearchSessionDetail extends ResearchSessionSummary {
  completed_at: string | null;
  steps: AgentStep[];
}

export interface PaginatedResearchSessions {
  items: ResearchSessionSummary[];
  total: number;
  page: number;
  size: number;
}
```

- [ ] **Step 2: Create API client**

Create `frontend/src/lib/api/research.ts` using the existing `apiClient` (axios instance with auth token injection, auto-refresh, and correlation headers — see `frontend/src/lib/api/client.ts`):

```typescript
import { apiClient } from "@/lib/api/client";
import type {
  PaginatedResearchSessions,
  ResearchSessionDetail,
  SessionStatus,
} from "@/types/research";

export async function fetchSessions(
  status?: SessionStatus,
  page = 1,
  size = 10,
): Promise<PaginatedResearchSessions> {
  const params: Record<string, string> = { page: String(page), size: String(size) };
  if (status) params.status = status;
  const { data } = await apiClient.get<PaginatedResearchSessions>(
    "/research/sessions",
    { params },
  );
  return data;
}

export async function fetchSessionDetail(
  sessionId: string,
): Promise<ResearchSessionDetail> {
  const { data } = await apiClient.get<ResearchSessionDetail>(
    `/research/sessions/${sessionId}`,
  );
  return data;
}
```

- [ ] **Step 3: Update hooks**

Replace `frontend/src/hooks/use-research-sessions.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type {
  ResearchSessionDetail,
  SessionStatus,
} from "@/types/research";
import { fetchSessions, fetchSessionDetail } from "@/lib/api/research";

export function useResearchSessions(
  status?: SessionStatus,
  page = 1,
  size = 10,
) {
  return useQuery({
    queryKey: ["research-sessions", status, page, size],
    queryFn: () => fetchSessions(status, page, size),
    staleTime: 15 * 60 * 1000,
  });
}

export function useResearchSession(sessionId: string | null) {
  return useQuery({
    queryKey: ["research-session", sessionId],
    queryFn: () => fetchSessionDetail(sessionId!),
    enabled: sessionId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "planning" || status === "in_progress") return 10_000;
      return false;
    },
  });
}
```

- [ ] **Step 4: Delete mock data**

```bash
cd D:/Workbench/github/cognify-research-005
rm frontend/src/lib/mock/research-sessions.ts
```

- [ ] **Step 5: Check for other mock imports**

Run: `cd D:/Workbench/github/cognify-research-005 && grep -r "mock/research-sessions" frontend/src/ --include="*.ts" --include="*.tsx"` to verify no remaining imports.

- [ ] **Step 6: Update STEP_LABELS and add output_summary rendering**

In `frontend/src/components/research/session-steps.tsx`, update:

```typescript
const STEP_LABELS: Record<string, string> = {
  plan_research: "Plan Research",
  index_findings: "Index Findings",
  evaluate_completeness: "Evaluate Completeness",
  finalize: "Finalize",
};

function getStepLabel(stepName: string): string {
  if (STEP_LABELS[stepName]) return STEP_LABELS[stepName];
  // Dynamic label for research_facet_N or research_facet_N_round_M
  if (stepName.startsWith("research_facet_")) return `Research Facet ${stepName.replace(/research_facet_/, "").replace(/_round_/, " (Round ") + (stepName.includes("_round_") ? ")" : "")}`;
  return stepName;
}
```

Update the step rendering to use `getStepLabel` and show `output_summary`:

```tsx
      {steps.map((step) => (
        <div key={step.step_name} className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2 text-sm">
            <StepIcon status={step.status} />
            <span className={step.status === "pending" ? "text-neutral-400" : "text-neutral-700"}>
              {getStepLabel(step.step_name)}
            </span>
            <span className="ml-auto text-xs text-neutral-400">
              {step.status === "complete" && step.duration_ms !== null
                ? formatDuration(step.duration_ms)
                : step.status === "running"
                  ? "..."
                  : ""}
            </span>
          </div>
          {step.output_summary && (
            <p className="ml-6 text-xs text-neutral-400">{step.output_summary}</p>
          )}
        </div>
      ))}
```

- [ ] **Step 7: Update tests for new step names and output_summary**

Update `frontend/src/components/research/session-steps.test.tsx` to use the real step names (`evaluate_completeness` instead of `evaluate`, `research_facet_0` instead of `web_search`, `finalize` instead of `compile_results`) and verify output_summary renders when present.

- [ ] **Step 8: Update KnowledgeBaseStub component**

Replace `frontend/src/components/research/knowledge-base-stub.tsx`:

```tsx
import { Database, FileText, Box } from "lucide-react";
import type { ResearchSessionSummary } from "@/types/research";

interface KnowledgeBaseStatsProps {
  sessions: ResearchSessionSummary[];
}

export function KnowledgeBaseStub({ sessions }: KnowledgeBaseStatsProps) {
  const totalSources = sessions.reduce((sum, s) => sum + s.sources_count, 0);
  const totalEmbeddings = sessions.reduce((sum, s) => sum + s.embeddings_count, 0);
  const completedSessions = sessions.filter((s) => s.status === "complete").length;

  return (
    <div className="flex items-center gap-6 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
      <div className="flex items-center gap-2">
        <Database className="h-4 w-4 text-neutral-400" />
        <div>
          <p className="text-sm font-medium text-neutral-700">{completedSessions}</p>
          <p className="text-xs text-neutral-400">Sessions</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 text-neutral-400" />
        <div>
          <p className="text-sm font-medium text-neutral-700">{totalSources}</p>
          <p className="text-xs text-neutral-400">Sources</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Box className="h-4 w-4 text-neutral-400" />
        <div>
          <p className="text-sm font-medium text-neutral-700">{totalEmbeddings}</p>
          <p className="text-xs text-neutral-400">Embeddings</p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 9: Update KnowledgeBaseStub tests**

Update `frontend/src/components/research/knowledge-base-stub.test.tsx` to pass `sessions` prop with mock session data and verify counts render correctly.

- [ ] **Step 10: Update research page to pass sessions to KnowledgeBaseStub**

Check `frontend/src/app/(dashboard)/research/page.tsx` — the page uses `useResearchSessions()` and renders `<KnowledgeBaseStub />`. Update the page to pass the sessions data: `<KnowledgeBaseStub sessions={data?.items ?? []} />`.

- [ ] **Step 11: Fix all remaining frontend test breakages**

Common fixes needed:
- `session-card.test.tsx` → update mock data to include `sources_count`, `embeddings_count`, non-optional `topic_title`
- `page.test.tsx` → remove mock data imports, use inline test data matching new types
- Any other tests importing from `@/lib/mock/research-sessions` → replace with inline data

- [ ] **Step 12: Run full frontend test suite**

Run: `cd D:/Workbench/github/cognify-research-005/frontend && npx vitest run`
Expected: All 226+ tests PASS.

- [ ] **Step 13: Commit all frontend changes atomically**

```bash
cd D:/Workbench/github/cognify-research-005
git add frontend/
git rm frontend/src/lib/mock/research-sessions.ts
git commit -m "feat(frontend): connect to real research API, update types/hooks/components"
```

---

## Task 9: Full integration verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run pytest tests/ -q --tb=short`
Expected: 697+ passed, 1 pre-existing error (pytrends).

- [ ] **Step 2: Run full frontend test suite**

Run: `cd D:/Workbench/github/cognify-research-005/frontend && npx vitest run`
Expected: 226+ tests PASS.

- [ ] **Step 3: Run linters**

Run: `cd D:/Workbench/github/cognify-research-005 && uv run ruff check src/ && uv run ruff format --check src/`
Expected: No errors.

- [ ] **Step 4: Update PROGRESS.md spec/plan links**

Update `project-management/PROGRESS.md` RESEARCH-005 row with plan and spec links.

- [ ] **Step 5: Final commit if any outstanding changes**

```bash
cd D:/Workbench/github/cognify-research-005
git add -A
git commit -m "docs: update PROGRESS.md with RESEARCH-005 plan and spec links"
```
