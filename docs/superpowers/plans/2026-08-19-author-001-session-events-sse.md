# AUTHOR-001 — Session Events (SSE progress) + Session Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fake percentage-by-status progress with a real, live, step-and-section-level progress stream for a research/article session, shown on a new `/research/[id]` page that the Generate flow navigates to automatically.

**Architecture:** Pipeline nodes already persist `agent_steps` rows via `_record_step/_complete_step`. We add (a) a contextvar-based `report_progress()` so the draft node can write per-section progress into its running step's `output_data`, (b) a pure `diff_steps()` + async `tail_session()` that turns successive DB snapshots into typed `SessionEvent`s, (c) an SSE endpoint `GET /research/sessions/{id}/events` streaming those events (snapshot first, then diffs, 1 s poll, keepalives), (d) `GET /research/sessions/{id}/article` to jump to the produced article, and (e) a frontend `consumeSse` + `useSessionEvents` + `SessionProgress` + route. DB-tailing makes the producer location irrelevant (works unchanged once INFRA-007 moves the pipeline to a worker) and gives replay-on-connect for free. No Redis.

**Tech Stack:** FastAPI `StreamingResponse`, pydantic, contextvars, pytest + httpx ASGI streaming; Next.js 16 app router, `fetch` + `ReadableStream`, TanStack Query, Vitest + Testing Library.

**Spec:** `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §3, §5.1–5.2, §6, §9 Phase A; `docs/architecture/adrs/ADR-006-supervised-pipeline-events-and-outline-gate.md`.

## Global Constraints

- Functions < 20 lines, files < 200 lines, ≤ 3 params (CLAUDE.md). Use small dataclasses/Pydantic models to bundle params.
- TDD: failing test first. Backend: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest <path> -q -p no:cacheprovider`. Frontend: `cd frontend && npx vitest run <path>`.
- Lint before each commit: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`; frontend `npx eslint <files>`.
- No new session statuses in this ticket (that is AUTHOR-002). Terminal statuses for the stream: `article_complete`, `article_failed`, `failed`, `completed`, `cancelled`; `complete` is terminal only if unchanged for 30 s (content service may be absent).
- Auth: SSE endpoint requires `require_viewer_or_above`; bearer header (frontend uses `fetch`, not `EventSource`).
- Conventional commits, one logical commit per task; branch `feature/AUTHOR-001-pipeline-events`; never stack PRs.

---

### Task 1: `report_progress()` contextvar + draft node per-section progress

**Files:**
- Create: `src/utils/step_progress.py`
- Modify: `src/agents/content/pipeline.py:99-115` (`_wrap_node`)
- Modify: `src/agents/content/nodes.py:107-121` (draft loop)
- Test: `tests/unit/utils/test_step_progress.py`, `tests/unit/agents/content/test_pipeline_progress.py`

**Interfaces:**
- Produces: `current_progress_reporter: ContextVar[ProgressReporter | None]`, `async report_progress(data: dict[str, object]) -> None`, `make_step_reporter(step_repo, step) -> ProgressReporter` (merges `data` into the step's `output_data` and calls `step_repo.update`).
- Draft node writes `{"sections_done": i, "sections_total": n, "current_section": title}` after each section.

- [x] **Step 1: Write failing tests for the reporter**

```python
# tests/unit/utils/test_step_progress.py
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.research_db import AgentStep
from src.utils.step_progress import (
    current_progress_reporter,
    make_step_reporter,
    report_progress,
)


class _Repo:
    def __init__(self) -> None:
        self.updates: list[AgentStep] = []

    async def update(self, step: AgentStep) -> AgentStep:
        self.updates.append(step)
        return step


def _step() -> AgentStep:
    return AgentStep(
        session_id=uuid4(), step_name="content_draft", started_at=datetime.now(UTC)
    )


@pytest.mark.asyncio
async def test_report_progress_noop_without_reporter() -> None:
    current_progress_reporter.set(None)
    await report_progress({"sections_done": 1})  # must not raise


@pytest.mark.asyncio
async def test_step_reporter_merges_output_data() -> None:
    repo = _Repo()
    reporter = make_step_reporter(repo, _step())
    token = current_progress_reporter.set(reporter)
    try:
        await report_progress({"sections_done": 1, "sections_total": 3})
        await report_progress({"sections_done": 2})
    finally:
        current_progress_reporter.reset(token)
    assert repo.updates[-1].output_data == {"sections_done": 2, "sections_total": 3}
    assert repo.updates[-1].status == "running"


@pytest.mark.asyncio
async def test_reporter_swallows_repo_errors() -> None:
    class Boom:
        async def update(self, step: AgentStep) -> AgentStep:
            raise RuntimeError("db down")

    token = current_progress_reporter.set(make_step_reporter(Boom(), _step()))
    try:
        await report_progress({"x": 1})  # must not raise
    finally:
        current_progress_reporter.reset(token)
```

- [x] **Step 2: Run to verify failure**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/utils/test_step_progress.py -q -p no:cacheprovider`
Expected: FAIL — `ModuleNotFoundError: src.utils.step_progress`

- [x] **Step 3: Implement `src/utils/step_progress.py`**

```python
"""Per-step progress reporting for long-running pipeline nodes.

Nodes call ``report_progress({...})``; the active node wrapper binds a
reporter that merges the dict into the running AgentStep's ``output_data``
so the session-events stream (AUTHOR-001) can surface sub-step progress.
"""

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable
from typing import Protocol

import structlog

from src.models.research_db import AgentStep

logger = structlog.get_logger(__name__)

ProgressReporter = Callable[[dict[str, object]], Awaitable[None]]

current_progress_reporter: contextvars.ContextVar[ProgressReporter | None] = (
    contextvars.ContextVar("current_progress_reporter", default=None)
)


class _StepUpdater(Protocol):
    async def update(self, step: AgentStep) -> AgentStep: ...


async def report_progress(data: dict[str, object]) -> None:
    """Publish progress for the current step; silent no-op when unbound."""
    reporter = current_progress_reporter.get()
    if reporter is None:
        return
    try:
        await reporter(data)
    except Exception as exc:  # progress is telemetry — never break the node
        logger.warning("step_progress_report_failed", error=str(exc))


def make_step_reporter(step_repo: _StepUpdater, step: AgentStep) -> ProgressReporter:
    """Build a reporter that merges progress into ``step.output_data``."""
    merged: dict[str, object] = dict(step.output_data)

    async def _report(data: dict[str, object]) -> None:
        merged.update(data)
        await step_repo.update(step.model_copy(update={"output_data": dict(merged)}))

    return _report
```

