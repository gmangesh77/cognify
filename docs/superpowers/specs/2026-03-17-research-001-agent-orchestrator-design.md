# RESEARCH-001: Agent Orchestrator (LangGraph) — Design Spec

> **Date**: 2026-03-17
> **Ticket**: RESEARCH-001
> **Status**: Design approved
> **Depends on**: ARCH-001 (CanonicalArticle contracts — merged)
> **Blocks**: RESEARCH-002, RESEARCH-003, RESEARCH-005, CONTENT-001

---

## 1. Overview

Build a LangGraph-based orchestrator that receives a topic, generates a research plan via LLM, dispatches stub research agents in parallel, evaluates completeness, and optionally retries weak facets. This is the foundation for the entire multi-agent research pipeline.

### Scope

**In scope:**
- LangGraph StateGraph with linear-with-conditional-loop topology
- LLM-based research planning (Claude Sonnet via LangChain)
- LLM-based completeness evaluation with heuristic guardrails
- Protocol-based task dispatch (asyncio implementation, Celery-swappable)
- Stub research agents returning realistic-shaped fake data
- Hybrid state persistence: LangGraph checkpointing + SQLAlchemy business models
- API endpoints: create session, get session, list sessions
- Service layer bridging API to orchestrator
- Comprehensive unit tests with FakeLLM

**Out of scope:**
- Real research agents (RESEARCH-002, RESEARCH-003)
- Milvus/vector DB integration (RESEARCH-003)
- Celery + Redis infrastructure
- WebSocket real-time updates (RESEARCH-005)
- PostgresSaver for LangGraph checkpoints
- Real database (SQLAlchemy models use in-memory repositories)
- CanonicalArticle production (CONTENT-001)

### Stubs Introduced

These placeholders will be replaced by downstream tickets:

| Stub | Location | Replaced by |
|------|----------|-------------|
| `stub_research_agent` | `src/agents/research/stub.py` | RESEARCH-002 (Web Search Agent), RESEARCH-003 (RAG Pipeline) |
| `AsyncIODispatcher` | `src/services/task_dispatch.py` | Future Celery integration ticket |
| `InMemoryResearchRepository` | `src/services/research.py` | Future DB migration ticket |
| `MemorySaver` (LangGraph) | `src/agents/research/orchestrator.py` | Future PostgresSaver infra ticket |

---

## 2. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM integration | Real LangChain + ChatAnthropic, FakeLLM in tests | Matches ADR-001; test strategy already defines FakeLLM pattern |
| State persistence | Hybrid: LangGraph checkpointing + SQLAlchemy models | LangGraph handles recovery; our models serve the dashboard API |
| Task dispatch | Protocol-based, asyncio for now | Keeps ticket focused; Celery swap is mechanical later |
| Completeness eval | LLM + heuristic guardrails | LLM judges quality; guardrails prevent cost/loop issues (RISK-003, RISK-006) |
| Graph topology | Linear with conditional loop | Simplest topology satisfying all acceptance criteria |
| API endpoints | Included in this ticket | Enables end-to-end testing and demo |

---

## 3. LangGraph State Schema

### ResearchState (graph state)

```python
class ResearchState(TypedDict):
    topic: TopicInput                                          # Narrowed input (from src/models/research.py)
    research_plan: ResearchPlan | None                         # LLM-generated facets
    dispatched_tasks: list[FacetTask]                          # Tracking per-facet dispatch (full replacement per node)
    findings: Annotated[list[FacetFindings], operator.add]     # Accumulated across rounds via additive reducer
    evaluation: EvaluationResult | None                        # LLM completeness judgment
    round_number: int                                          # Current research round (max 2)
    session_id: UUID                                           # Links to SQLAlchemy ResearchSession
    status: str                                                # planning | researching | evaluating | complete | failed
    error: str | None
```