- [x] **Step 4: Run tests — expect PASS**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/utils/test_step_progress.py -q -p no:cacheprovider`
Expected: 3 passed

- [x] **Step 5: Write failing test for `_wrap_node` binding + draft node progress**

```python
# tests/unit/agents/content/test_pipeline_progress.py
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.agents.content.pipeline import ContentGraphDeps, _wrap_node
from src.models.research_db import AgentStep
from src.utils.step_progress import report_progress


class _StepRepo:
    def __init__(self) -> None:
        self.rows: list[AgentStep] = []

    async def create(self, step: AgentStep) -> AgentStep:
        self.rows.append(step)
        return step

    async def update(self, step: AgentStep) -> AgentStep:
        self.rows.append(step)
        return step

    async def list_by_session(self, session_id):  # type: ignore[no-untyped-def]
        return [r for r in self.rows if r.session_id == session_id]


@pytest.mark.asyncio
async def test_wrap_node_binds_progress_reporter() -> None:
    repo = _StepRepo()
    sid = uuid4()
    deps = ContentGraphDeps(step_repo=repo, session_id=sid)  # type: ignore[arg-type]

    async def node(state):  # type: ignore[no-untyped-def]
        await report_progress({"sections_done": 1, "sections_total": 2})
        return {"status": "draft_complete"}

    wrapped = _wrap_node("draft", node, deps)
    await wrapped({"session_id": sid})
    running = [r for r in repo.rows if r.status == "running" and r.output_data]
    assert running and running[-1].output_data["sections_done"] == 1
    assert repo.rows[-1].status == "complete"


@pytest.mark.asyncio
async def test_wrap_node_unbinds_reporter_after_node() -> None:
    from src.utils.step_progress import current_progress_reporter

    repo = _StepRepo()
    deps = ContentGraphDeps(step_repo=repo, session_id=uuid4())  # type: ignore[arg-type]

    async def node(state):  # type: ignore[no-untyped-def]
        return {}

    await _wrap_node("x", node, deps)({"session_id": deps.session_id})
    assert current_progress_reporter.get() is None
```

- [x] **Step 6: Run to verify failure**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/content/test_pipeline_progress.py -q -p no:cacheprovider`
Expected: FAIL — `running` list empty (reporter never bound)

- [x] **Step 7: Bind the reporter in `_wrap_node`** (`src/agents/content/pipeline.py`)

Replace the body of `wrapped` with:

```python
    async def wrapped(state: ContentState) -> dict:  # type: ignore[type-arg]
        from src.agents.research.orchestrator import _complete_step, _record_step
        from src.utils.step_progress import current_progress_reporter, make_step_reporter

        sid = deps.session_id or state.get("session_id")
        step = await _record_step(deps.step_repo, sid, f"content_{name}")
        token = current_progress_reporter.set(
            make_step_reporter(deps.step_repo, step) if step is not None else None
        )
        try:
            result = await node_fn(state)  # type: ignore[misc]
            await _complete_step(deps.step_repo, step, _extract_output(name, result))
            return result
        except Exception as exc:
            await _complete_step(
                deps.step_repo, step, {"error": str(exc)}, status="failed"
            )
            raise
        finally:
            current_progress_reporter.reset(token)
```

- [x] **Step 8: Report per-section progress in the draft node** (`src/agents/content/nodes.py`)

Change the loop to:

```python
        total = len(outline.sections)
        for i, section in enumerate(outline.sections, start=1):
            sq = _find_queries(queries_list, section.index)
            ctx = DraftingContext(
                retriever=retriever,
                topic_id=str(topic.id),
                llm=llm,
                prior_drafts=list(drafts),
                target_audience=state.get("target_audience"),
                content_tone=state.get("content_tone"),
                preferred_angle=state.get("preferred_angle"),
                keywords=state.get("keywords"),
            )
            draft = await draft_section(section, sq, ctx)
            drafts.append(draft)
            await report_progress(
                {"sections_done": i, "sections_total": total, "current_section": section.title}
            )
```

and add `from src.utils.step_progress import report_progress` to the imports. If `draft_node` exceeds 20 lines, extract `_make_ctx(state, retriever, llm, drafts)`.

- [x] **Step 9: Run tests — expect PASS; run the whole content-agent suite**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/content tests/unit/utils/test_step_progress.py -q -p no:cacheprovider`
Expected: all pass (existing draft-node tests unaffected — `report_progress` is a no-op when unbound).

- [x] **Step 10: Lint + commit**

```bash
uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/
git add src/utils/step_progress.py src/agents/content/pipeline.py src/agents/content/nodes.py tests/unit/utils/test_step_progress.py tests/unit/agents/content/test_pipeline_progress.py
git commit -m "feat(pipeline): per-step progress reporter + per-section draft progress (AUTHOR-001)"
```

---

### Task 2: `SessionEvent` model + pure `diff_steps()` + `tail_session()` async generator

**Files:**
- Create: `src/models/session_events.py`, `src/services/session_events.py`
- Test: `tests/unit/services/test_session_events.py`

**Interfaces:**
- Produces:
  ```python
  class SessionEvent(BaseModel):
      type: Literal["snapshot","status_changed","step_started","step_progress","step_done","step_failed","done","error","keepalive"]
      session_id: UUID
      status: str | None = None
      step: str | None = None
      data: dict[str, object] = {}
      ts: datetime
  def diff_steps(prev: list[AgentStep], curr: list[AgentStep], session_id: UUID) -> list[SessionEvent]
  def is_terminal(status: str) -> bool
  async def tail_session(svc: ResearchService, session_id: UUID, opts: TailOptions) -> AsyncIterator[SessionEvent]
  @dataclass TailOptions: poll_seconds: float = 1.0; keepalive_seconds: float = 15.0; complete_grace_seconds: float = 30.0; max_seconds: float = 1800.0
  ```
- Consumes: `ResearchService.get_session(session_id) -> SessionDetail(session, steps)` (`src/services/research.py:167`).

- [x] **Step 1: Write failing tests**

```python
# tests/unit/services/test_session_events.py
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.research_db import AgentStep
from src.models.session_events import SessionEvent
from src.services.session_events import (
    TailOptions,
    diff_steps,
    is_terminal,
    tail_session,
)

SID = uuid4()


def _step(name: str, status: str = "running", **out) -> AgentStep:  # type: ignore[no-untyped-def]
    return AgentStep(
        session_id=SID, step_name=name, status=status,
        output_data=dict(out), started_at=datetime.now(UTC),
    )


def test_diff_emits_started_for_new_step() -> None:
    ev = diff_steps([], [_step("plan_research")], SID)
    assert [e.type for e in ev] == ["step_started"]
    assert ev[0].step == "plan_research"


def test_diff_emits_progress_when_running_output_changes() -> None:
    a = _step("content_draft", sections_done=1)
    b = a.model_copy(update={"output_data": {"sections_done": 2}})
    ev = diff_steps([a], [b], SID)
    assert [e.type for e in ev] == ["step_progress"]
    assert ev[0].data == {"sections_done": 2}


def test_diff_emits_done_and_failed() -> None:
    a = _step("x"); b = _step("y")
    ev = diff_steps([a, b], [a.model_copy(update={"status": "complete"}),
                             b.model_copy(update={"status": "failed", "output_data": {"error": "boom"}})], SID)
    assert [e.type for e in ev] == ["step_done", "step_failed"]
    assert ev[1].data == {"error": "boom"}


def test_diff_is_keyed_by_step_id_not_name() -> None:
    a = _step("research_facet_1"); b = _step("research_facet_1")
    assert [e.type for e in diff_steps([a], [a, b], SID)] == ["step_started"]


@pytest.mark.parametrize("s,expected", [
    ("article_complete", True), ("article_failed", True), ("failed", True),
    ("cancelled", True), ("completed", True), ("complete", False), ("planning", False),
])
def test_is_terminal(s: str, expected: bool) -> None:
    assert is_terminal(s) is expected


class _Svc:
    """Scripted ResearchService double: each get_session pops the next snapshot."""
    def __init__(self, snapshots):  # type: ignore[no-untyped-def]
        self._snaps = list(snapshots)
    async def get_session(self, session_id):  # type: ignore[no-untyped-def]
        from src.services.research import SessionDetail
        from src.models.research_db import ResearchSession
        status, steps = self._snaps.pop(0) if len(self._snaps) > 1 else self._snaps[0]
        session = ResearchSession(id=session_id, topic_id=uuid4(), topic_title="t",
                                  status=status, started_at=datetime.now(UTC))
        return SessionDetail(session=session, steps=steps)


@pytest.mark.asyncio
async def test_tail_emits_snapshot_then_diffs_then_done() -> None:
    s1 = _step("plan_research")
    svc = _Svc([
        ("planning", [s1]),
        ("researching", [s1.model_copy(update={"status": "complete"}), _step("content_outline")]),
        ("article_complete", [s1.model_copy(update={"status": "complete"}),
                              _step("content_outline", "complete")]),
    ])
    events = [e async for e in tail_session(svc, SID, TailOptions(poll_seconds=0))]
    types = [e.type for e in events]
    assert types[0] == "snapshot"
    assert events[0].data["steps"][0]["step_name"] == "plan_research"
    assert "status_changed" in types and "step_done" in types and "step_started" in types
    assert types[-1] == "done" and events[-1].status == "article_complete"


@pytest.mark.asyncio
async def test_tail_treats_complete_as_terminal_after_grace() -> None:
    svc = _Svc([("complete", [])])
    opts = TailOptions(poll_seconds=0, complete_grace_seconds=0)
    events = [e async for e in tail_session(svc, SID, opts)]
    assert events[-1].type == "done"


@pytest.mark.asyncio
async def test_tail_stops_on_error_when_session_missing() -> None:
    class Missing:
        async def get_session(self, session_id):  # type: ignore[no-untyped-def]
            from src.services.research import NotFoundError
            raise NotFoundError("nope")
    events = [e async for e in tail_session(Missing(), SID, TailOptions(poll_seconds=0))]
    assert [e.type for e in events] == ["error"]
```

(Check `ResearchSession`'s required fields in `src/models/research_db.py` and `NotFoundError`'s module before running; adjust the double accordingly — the test must construct a valid session.)

- [x] **Step 2: Run to verify failure**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/test_session_events.py -q -p no:cacheprovider`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Implement `src/models/session_events.py`**

```python
"""Typed events streamed to the dashboard for a research/article session."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

EventType = Literal[
    "snapshot", "status_changed", "step_started", "step_progress",
    "step_done", "step_failed", "done", "error", "keepalive",
]

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"article_complete", "article_failed", "failed", "cancelled", "completed"}
)


class SessionEvent(BaseModel):
    type: EventType
    session_id: UUID
    status: str | None = None
    step: str | None = None
    data: dict[str, object] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_sse(self) -> str:
        """Serialize as one SSE frame (``event:`` + ``data:`` lines)."""
        return f"event: {self.type}\ndata: {self.model_dump_json()}\n\n"
```

- [x] **Step 4: Implement `src/services/session_events.py`**