> **Note (Issue #1 fix):** `TopicInput` is a narrow Pydantic model defined in `src/models/research.py` containing only the fields the orchestrator needs (`id`, `title`, `description`, `domain`). This avoids importing `RankedTopic` from the API schema layer into the agent layer, preserving layered architecture. The API router constructs `TopicInput` from the full topic data before passing to the service.

### Node Return Semantics

LangGraph nodes receive the current state and **return a partial state update dict** — they do not mutate the state object directly. Each node returns only the keys it changes:

```python
# Example: plan_research node returns only the keys it updates
def plan_research(state: ResearchState) -> dict:
    plan = ...  # generate plan
    return {"research_plan": plan, "status": "planning"}
```

**Reducers for accumulation:** The `findings` field uses `Annotated[list[FacetFindings], operator.add]` so that each `dispatch_agents` call **appends** its results to the existing list rather than replacing it. This is critical for the retry path — round 2 findings accumulate alongside round 1 findings.

**Full replacement fields:** `dispatched_tasks` does NOT use a reducer — each `dispatch_agents` call returns the complete current task list (replacing the previous value). This is correct because task statuses are fully reconstructed each round.

### Checkpointer Serialization Note

`MemorySaver` stores state as in-memory Python dicts — Pydantic model instances are preserved as-is since there is no serialization/deserialization boundary. This is sufficient for RESEARCH-001 where the graph runs in-process.

**Migration note for PostgresSaver:** When migrating to `PostgresSaver` (future infra ticket), state is serialized to JSON and deserialized back. Pydantic model fields in the `TypedDict` will deserialize as plain dicts, not model instances. The migration ticket must either: (a) register a custom LangGraph serializer that round-trips Pydantic models, or (b) add validation at node entry points that reconstructs models from dicts. This limitation is documented here to prevent a surprise during migration.

### Supporting Pydantic Models (in `src/models/research.py`)

```python
class TopicInput(BaseModel, frozen=True):
    id: UUID
    title: str
    description: str
    domain: str

class ResearchFacet(BaseModel, frozen=True):
    index: int
    title: str
    description: str
    search_queries: list[str]            # 1-3 queries per facet

class ResearchPlan(BaseModel, frozen=True):
    facets: list[ResearchFacet]          # 3-5 facets
    reasoning: str                       # Why these facets were chosen

class SourceDocument(BaseModel, frozen=True):
    url: str
    title: str
    snippet: str
    retrieved_at: datetime

class FacetFindings(BaseModel, frozen=True):
    facet_index: int
    sources: list[SourceDocument]
    claims: list[str]
    summary: str

class FacetTask(BaseModel, frozen=True):
    facet_index: int
    status: str                          # pending | running | completed | failed
    started_at: datetime | None = None
    completed_at: datetime | None = None

# FacetTask is frozen (immutable). The dispatch_agents node constructs a fresh
# list of FacetTask objects each round and returns it as a full replacement
# (no reducer on dispatched_tasks). Status transitions are modeled by creating
# new FacetTask instances, not mutating existing ones.

class EvaluationResult(BaseModel, frozen=True):
    is_complete: bool
    weak_facets: list[int]               # Indices of facets needing more research
    reasoning: str
```

### SQLAlchemy Models (in `src/models/research_db.py`)

```python
class ResearchSession:
    id: UUID (PK)
    topic_id: UUID
    status: str                          # planning | researching | evaluating | complete | failed
    agent_plan: dict (JSONB)             # Serialized ResearchPlan
    round_count: int
    findings_count: int
    duration_seconds: float | None
    started_at: datetime
    completed_at: datetime | None

class AgentStep:
    id: UUID (PK)
    session_id: UUID (FK → ResearchSession)
    step_name: str                       # plan_research | dispatch_agents | evaluate | finalize
    status: str                          # running | completed | failed
    input_data: dict (JSONB)
    output_data: dict (JSONB)
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None
```

Note: These are defined as SQLAlchemy-style models but backed by in-memory repositories for RESEARCH-001 (same pattern as `InMemoryRefreshTokenRepository` in auth). Real DB migration comes later.

---

## 4. LangGraph Orchestrator

### Graph Topology

```
[START] → plan_research → dispatch_agents → evaluate_completeness → [should_retry?]
                              ↑                                          |
                              |←── retry (weak facets only) ────────── yes
                              |                                          |
                           finalize ←────────────────────────────────── no
                              ↓
                           [END]
```

### Node Definitions

**`plan_research`**
- Calls Claude Sonnet with topic title, description, and domain
- Prompt: generate 3-5 research facets with search queries per facet
- Parses response into `ResearchPlan`
- Persists `AgentStep` record (step_name="plan_research")
- Sets `state.status = "planning"`
- Error: malformed LLM response → retry once, then fail

**`dispatch_agents`**
- Takes facets from plan (or `weak_facets` on retry round)
- Dispatches via `TaskDispatcher.dispatch()` (asyncio.gather for now)
- Each facet runs the agent function (stub for RESEARCH-001)
- Collects results into `state.findings` (appends on retry, doesn't replace)
- Persists `AgentStep` per facet dispatched
- Sets `state.status = "researching"`
- Increments `state.round_number`

**`evaluate_completeness`**
- Calls Claude Sonnet with topic + all collected findings
- Prompt: are findings sufficient? Which facets are weak?
- Returns `EvaluationResult`
- Heuristic guardrails enforced:
  - `round_number >= 2` → force `is_complete = True`
  - Per-round timeout: 5 minutes
  - Facets with zero sources → always marked weak
- Persists `AgentStep` record (step_name="evaluate")
- Sets `state.status = "evaluating"`

**`finalize`**
- Merges all findings into final structured output
- Updates `ResearchSession`: status="complete", duration, findings_count, round_count
- Persists `AgentStep` record (step_name="finalize")
- Sets `state.status = "complete"`
- Does NOT produce CanonicalArticle (that's CONTENT-001)

### Conditional Edges

**`should_retry`** — This is a **routing function** passed to `add_conditional_edges`, NOT a graph node.

```python
graph.add_conditional_edges(
    "evaluate_completeness",
    should_retry,  # routing function
    {"retry": "dispatch_agents", "finalize": "finalize"},
)
```

The `should_retry` function inspects `ResearchState` and returns:
- `"retry"` if `evaluation.is_complete is False` and `round_number < 2`
- `"finalize"` otherwise

> **Note (Issue #4 fix):** LangGraph conditional edges are routing functions, not nodes. They are registered via `add_conditional_edges()` on the source node, not via `add_node()`.

### Checkpointing

- `MemorySaver` for dev/tests (in-memory, no infra needed)
- Configurable via settings to swap to `PostgresSaver` later
- Each node transition is automatically checkpointed by LangGraph

### Error Handling

- Node failure → `state.status = "failed"`, `state.error` populated
- LLM timeout: 30s per call, raises on expiry
- Individual facet timeout: 5 min, returns partial results
- Partial facet failure: surviving results kept, failed facets marked weak for retry

---

## 5. Task Dispatch Protocol

### Protocol Definition

```python
AgentFunction = Callable[[ResearchFacet], Awaitable[FacetFindings]]

class TaskDispatcher(Protocol):
    async def dispatch(
        self, facets: list[ResearchFacet], agent_fn: AgentFunction
    ) -> list[FacetFindings]: ...
```

> **Note (Issue #5 fix):** The dispatcher receives `list[ResearchFacet]` (facet definitions), not `list[FacetTask]` (status-tracking objects). `FacetTask` status tracking is managed by the `dispatch_agents` node, which creates/updates `FacetTask` entries based on dispatch results. This eliminates the impedance mismatch between task-tracking and agent-function signatures.

### AsyncIODispatcher (RESEARCH-001 implementation)

- Uses `asyncio.gather(*tasks, return_exceptions=True)` for parallel execution
- Per-task timeout via `asyncio.wait_for()` (default 300s, configurable)
- Failed tasks return empty `FacetFindings` with `sources=[]`
- Returns all results (successful + empty for failed)

### Stub Research Agent

Lives in `src/agents/research/stub.py`:

```python
async def stub_research_agent(facet: ResearchFacet) -> FacetFindings:
    """Placeholder returning realistic-shaped fake findings.
    Replaced by real agents in RESEARCH-002/RESEARCH-003."""
    await asyncio.sleep(0.1)  # Simulate latency
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

### Celery Swap Path

Future `CeleryDispatcher` implements the same `TaskDispatcher` protocol:
- `dispatch()` enqueues Celery tasks, awaits `AsyncResult`
- Orchestrator code unchanged — just inject different dispatcher via config/DI

---

## 6. API Endpoints

### Router: `src/api/routers/research.py`

**`POST /api/v1/research/sessions`**
- Body: `CreateResearchSessionRequest { topic_id: UUID }`
- Auth: `require_role("admin", "editor")`
- Rate limit: `3/minute`
- Behavior: creates `ResearchSession` record, launches orchestrator via FastAPI `BackgroundTasks`, returns immediately
- The background task wrapper catches all exceptions, updates session status to "failed" with error message, and logs with correlation ID via structlog
- Response (201): `{ session_id: UUID, status: "planning", started_at: datetime }`

> **Note (Issue #3 fix):** Uses FastAPI's `BackgroundTasks` (Starlette task runner) instead of raw `asyncio.create_task`. This provides lifecycle management — tasks run after the response is sent and exceptions are logged by Starlette. Additionally, the orchestrator runner is wrapped to catch exceptions and update session state to "failed", ensuring no silent failures.
>
> **Injection wiring:** The router constructs the `ResearchService` via its factory function (same pattern as `_get_hn_service` in `trends.py`), then passes the already-constructed service instance and `session_id` into the background task closure: `background_tasks.add_task(service.run_and_finalize, session_id, topic)`. The service method `run_and_finalize` wraps the orchestrator call in a try/except that catches all exceptions, updates the session to "failed", and logs with correlation ID via structlog.

**`GET /api/v1/research/sessions/{session_id}`**
- Auth: `require_role("admin", "editor", "viewer")`
- Rate limit: `30/minute`
- Response (200): `ResearchSessionResponse` with session details + agent steps

**`GET /api/v1/research/sessions`**
- Auth: `require_role("admin", "editor", "viewer")`
- Rate limit: `30/minute`
- Query params: `status` (optional filter), `page` (default 1), `size` (default 20)
- Response (200): paginated list of `ResearchSessionSummary`

### Request/Response Schemas (`src/api/schemas/research.py`)

```python
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

---

## 7. Service Layer

### ResearchService (`src/services/research.py`)

```python
@dataclass(frozen=True)
class ResearchRepositories:
    """Bundles research repositories to respect the 3-param constructor limit."""
    sessions: ResearchSessionRepository
    steps: AgentStepRepository
    topics: TopicRepository

class ResearchService:
    def __init__(
        self,
        repos: ResearchRepositories,
        orchestrator: ResearchOrchestrator,
    ) -> None: ...

    async def start_session(self, topic_id: UUID) -> ResearchSession: ...
    async def get_session(self, session_id: UUID) -> ResearchSessionDetail: ...
    async def list_sessions(
        self, status: str | None, page: int, size: int
    ) -> PaginatedResult: ...
```

> **Note (Issue #2 fix):** `ResearchRepositories` dataclass bundles the two repos into one parameter, keeping the constructor at 2 injected dependencies (within the 3-param project limit).

### Repository Protocols

```python
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
```

In-memory implementations for RESEARCH-001 (same pattern as `InMemoryRefreshTokenRepository`).

### ResearchOrchestrator Protocol (`src/agents/research/runner.py`)

```python
class ResearchOrchestrator(Protocol):
    async def run(self, session_id: UUID, topic: TopicInput) -> ResearchState: ...
```

> **Note (Issue #7 + #8 fix):** `orchestrator.py` contains only graph wiring — the `build_graph()` factory function that constructs the `StateGraph`, registers nodes, and compiles. `runner.py` defines the `ResearchOrchestrator` Protocol and a concrete `LangGraphResearchOrchestrator` class that runs the compiled graph and manages session lifecycle (creating/updating `ResearchSession` and `AgentStep` records via injected repositories). This split keeps both files under 200 lines and gives the service layer a clean typed protocol to depend on (no `Any` types, satisfies mypy strict).

---

## 8. File Structure

```
src/
  agents/
    __init__.py                          # (exists)
    research/
      __init__.py
      orchestrator.py                    # LangGraph StateGraph wiring (build_graph factory only, <200 lines)
      runner.py                          # ResearchOrchestrator protocol + implementation (runs graph, manages session lifecycle)
      planner.py                         # LLM-based research plan generation
      evaluator.py                       # LLM-based completeness evaluation
      stub.py                            # Stub research agent (placeholder)
      state.py                           # ResearchState TypedDict only (imports TopicInput from src/models/research.py)
  models/
    research.py                          # Pydantic: ResearchPlan, FacetFindings, etc.
    research_db.py                       # SQLAlchemy-style: ResearchSession, AgentStep
  services/
    research.py                          # ResearchService
    task_dispatch.py                     # TaskDispatcher protocol + AsyncIODispatcher
  api/
    routers/
      research.py                        # POST/GET endpoints
    schemas/
      research.py                        # Request/response models
tests/
  unit/
    agents/
      research/
        test_orchestrator.py
        test_planner.py
        test_evaluator.py
    services/
      test_research_service.py
      test_task_dispatch.py
    api/
      test_research_endpoints.py
    models/
      test_research_models.py
  integration/
    test_research_flow.py               # End-to-end flow with FakeLLM
```

### New Dependencies (`pyproject.toml`)

```
langgraph >= 0.2.0
langchain-core >= 0.3.0
langchain-anthropic >= 0.3.0
```

---

## 9. Testing Strategy

### Unit Tests (FakeLLM, in-memory repos)

**`test_orchestrator.py`**
- Happy path: topic → plan → dispatch → evaluate (complete) → finalize
- Retry path: evaluate (incomplete) → re-dispatch weak facets → evaluate (complete) → finalize
- Max rounds: stops at round 2 even if evaluation says incomplete
- Agent timeout: facet exceeds timeout, partial results kept
- Partial failure: some facets fail, others succeed, failed marked weak
- State transitions: correct status at each node
- Failed run: LLM error sets status="failed" with error message

**`test_planner.py`**
- Produces 3-5 facets from topic
- Each facet has title, description, at least 1 search query
- Handles malformed LLM JSON gracefully

**`test_evaluator.py`**
- Returns is_complete=True when findings sufficient
- Identifies weak facets when coverage thin
- Guardrail: forces complete at round 2
- Guardrail: zero-source facets always marked weak

**`test_task_dispatch.py`**
- Runs tasks in parallel (timing verification)
- Respects per-task timeout
- Returns partial results on partial failure

**`test_research_service.py`**
- start_session creates record and launches orchestrator
- get_session returns session with steps
- list_sessions filters and paginates
- Rejects invalid topic_id (via `TopicRepository` — see Issue #6 note below)

> **Note (Issue #6 fix):** `topic_id` validation uses a `TopicRepository` protocol with an `exists(topic_id) -> bool` method. For RESEARCH-001, an `InMemoryTopicRepository` is pre-seeded with test topic IDs. The service calls `topic_repo.exists(topic_id)` and raises `NotFoundError` if invalid. This keeps validation testable without a real DB.

**`test_research_endpoints.py`**
- POST returns 201 with session_id
- GET returns session with steps
- GET list with pagination and filters
- Auth enforcement: editor/admin create, viewer read-only
- Rate limiting

**`test_research_models.py`**
- Pydantic model construction and serialization
- Edge cases: empty facets, missing fields, boundaries

### Integration Test

**`test_research_flow.py`**
- Full flow: API POST → service → orchestrator → stub agents → session updated
- Uses FakeLLM + in-memory repos
- Validates wiring between all layers

---

## 10. Acceptance Criteria Mapping

| Acceptance Criteria | How Addressed |
|---|---|
| Receives topic, generates research plan (3-5 facets) | `plan_research` node calls LLM, produces `ResearchPlan` with 3-5 facets |
| Spawns research agents in parallel via Celery | `TaskDispatcher` protocol with `AsyncIODispatcher` (asyncio.gather); Celery-swappable |
| Monitors agent progress with timeout (5 min per agent) | `asyncio.wait_for()` with 300s timeout per facet; `FacetTask.status` tracking |
| Evaluates completeness and triggers additional research | `evaluate_completeness` node with LLM + heuristic guardrails; conditional retry edge |
| State persisted in PostgreSQL for recovery | **Partial**: SQLAlchemy models (`ResearchSession`, `AgentStep`) provide business state persistence visible to the API. LangGraph checkpointing uses `MemorySaver` (in-memory) for RESEARCH-001; `PostgresSaver` for full workflow recovery across process restarts is deferred to a future infra ticket. |