```python
"""Turn persisted agent_steps + session status into a live event stream.

DB-tailing (not pub/sub) so it works identically whether the pipeline runs
in-process or in a worker, and replays current state on connect.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from src.models.research_db import AgentStep
from src.models.session_events import TERMINAL_STATUSES, SessionEvent
from src.services.research import NotFoundError, ResearchService


@dataclass(frozen=True)
class TailOptions:
    poll_seconds: float = 1.0
    keepalive_seconds: float = 15.0
    complete_grace_seconds: float = 30.0
    max_seconds: float = 1800.0


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def _ev(kind: str, sid: UUID, step: AgentStep, data: dict[str, object] | None = None) -> SessionEvent:
    return SessionEvent(type=kind, session_id=sid, step=step.step_name,  # type: ignore[arg-type]
                        status=step.status, data=data if data is not None else {})


def diff_steps(prev: list[AgentStep], curr: list[AgentStep], session_id: UUID) -> list[SessionEvent]:
    """Events explaining how ``curr`` differs from ``prev`` (keyed by step id)."""
    before = {s.id: s for s in prev}
    out: list[SessionEvent] = []
    for s in curr:
        old = before.get(s.id)
        if old is None:
            out.append(_ev("step_started", session_id, s))
        elif old.status == "running" and s.status == "running" and old.output_data != s.output_data:
            out.append(_ev("step_progress", session_id, s, s.output_data))
        elif old.status != s.status and s.status == "complete":
            out.append(_ev("step_done", session_id, s, {"duration_ms": s.duration_ms}))
        elif old.status != s.status and s.status == "failed":
            out.append(_ev("step_failed", session_id, s, s.output_data))
    return out


def _snapshot(sid: UUID, status: str, steps: list[AgentStep]) -> SessionEvent:
    rows = [s.model_dump(mode="json", include={"id", "step_name", "status", "started_at",
                                                "completed_at", "duration_ms", "output_data"})
            for s in steps]
    return SessionEvent(type="snapshot", session_id=sid, status=status, data={"steps": rows})


async def tail_session(svc: ResearchService, session_id: UUID, opts: TailOptions) -> AsyncIterator[SessionEvent]:
    """Yield snapshot, then diffs until the session reaches a terminal state."""
    try:
        detail = await svc.get_session(session_id)
    except NotFoundError as exc:
        yield SessionEvent(type="error", session_id=session_id, data={"error": str(exc)})
        return
    status, steps = detail.session.status, list(detail.steps)
    yield _snapshot(session_id, status, steps)
    started = last_change = last_emit = time.monotonic()
    while not is_terminal(status) and time.monotonic() - started < opts.max_seconds:
        if status == "complete" and time.monotonic() - last_change >= opts.complete_grace_seconds:
            break
        await asyncio.sleep(opts.poll_seconds)
        detail = await svc.get_session(session_id)
        events = diff_steps(steps, list(detail.steps), session_id)
        if detail.session.status != status:
            events.insert(0, SessionEvent(type="status_changed", session_id=session_id,
                                          status=detail.session.status))
        status, steps = detail.session.status, list(detail.steps)
        if events:
            last_change = last_emit = time.monotonic()
        elif time.monotonic() - last_emit >= opts.keepalive_seconds:
            events, last_emit = [SessionEvent(type="keepalive", session_id=session_id)], time.monotonic()
        for e in events:
            yield e
    yield SessionEvent(type="done", session_id=session_id, status=status)
```

If `tail_session` exceeds 20 lines after formatting, extract `_poll_once(svc, session_id, state) -> tuple[list[SessionEvent], _State]` with a small `@dataclass _State(status, steps, last_change, last_emit)`.

- [x] **Step 5: Run tests — expect PASS**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/test_session_events.py -q -p no:cacheprovider`
Expected: all pass

- [x] **Step 6: Lint + commit**

```bash
uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/
git add src/models/session_events.py src/services/session_events.py tests/unit/services/test_session_events.py
git commit -m "feat(session-events): SessionEvent model, diff_steps, tail_session (AUTHOR-001)"
```

---

### Task 3: `find_by_session` on the article repository

**Files:**
- Modify: `src/services/content_repositories.py:47-80` (protocol + in-memory)
- Modify: `src/db/repositories.py:573+` (`PgArticleRepository`)
- Test: `tests/unit/services/test_content_repositories_find_by_session.py`

**Interfaces:**
- Produces: `async find_by_session(self, session_id: UUID) -> CanonicalArticle | None` on `ArticleRepository` protocol, `InMemoryArticleRepository`, `PgArticleRepository` (JSONB filter `provenance->>'research_session_id'`).

- [x] **Step 1: Failing test (in-memory)**

```python
# tests/unit/services/test_content_repositories_find_by_session.py
from uuid import uuid4

import pytest

from src.services.content_repositories import InMemoryArticleRepository
from tests.unit.helpers.canonical_article_factory import make_canonical_article  # if absent, see note


@pytest.mark.asyncio
async def test_find_by_session_returns_matching_article() -> None:
    repo = InMemoryArticleRepository()
    sid = uuid4()
    article = make_canonical_article(research_session_id=sid)
    await repo.create(article)
    assert (await repo.find_by_session(sid)) is not None
    assert (await repo.find_by_session(uuid4())) is None
```

Note: grep `tests/` for an existing CanonicalArticle factory (`rg "def make_canonical_article|CanonicalArticle\(" tests/unit | head`). Reuse it; if none exists, build the article inline in the test using the minimal required fields from `src/models/content.py` (title, subtitle, body_markdown, summary, content_type, domain, seo, provenance(research_session_id=sid, primary_model=..., drafting_model=..., embedding_model=...)).

- [x] **Step 2: Run → FAIL (`AttributeError: find_by_session`)**

- [x] **Step 3: Implement**

Protocol + in-memory (`src/services/content_repositories.py`):
```python
    async def find_by_session(self, session_id: UUID) -> CanonicalArticle | None: ...
```
```python
    async def find_by_session(self, session_id: UUID) -> CanonicalArticle | None:
        for a in self._store.values():
            if a.provenance.research_session_id == session_id:
                return a
        return None
```
Pg (`src/db/repositories.py`, inside `PgArticleRepository`, mirroring how `get` maps a row → model):
```python
    async def find_by_session(self, session_id: UUID) -> CanonicalArticle | None:
        async with self._sf() as db:
            stmt = (
                select(CanonicalArticleRow)
                .where(CanonicalArticleRow.provenance["research_session_id"].astext == str(session_id))
                .order_by(CanonicalArticleRow.generated_at.desc())
                .limit(1)
            )
            row = (await db.execute(stmt)).scalar_one_or_none()
            return None if row is None else _row_to_canonical(row)
```
Use whatever row→model helper `get()` already uses (grep `def get` in `PgArticleRepository`).

- [x] **Step 4: Run → PASS; run `tests/unit/services tests/unit/db -q`**

- [x] **Step 5: Lint + commit** — `git commit -m "feat(articles): ArticleRepository.find_by_session (AUTHOR-001)"`

---

### Task 4: SSE endpoint + `GET /research/sessions/{id}/article`

**Files:**
- Create: `src/api/routers/session_events.py`
- Modify: `src/api/main.py:672+` (include router, tag `research`)
- Modify: `src/config/settings.py` (add `session_events_poll_seconds: float = 1.0`, `session_events_keepalive_seconds: float = 15.0`, `session_events_max_seconds: float = 1800.0`)
- Test: `tests/unit/api/test_session_events_endpoint.py`

**Interfaces:**
- `GET /api/v1/research/sessions/{session_id}/events` → `text/event-stream` of `SessionEvent.to_sse()` frames. Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Rate limit `30/minute`. Auth `require_viewer_or_above`. 400 on non-UUID.
- `GET /api/v1/research/sessions/{session_id}/article` → `{"article_id": UUID}` or 404 `{"detail": "No article for session"}`.

- [x] **Step 1: Failing tests** (reuse `research_app`/`research_client` fixtures from `tests/unit/api/test_research_endpoints.py` — import them or copy the fixture body; the app's `research_service` there is in-memory)

```python
# tests/unit/api/test_session_events_endpoint.py
import json
from uuid import uuid4

import httpx
import pytest

from src.config.settings import Settings
from tests.unit.api.conftest import make_auth_header
from tests.unit.api.test_research_endpoints import research_app, research_client, test_topic_id  # noqa: F401


async def _create_session(client: httpx.AsyncClient, headers, topic_id):  # type: ignore[no-untyped-def]
    r = await client.post("/api/v1/research/sessions", json={"topic_id": topic_id}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


@pytest.mark.asyncio
async def test_events_stream_emits_snapshot_first(research_client, auth_settings: Settings, test_topic_id: str):  # type: ignore[no-untyped-def]
    headers = make_auth_header("viewer", auth_settings)
    sid = await _create_session(research_client, make_auth_header("editor", auth_settings), test_topic_id)
    async with research_client.stream("GET", f"/api/v1/research/sessions/{sid}/events", headers=headers) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        first = ""
        async for line in resp.aiter_lines():
            first += line + "\n"
            if line == "":
                break
    assert first.startswith("event: snapshot\n")
    payload = json.loads(first.split("data: ", 1)[1].strip())
    assert payload["session_id"] == sid and "steps" in payload["data"]


@pytest.mark.asyncio
async def test_events_stream_unknown_session_emits_error(research_client, auth_settings):  # type: ignore[no-untyped-def]
    headers = make_auth_header("viewer", auth_settings)
    async with research_client.stream("GET", f"/api/v1/research/sessions/{uuid4()}/events", headers=headers) as resp:
        body = ""
        async for line in resp.aiter_lines():
            body += line + "\n"
            if body.count("\n\n") >= 1:
                break
    assert body.startswith("event: error\n")


@pytest.mark.asyncio
async def test_events_requires_auth(research_client):  # type: ignore[no-untyped-def]
    r = await research_client.get(f"/api/v1/research/sessions/{uuid4()}/events")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_session_article_404_when_missing(research_client, auth_settings):  # type: ignore[no-untyped-def]
    r = await research_client.get(f"/api/v1/research/sessions/{uuid4()}/article",
                                  headers=make_auth_header("viewer", auth_settings))
    assert r.status_code == 404
```

Note: the `research_app` fixture's stub runner finishes the session immediately (status `complete`); with `complete_grace_seconds` the stream would wait 30 s. In the router, read `TailOptions` from `request.app.state.settings` **and** allow the test to override by setting `app.state.settings.session_events_poll_seconds = 0` and adding `session_events_complete_grace_seconds: float = 30.0` to Settings — set it to `0` in the test fixture (`research_app.state.settings.session_events_complete_grace_seconds = 0`). Add a 4th test asserting the stream ends with an `event: done` frame under that override.

- [x] **Step 2: Run → FAIL (404 route not found)**

- [x] **Step 3: Implement router**

```python
"""SSE progress stream + article lookup for a research/article session (AUTHOR-001)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_viewer_or_above
from src.api.rate_limiter import limiter
from src.api.routers.research import _get_research_service_readonly
from src.services.session_events import TailOptions, tail_session

session_events_router = APIRouter()

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def _tail_options(request: Request) -> TailOptions:
    s = request.app.state.settings
    return TailOptions(
        poll_seconds=s.session_events_poll_seconds,
        keepalive_seconds=s.session_events_keepalive_seconds,
        complete_grace_seconds=s.session_events_complete_grace_seconds,
        max_seconds=s.session_events_max_seconds,
    )


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session id") from exc


@limiter.limit("30/minute")
@session_events_router.get("/research/sessions/{session_id}/events")
async def stream_session_events(
    request: Request,
    session_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> StreamingResponse:
    svc = _get_research_service_readonly(request)
    sid = _parse_uuid(session_id)

    async def gen() -> AsyncIterator[str]:
        async for event in tail_session(svc, sid, _tail_options(request)):
            if await request.is_disconnected():
                return
            yield event.to_sse()

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


@limiter.limit("60/minute")
@session_events_router.get("/research/sessions/{session_id}/article")
async def get_session_article(
    request: Request,
    session_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> dict[str, str]:
    repo = getattr(request.app.state, "article_repo", None)
    article = await repo.find_by_session(_parse_uuid(session_id)) if repo else None
    if article is None:
        raise HTTPException(status_code=404, detail="No article for session")
    return {"article_id": str(article.id)}
```

Register in `src/api/main.py` next to the research router:
```python
    app.include_router(session_events_router, prefix=settings.api_v1_prefix, tags=["research"])
```
Add the four settings fields to `Settings` (`src/config/settings.py`) with the defaults above. Ensure `research_app` fixture has `article_repo` (if not set there, the endpoint returns 404 via the `getattr` guard — fine for the test).

- [x] **Step 4: Run → PASS; then `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api -q -p no:cacheprovider`**

- [x] **Step 5: Manual smoke against the running stack** (optional but recommended): `TOKEN=$(...login...)`; `curl -N -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/research/sessions/<id>/events | head -5` shows `event: snapshot`.

- [x] **Step 6: Lint + commit** — `git commit -m "feat(api): SSE session events stream + session article lookup (AUTHOR-001)"`

---

### Task 5: Frontend `consumeSse` + `useSessionEvents`

**Files:**
- Create: `frontend/src/lib/sse/consume-sse.ts`, `frontend/src/lib/sse/consume-sse.test.ts`
- Create: `frontend/src/hooks/use-session-events.ts`, `frontend/src/hooks/use-session-events.test.tsx`
- Modify: `frontend/src/lib/api/research.ts` (add `sessionEventsUrl(id)`, `fetchSessionArticle(id)`)
- Modify: `frontend/src/types/research.ts` (add `SessionEvent`, `SessionStepRow`)

**Interfaces:**
```ts
// types/research.ts
export type SessionEventType = "snapshot"|"status_changed"|"step_started"|"step_progress"|"step_done"|"step_failed"|"done"|"error"|"keepalive";
export interface SessionStepRow { id: string; step_name: string; status: string; started_at: string; completed_at: string|null; duration_ms: number|null; output_data: Record<string, unknown>; }
export interface SessionEvent { type: SessionEventType; session_id: string; status: string|null; step: string|null; data: Record<string, unknown>; ts: string; }
// lib/sse/consume-sse.ts
export interface ConsumeSseOptions { token?: string|null; signal?: AbortSignal; onEvent: (type: string, data: unknown) => void; }
export async function consumeSse(url: string, opts: ConsumeSseOptions): Promise<void>; // resolves when stream ends; rejects on HTTP !ok / network error
// hooks/use-session-events.ts
export interface SessionEventsState { status: SessionStatus|null; steps: SessionStepRow[]; sections: {done:number; total:number; current?:string}|null; connection: "connecting"|"live"|"closed"|"error"; error: string|null; }
export function useSessionEvents(sessionId: string|null): SessionEventsState;
```
Reducer rules: `snapshot` → replace steps/status; `step_started` → append `{id: data.id ?? step+ts, step_name: step, status:"running"}` (backend `_ev` sets `step` and `status`; to carry the step id, extend Task 2's `_ev` to include `data["step_id"] = str(step.id)` — do that in Task 2 if not already); `step_progress` → update matching step's `output_data` and, if `step === "content_draft"`, set `sections`; `step_done/step_failed` → update status; `status_changed/done` → set status; `done` → connection `closed`; `error` → `error`.

- [x] **Step 1: Failing tests for `consumeSse`**

```ts
// frontend/src/lib/sse/consume-sse.test.ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { consumeSse } from "./consume-sse";

function streamOf(chunks: string[]) {
  const enc = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(c) { chunks.forEach((ch) => c.enqueue(enc.encode(ch))); c.close(); },
  });
}

afterEach(() => vi.restoreAllMocks());

describe("consumeSse", () => {
  it("parses events split across chunks and ignores comments", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(streamOf([
      "event: snap", "shot\ndata: {\"a\":1}\n\n: keepalive\n\nevent: done\ndata: {\"b\":2}\n\n",
    ]), { status: 200 })));
    const seen: Array<[string, unknown]> = [];
    await consumeSse("/x", { onEvent: (t, d) => seen.push([t, d]) });
    expect(seen).toEqual([["snapshot", { a: 1 }], ["done", { b: 2 }]]);
  });

  it("sends the bearer token and rejects on non-2xx", async () => {
    const f = vi.fn(async () => new Response("nope", { status: 403 }));
    vi.stubGlobal("fetch", f);
    await expect(consumeSse("/x", { token: "T", onEvent: () => {} })).rejects.toThrow(/403/);
    expect((f.mock.calls[0][1] as RequestInit).headers).toMatchObject({ Authorization: "Bearer T" });
  });

  it("stops when aborted", async () => {
    const ctrl = new AbortController();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new ReadableStream({ start() {} }), { status: 200 })));
    const p = consumeSse("/x", { signal: ctrl.signal, onEvent: () => {} });
    ctrl.abort();
    await expect(p).resolves.toBeUndefined();
  });
});
```

- [x] **Step 2: Run → FAIL** — `cd frontend && npx vitest run src/lib/sse/consume-sse.test.ts`

- [x] **Step 3: Implement `consume-sse.ts`**

```ts
export interface ConsumeSseOptions {
  token?: string | null;
  signal?: AbortSignal;
  onEvent: (type: string, data: unknown) => void;
}

function dispatchFrame(frame: string, onEvent: ConsumeSseOptions["onEvent"]) {
  let type = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith(":") || line === "") continue;
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return;
  const raw = dataLines.join("\n");
  let data: unknown = raw;
  try { data = JSON.parse(raw); } catch { /* plain text payload */ }
  onEvent(type, data);
}

export async function consumeSse(url: string, opts: ConsumeSseOptions): Promise<void> {
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
  const res = await fetch(url, { headers, signal: opts.signal, credentials: "include" });
  if (!res.ok || !res.body) throw new Error(`SSE request failed: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        dispatchFrame(buffer.slice(0, idx), opts.onEvent);
        buffer = buffer.slice(idx + 2);
      }
    }
    if (buffer.trim()) dispatchFrame(buffer, opts.onEvent);
  } catch (err) {
    if ((err as Error).name === "AbortError" || opts.signal?.aborted) return;
    throw err;
  }
}
```
(Normalize `\r\n` → `\n` after decode if the backend ever emits CRLF.) If `consumeSse` exceeds ~20 lines, split the read loop into `pumpFrames(reader, onEvent)`.

- [x] **Step 4: Run → PASS**

- [x] **Step 5: Add API helpers** (`frontend/src/lib/api/research.ts`)

```ts
export function sessionEventsUrl(sessionId: string): string {
  return `${apiClient.defaults.baseURL}/research/sessions/${sessionId}/events`;
}
export async function fetchSessionArticle(sessionId: string): Promise<{ article_id: string } | null> {
  try {
    const { data } = await apiClient.get<{ article_id: string }>(`/research/sessions/${sessionId}/article`);
    return data;
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.status === 404) return null;
    throw e;
  }
}
```
Add the types from the Interfaces block to `types/research.ts`.

- [x] **Step 6: Failing hook test**

```tsx
// frontend/src/hooks/use-session-events.test.tsx
import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const consume = vi.fn();
vi.mock("@/lib/sse/consume-sse", () => ({ consumeSse: (...a: unknown[]) => consume(...a) }));
vi.mock("@/lib/api/client", () => ({ getAccessToken: () => "T", apiClient: { defaults: { baseURL: "http://api/api/v1" } } }));

import { useSessionEvents } from "./use-session-events";

beforeEach(() => consume.mockReset());

describe("useSessionEvents", () => {
  it("applies snapshot, progress and done events", async () => {
    let emit!: (t: string, d: unknown) => void;
    consume.mockImplementation(async (_url: string, o: { onEvent: typeof emit }) => { emit = o.onEvent; await new Promise(() => {}); });
    const { result } = renderHook(() => useSessionEvents("s1"));
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() => emit("snapshot", { type: "snapshot", session_id: "s1", status: "researching", step: null, ts: "", data: { steps: [{ id: "a", step_name: "plan_research", status: "complete", started_at: "", completed_at: null, duration_ms: 5, output_data: {} }] } }));
    expect(result.current.steps).toHaveLength(1);
    act(() => emit("step_started", { type: "step_started", session_id: "s1", status: "running", step: "content_draft", ts: "", data: { step_id: "b" } }));
    act(() => emit("step_progress", { type: "step_progress", session_id: "s1", status: "running", step: "content_draft", ts: "", data: { step_id: "b", sections_done: 2, sections_total: 5, current_section: "Intro" } }));
    expect(result.current.sections).toEqual({ done: 2, total: 5, current: "Intro" });
    act(() => emit("done", { type: "done", session_id: "s1", status: "article_complete", step: null, ts: "", data: {} }));
    expect(result.current.status).toBe("article_complete");
    expect(result.current.connection).toBe("closed");
  });

  it("reports error state when the stream fails", async () => {
    consume.mockRejectedValue(new Error("SSE request failed: 503"));
    const { result } = renderHook(() => useSessionEvents("s1"));
    await waitFor(() => expect(result.current.connection).toBe("error"));
    expect(result.current.error).toMatch(/503/);
  });

  it("does nothing for null session id", () => {
    renderHook(() => useSessionEvents(null));
    expect(consume).not.toHaveBeenCalled();
  });
});
```

- [x] **Step 7: Run → FAIL; implement `use-session-events.ts`** (useReducer + useEffect with AbortController; reconnect with backoff 1s→30s on rejection while not terminal, max 5 attempts, then `connection: "error"`). Keep the reducer in a separate `frontend/src/hooks/session-events-reducer.ts` (pure, unit-testable) if the hook file nears 200 lines.

- [x] **Step 8: Run → PASS; `npx eslint src/lib/sse src/hooks/use-session-events.ts src/hooks/session-events-reducer.ts`**

- [x] **Step 9: Commit** — `git commit -m "feat(frontend): consumeSse + useSessionEvents hook (AUTHOR-001)"`

---

### Task 6: `SessionProgress` component + `/research/[id]` page + step labels

**Files:**
- Create: `frontend/src/components/research/session-progress.tsx`, `.test.tsx`
- Create: `frontend/src/app/(dashboard)/research/[id]/page.tsx`
- Modify: `frontend/src/components/research/session-steps.tsx:5-20` (add labels `content_image_planner: "Plan Visuals"`, `content_image_render: "Render Visuals"`, `content_outline: "Outline"`, `content_queries: "Research Queries"`, `content_draft: "Draft Sections"`, `content_validate: "Validate"`, `content_citations: "Citations"`, `content_humanize: "Humanize"`, `content_seo: "SEO"`; export `stepLabel(name)` if not already exported)

**Interfaces:**
- `SessionProgress({ sessionId }: { sessionId: string })` — renders: header (topic title from `useResearchSession(sessionId)`, status badge via existing `SessionStatusBadge`, elapsed time), connection chip (`live` green dot / `reconnecting` / `offline — polling`), ordered step list (`role="list"`, each `role="listitem"` with `data-status`), per-section progress bar + "Drafting 2 / 5 — Intro" when `sections` present, terminal footer: on `article_complete` → primary button **View article** (calls `fetchSessionArticle`, `router.push(/articles/{id})`); on `*_failed/failed` → red error panel with the failed step's `output_data.error` and a **Back to research** link.
- Uses design tokens from `DESIGN.md` (badges `rounded-full px-2.5 py-0.5 text-xs`, card `rounded-lg border border-neutral-200 bg-white shadow-sm p-6`, primary `bg-primary text-white`). No inline styles except the progress width.

- [x] **Step 1: Failing component tests** (mock `useSessionEvents` and `useResearchSession`; assert: steps render with labels and `data-status`; sections bar text; "View article" appears on `article_complete` and navigates; error panel on `article_failed`; connection chip text for `error`).

```tsx
// frontend/src/components/research/session-progress.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
const events = vi.fn();
vi.mock("@/hooks/use-session-events", () => ({ useSessionEvents: (id: string) => events(id) }));
vi.mock("@/hooks/use-research-sessions", () => ({ useResearchSession: () => ({ data: { topic_title: "OAuth 2.1", status: "generating_article", started_at: new Date().toISOString() } }) }));
vi.mock("@/lib/api/research", () => ({ fetchSessionArticle: vi.fn(async () => ({ article_id: "art-1" })) }));

import { SessionProgress } from "./session-progress";

const base = { status: "generating_article", connection: "live", error: null, sections: null,
  steps: [{ id: "1", step_name: "plan_research", status: "complete", started_at: "", completed_at: null, duration_ms: 10, output_data: {} },
          { id: "2", step_name: "content_draft", status: "running", started_at: "", completed_at: null, duration_ms: null, output_data: {} }] };

describe("SessionProgress", () => {
  it("renders labelled steps with status", () => {
    events.mockReturnValue(base);
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText("Plan Research").closest("[role=listitem]")).toHaveAttribute("data-status", "complete");
    expect(screen.getByText("Draft Sections").closest("[role=listitem]")).toHaveAttribute("data-status", "running");
  });
  it("shows section progress", () => {
    events.mockReturnValue({ ...base, sections: { done: 2, total: 5, current: "Intro" } });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText(/Drafting 2 \/ 5/)).toBeInTheDocument();
  });
  it("offers View article when complete", async () => {
    events.mockReturnValue({ ...base, status: "article_complete", connection: "closed" });
    render(<SessionProgress sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /view article/i }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/articles/art-1"));
  });
  it("shows the failed step error", () => {
    events.mockReturnValue({ ...base, status: "article_failed", steps: [{ ...base.steps[1], status: "failed", output_data: { error: "LLM timeout" } }] });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText(/LLM timeout/)).toBeInTheDocument();
  });
});
```

- [x] **Step 2: Run → FAIL; implement component (split into `session-progress.tsx` + `session-step-list.tsx` + `session-progress-footer.tsx` to stay < 200 lines each)**

- [x] **Step 3: Page** `frontend/src/app/(dashboard)/research/[id]/page.tsx`:
```tsx
"use client";
import { useParams } from "next/navigation";
import { Header } from "@/components/layout/header";
import { SessionProgress } from "@/components/research/session-progress";

export default function ResearchSessionPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="flex flex-col gap-6">
      <Header title="Article generation" description="Live progress for this research session" />
      <SessionProgress sessionId={id} />
    </div>
  );
}
```
(Match the `Header` props used by `research/page.tsx`.) Note: CLAUDE.md says "named exports only" — Next page files are the accepted exception in this repo (see existing pages).

- [x] **Step 4: Run tests → PASS; `npx vitest run src/components/research`; `npx eslint` the new files; `npx tsc --noEmit`**

- [x] **Step 5: Commit** — `git commit -m "feat(frontend): SessionProgress + /research/[id] live page (AUTHOR-001)"`

---

### Task 7: Auto-navigate after Generate + honest session card

**Files:**
- Modify: `frontend/src/app/(dashboard)/topics/page.tsx:110-146` (`handleCreateAndGenerate`, `handleConfirm`)
- Modify: `frontend/src/components/research/session-card.tsx` (`getProgressPercent` + bar)
- Modify: `frontend/src/components/research/session-card.test.tsx` (update expectations)
- Modify: `frontend/src/app/(dashboard)/topics/page.test.tsx` if it exists (assert `router.push`)

- [x] **Step 1: Failing test — topics page navigates to `/research/{id}` after confirm** (mock `createResearchSession` → `{session_id:"s9"}`, mock `useRouter().push`; assert push called with `/research/s9`). Also forward `keywords` and `structural_diagram_mode` in `handleCreateAndGenerate` (the plan notes this drop) — assert the POST body includes them when provided by `CreateTopicData`.

- [x] **Step 2: Implement**: `const router = useRouter();` then in both handlers `const res = await createResearchSession(...); router.push(`/research/${res.session_id}`);` and remove the "Check Research page" toast (keep the failure toast).

- [x] **Step 3: Session card**: replace `getProgressPercent`'s status→% map with: terminal → 100; active → indeterminate (`animate-pulse` bar at `w-1/3`, `aria-busy="true"`, no numeric width); add a **View progress →** link (`<Link href={`/research/${session.session_id}`}>`) for non-terminal sessions and **View article** (via the same `fetchSessionArticle` helper, or link to `/research/{id}` which offers the button) for `article_complete`. Update `session-card.test.tsx` accordingly; remove any assertion on exact `%` widths.

- [x] **Step 4: Run → PASS: `npx vitest run src/components/research src/app`; `npx tsc --noEmit`; `npx eslint` changed files**

- [x] **Step 5: Commit** — `git commit -m "feat(frontend): navigate to live session page after Generate; honest session card progress (AUTHOR-001)"`

---

### Task 8: Docs, full test run, PR

**Files:**
- Modify: `project-management/PROGRESS.md` (AUTHOR-001 row → Done once merged; add cross-cutting note), `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` (§5.1–5.2: note v1 transport = DB tailing, Redis pub/sub deferred; tick Phase A AC items covered), `docs/architecture/adrs/ADR-006-…md` (add "Transport (v1): DB tailing of `agent_steps`; Redis pub/sub is an optional latency upgrade" under Decision Outcome)
- Modify: `CLAUDE.md` "Current Status" (one line: Epic 11 Phase A in progress, AUTHOR-001)

- [x] **Step 1: Full suites**
```bash
COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/ -q -p no:cacheprovider
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/ --ignore-missing-imports
cd frontend && npx vitest run && npx tsc --noEmit && npx eslint src
```
Expected: all green (backend ≥ 1419 + new tests; frontend ≥ 357 + new).

- [x] **Step 2: Live smoke** (stack is running from `docker compose up -d` in the main checkout): rebuild api + frontend from this worktree (`docker compose build api frontend && docker compose up -d api frontend`, verify image timestamps advanced — see memory note on flaky `--no-cache`), log in, Generate on a topic, confirm redirect to `/research/{id}`, steps appear live, section counter advances, "View article" works. Capture one screenshot into the scratchpad (not the repo).

- [x] **Step 3: Docs edits + commit** — `git commit -m "docs: AUTHOR-001 progress, ADR-006 transport note"`

- [x] **Step 4: Push + PR to `develop`**
```bash
git push -u origin feature/AUTHOR-001-pipeline-events
gh pr create --base develop --title "feat(authoring): live session progress stream + session page (AUTHOR-001)" --body "$(cat <<'EOF'
## Summary
- Per-step progress reporter (contextvar) + per-section draft progress written to `agent_steps.output_data`
- `SessionEvent` + `diff_steps`/`tail_session` (DB-tailing; worker-safe, replay on connect)
- `GET /research/sessions/{id}/events` (SSE) + `GET /research/sessions/{id}/article`
- Frontend `consumeSse`, `useSessionEvents`, `SessionProgress`, `/research/[id]` page; Generate now navigates to the live page; session card no longer shows fake percentages
- Docs: Aug 2026 review, Epic 11 program plan, ADR-006/007

Part of Epic 11 Phase A — see `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md`.

## Test plan
- [ ] backend unit suite green, frontend vitest green, tsc/eslint clean
- [ ] live: Generate → redirected → steps stream → View article

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01XtSDk3hNcBfDFPmXYMgUmF
EOF
)"
```

---

## Self-review

- **Spec coverage:** Phase A AC #1 (navigate + live progress within 2 s, no fake % in session-card) → Tasks 1–7. AC #7 (Redis down ⇒ fallback) is moot with DB tailing; the hook's error state + existing polling covers "SSE unavailable". Outline gate / cancel / brief / regenerate / usage are AUTHOR-002..005 (not this ticket).
- **Placeholders:** none — every step has code or an exact command. Two "check before running" notes (ResearchSession required fields; CanonicalArticle factory) are explicit instructions to verify and adapt, not TBDs.
- **Type consistency:** `SessionEvent` fields (`type,session_id,status,step,data,ts`) identical in Task 2 (py), Task 5 (ts). `report_progress`/`make_step_reporter`/`current_progress_reporter` names match across Tasks 1–2. `find_by_session` matches Tasks 3–4. `sessionEventsUrl`/`fetchSessionArticle` match Tasks 5–7. Event `data.step_id` required by the reducer — Task 2's `_ev` must include it (noted in Task 5 interfaces; implement in Task 2: `data = {"step_id": str(step.id), **data}`).
