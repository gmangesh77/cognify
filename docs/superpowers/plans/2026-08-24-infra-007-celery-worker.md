# INFRA-007 — Celery Pipeline Dispatch + Worker Wiring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Article generation can run on the Celery worker container instead of the API event loop (opt-in via `COGNIFY_TASK_DISPATCH=celery`, default unchanged), so a stuck generation can never freeze the API again.

**Architecture:** A new `PipelineDispatcher` seam replaces the two direct `registry.spawn(...)` calls (session create in `research.py`, outline approve in `outline.py`). `InProcessDispatcher` wraps the existing `SessionTaskRegistry` (byte-identical behaviour, default). `CeleryDispatcher` enqueues `src/tasks/pipeline_tasks.py` tasks with `task_id=str(session_id)` (so cancel = revoke by session id) over a Redis broker. The worker rebuilds the service graph through a new `src/services/bootstrap.py` factory extracted from `_lifespan` — including API-key resolution and the LlmConfig overlay, so worker runs use the same keys/models as the API. Cancellation in worker mode is cooperative: the content graph and pipeline driver check the session status in the DB and stop on `cancelled`. SSE needs no change (DB-tailing); a Celery `on_failure` hook writes `article_failed` so streams terminate when a worker dies.

**Explicitly in scope:** `Dockerfile.worker` gets the HF model pre-bake + offline env (without it the freeze this ticket exists to kill just moves into the worker) and docker-compose mounts `generated_assets` into the worker (without it worker-rendered images 404 from the API).

**Not in scope (say so in the PR):** `is_running` introspection for Celery mode (the `generating_article` status write already closes the double-approve race); a job-status store (review §6 #18, pair later); moving `outline/regenerate`'s synchronous LLM call off the request path; per-facet `TaskDispatcher` in `src/services/task_dispatch.py` — that protocol dispatches in-memory callables and is NOT this ticket's seam despite the old "CeleryDispatcher" name in PROGRESS.md's RESEARCH-era notes.

**Tech Stack:** Celery 5.x + redis-py over the existing `redis:7` compose service; FastAPI; pytest with the existing `research_app` / `_make_outline_app` fixture patterns.

**Spec:** `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §3 (line 36), §9 Phase A row INFRA-007 ("`CeleryDispatcher` + worker wiring for `_run_full_pipeline`; DB-tailing works unchanged from a worker", 5 SP, depends AUTHOR-001); `docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md` §5 "Background work" row + §7 ("Do the Celery/threadpool offload alongside Phase A").

## Global Constraints

- All functions < 20 lines, all files < 200 lines (prod code), max 3 params. `src/api/main.py` (803) and `src/api/routers/research.py` (246) are pre-existing violations — do not grow them; the bootstrap extraction must shrink `main.py`.
- `src/config/settings.py` is at 183/200 — the new settings block must stay ≤ ~12 lines including comments.
- No `Any` types; mypy strict — add a `celery.*` ignore override in `pyproject.toml` `[tool.mypy]` section (celery ships no complete stubs).
- L-001: any Pydantic model crossing the broker goes through `model_dump(mode="json")`.
- Serialization boundary: Celery task args are only `str`/`dict` (session id as `str(UUID)`, topic as `TopicInput.model_dump(mode="json")`).
- Default behaviour MUST be byte-identical: `task_dispatch="inprocess"` keeps `SessionTaskRegistry` semantics, all 1653 existing backend tests pass unmodified except where a test explicitly targets the seam.
- Run backend tests with no `.env` in the worktree (Milvus import-hang gotcha). If you copy `.env` in for a docker smoke, delete it afterwards.
- TDD red/green per step; commit per task.

---

### Task 1: Settings + dependencies + mypy override

**Files:**
- Modify: `pyproject.toml` (add `celery>=5.4`, `redis>=5.0` to `[project].dependencies`; add mypy override)
- Modify: `src/config/settings.py` (~line 179, after `require_outline_approval`)
- Test: `tests/unit/config/test_settings_dispatch.py` (create; `tests/unit/config/` may need creating — check for an existing settings test dir first and co-locate)

**Interfaces:**
- Produces (used by Tasks 2–6):
  - `Settings.task_dispatch: str = "inprocess"` (env `COGNIFY_TASK_DISPATCH`; values `"inprocess" | "celery"`)
  - `Settings.redis_url: str = "redis://localhost:6379/0"` (env `COGNIFY_REDIS_URL`)
  - `Settings.celery_broker_url: str = ""` and `Settings.celery_result_backend: str = ""` — empty string means "use `redis_url`"

- [ ] **Step 1: Write the failing test**

```python
"""Settings for task dispatch (INFRA-007)."""

from src.config.settings import Settings


class TestDispatchSettings:
    def test_defaults_preserve_inprocess_behaviour(self) -> None:
        s = Settings(_env_file=None)
        assert s.task_dispatch == "inprocess"
        assert s.redis_url == "redis://localhost:6379/0"
        assert s.celery_broker_url == ""
        assert s.celery_result_backend == ""

    def test_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("COGNIFY_TASK_DISPATCH", "celery")
        monkeypatch.setenv("COGNIFY_REDIS_URL", "redis://redis:6379/0")
        s = Settings(_env_file=None)
        assert s.task_dispatch == "celery"
        assert s.redis_url == "redis://redis:6379/0"
```

- [ ] **Step 2: Run it — FAIL** (`uv run pytest tests/unit/config/test_settings_dispatch.py -q` → AttributeError)

- [ ] **Step 3: Implement**

Append to `src/config/settings.py` after the `require_outline_approval` block (compact style like the `session_events_*` block):

```python
    # Task dispatch (INFRA-007) — "inprocess" runs pipelines on the API
    # event loop (today's behaviour); "celery" enqueues to the worker.
    task_dispatch: str = "inprocess"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""  # empty = use redis_url
    celery_result_backend: str = ""  # empty = use redis_url
```

In `pyproject.toml`: add `"celery>=5.4"` and `"redis>=5.0"` to `[project].dependencies`; under the mypy config add:

```toml
[[tool.mypy.overrides]]
module = "celery.*"
ignore_missing_imports = true
```

Run `uv sync --dev` (locks celery+redis) — check `uv.lock` diff is committed.

- [ ] **Step 4: Run tests — PASS**; `uv run ruff check src/config/settings.py` clean; settings.py still ≤ 200 lines (`(Get-Content src/config/settings.py).Count`).

- [ ] **Step 5: Commit** — `feat(config): task dispatch + redis/celery settings (INFRA-007 Task 1)` (include `pyproject.toml`, `uv.lock`).

---

### Task 2: Bootstrap factory — extract worker-reusable service construction from `_lifespan`

**Files:**
- Create: `src/services/bootstrap.py` (< 200 lines)
- Modify: `src/api/main.py` `_lifespan` DB branch (~lines 181–344) to call the factory (net shrink)
- Test: `tests/unit/services/test_bootstrap.py`

**Interfaces:**
- Consumes: everything `_lifespan` uses today — `create_db_engine`/`get_session_factory` (`src/db/engine.py`), the Pg repositories, `_build_llm(settings, llm_call_repo)` (main.py:427), `_build_real_orchestrator(settings, step_repo, llm_call_repo)` (main.py:446), `ContentDeps`/`ContentRepositories` (`src/services/content_repositories.py`), `ContentService` (`src/services/content/__init__.py:64`), `OutlineGateService` (`src/services/content/outline_gate.py:31`), `ApiKeyResolver` (`src/utils/key_resolver.py`), the LlmConfig overlay logic (main.py:318-344).
- Produces (used by Task 5 worker and by `_lifespan`):

```python
@dataclass(frozen=True)
class PipelineServices:
    settings: Settings          # post key-resolution + LlmConfig overlay
    session_factory: async_sessionmaker[AsyncSession]
    research_service: ResearchService
    content_service: ContentService | None
    outline_gate: OutlineGateService | None
    llm_call_repo: PgLlmCallRepository
    step_repo: PgAgentStepRepository
    content_repos: ContentRepositories
    article_repo: PgArticleRepository

async def resolve_runtime_settings(settings: Settings, sf: async_sessionmaker) -> Settings
    # ApiKeyResolver.resolve_all() (DB keys override .env) + LlmConfig overlay
    # (UI-selected image provider/model). Returns a NEW Settings; never mutates.

async def build_pipeline_services(settings: Settings, sf: async_sessionmaker) -> PipelineServices
    # settings here is ALREADY resolved. Builds repos → orchestrator →
    # ResearchService → ContentDeps(llm, retriever) → ContentService →
    # OutlineGateService. Content pieces are None when no anthropic key
    # (mirrors today's NoOp fallback).
```

**How to extract safely:** this is a *move*, not a rewrite. Lift the existing code blocks from `_lifespan` (steps: engine→sf is left in the caller; repos, orchestrator rebuild, content deps, content service, outline gate, key-resolution rebuild, LlmConfig overlay) into the two functions, preserving order and log events. `_lifespan` then does: `sf = ...` → `resolved = await resolve_runtime_settings(settings, sf)` → `app.state.settings = resolved` → `ps = await build_pipeline_services(resolved, sf)` → assign `app.state.research_service / content_service / outline_gate / llm_call_repo / content_repos / article_repo / drafting_llm` from `ps` — then continue with the parts bootstrap does NOT own (publishing, trends, topic persistence, settings repos, static files) exactly as today. `_build_llm`, `_build_real_orchestrator`, `_try_build_retriever`'s app-free variant (`_get_or_create_embedding_service_from_settings`, main.py:518) move INTO bootstrap.py (main.py imports them back from there if still referenced). Note `_try_build_retriever(app, settings)` takes `app` only to cache the embedding service — in bootstrap, build the retriever with the settings-only embedding path and keep a module-level cache.

**Watch out:** the retriever build connects to Milvus (can hang when Milvus is down and an anthropic key is set — the known test gotcha). Keep the try/except-log-None wrapper exactly as it is today.

- [ ] **Step 1: Write the failing test**

```python
"""Bootstrap factory (INFRA-007) — worker-reusable service construction."""

import pytest

from src.config.settings import Settings
from src.services.bootstrap import PipelineServices, build_pipeline_services


class _FakeSessionFactory:  # sentinel; repos accept any sessionmaker-shaped object
    pass


@pytest.mark.asyncio
async def test_no_anthropic_key_yields_noop_content_side() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="")
    ps = await build_pipeline_services(settings, _FakeSessionFactory())  # type: ignore[arg-type]
    assert isinstance(ps, PipelineServices)
    assert ps.research_service is not None
    assert ps.content_service is None          # mirrors today's NoOp fallback
    assert ps.outline_gate is None
    assert ps.settings is settings


@pytest.mark.asyncio
async def test_repos_are_bound_to_the_given_session_factory() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="")
    sf = _FakeSessionFactory()
    ps = await build_pipeline_services(settings, sf)  # type: ignore[arg-type]
    assert ps.llm_call_repo._sf is sf  # PgLlmCallRepository stores the factory
```

(Adapt the private-attribute assertion to `PgLlmCallRepository`'s real attribute name — read `src/db/llm_call_repository.py:17` first; if it's `self._session_factory`, assert that. The point is: no hidden global engine.)

- [ ] **Step 2: Run — FAIL** (module missing)
- [ ] **Step 3: Implement `bootstrap.py` + rewire `_lifespan`** as described above. Keep `resolve_runtime_settings` out of the no-key test path (it needs DB reads; the two tests above only exercise `build_pipeline_services` with a fake factory — construction must not touch the DB until first use, which is true today since repos store the factory lazily).
- [ ] **Step 4: Run the FULL backend suite** — `uv run pytest tests/unit/ -q`. This is the regression gate for the extraction; everything must stay green (1653+2). Also `uv run ruff check src/ tests/ && uv run mypy src/services/bootstrap.py src/api/main.py --ignore-missing-imports` (no NEW errors vs develop — main.py has pre-existing ones).
- [ ] **Step 5: Commit** — `refactor(api): extract pipeline service bootstrap from _lifespan (INFRA-007 Task 2)`.

---

### Task 3: `PipelineDispatcher` seam + `InProcessDispatcher` (default, behaviour-preserving)

**Files:**
- Create: `src/services/pipeline_dispatch.py` (< 200 lines)
- Modify: `src/api/routers/research.py` `_spawn_pipeline`/`_get_session_tasks` (~lines 147–168)
- Modify: `src/api/routers/outline.py` approve (~line 159) + cancel (~line 185)
- Modify: `src/api/main.py` (create dispatcher in `_lifespan`, `app.state.pipeline_dispatcher`)
- Test: `tests/unit/services/test_pipeline_dispatch.py`

**Interfaces:**
- Consumes: `SessionTaskRegistry` (`src/services/session_tasks.py`), `PipelineDeps`, `_run_full_pipeline(deps, session_id, topic)`, `_run_drafting_pipeline(deps, session_id)` (`src/api/routers/research_pipeline.py:31-85`), `TopicInput`.
- Produces (used by Task 4/5 and the routers):

```python
class PipelineDispatcher(Protocol):
    def dispatch_full_pipeline(self, session_id: UUID, topic: TopicInput) -> None: ...
    def dispatch_drafting(self, session_id: UUID) -> None: ...
    def cancel(self, session_id: UUID) -> bool: ...


class InProcessDispatcher:
    """Today's behaviour: asyncio task per session via SessionTaskRegistry."""

    def __init__(self, deps: PipelineDeps, registry: SessionTaskRegistry) -> None: ...
    # dispatch_full_pipeline → self._registry.spawn(session_id, _run_full_pipeline(self._deps, session_id, topic))
    # dispatch_drafting     → self._registry.spawn(session_id, _run_drafting_pipeline(self._deps, session_id))
    # cancel                → self._registry.cancel(session_id)
```

Move `_run_full_pipeline`/`_run_drafting_pipeline`/`PipelineDeps` OUT of `src/api/routers/research_pipeline.py` into `src/services/pipeline_runner.py` (rename module move — routers must not be imported by the worker; `src/tasks/` importing `src.api.routers.*` would drag FastAPI request machinery into the worker). Keep a thin re-export in `research_pipeline.py` if other imports exist (grep first: `grep -rn "research_pipeline import" src/ tests/`).

**Router changes (minimal):**
- `research.py`: `_spawn_pipeline(request, session, topic)` body becomes `request.app.state.pipeline_dispatcher.dispatch_full_pipeline(session.id, topic)`. Keep `_get_session_tasks` for the lazy-fallback only if the dispatcher is absent (build an `InProcessDispatcher` on the fly, mirroring today's lazy registry).
- `outline.py` approve: replace `registry.spawn(...)` + RuntimeError→409 with `dispatcher.dispatch_drafting(sid)`; `InProcessDispatcher.dispatch_drafting` must re-raise the registry's `RuntimeError` so the existing 409 mapping stays (keep the try/except in the router).
- `outline.py` cancel: `dispatcher.cancel(sid)` then the existing status write (order unchanged).
- `main.py` `_lifespan`: after Task 2's `ps` assignment — `deps = PipelineDeps(research_svc=ps.research_service, content_svc=ps.content_service, outline_gate=ps.outline_gate)`; `app.state.pipeline_dispatcher = InProcessDispatcher(deps, app.state.session_tasks)` (Task 4 adds the celery branch).

- [ ] **Step 1: Write failing dispatcher tests** (mirror `tests/unit/services/test_session_tasks.py` style)

```python
"""PipelineDispatcher seam (INFRA-007)."""

import asyncio
from uuid import uuid4

import pytest

from src.services.pipeline_dispatch import InProcessDispatcher
from src.services.session_tasks import SessionTaskRegistry


class _RecordingDeps:
    """Stands in for PipelineDeps — dispatcher never introspects it."""


@pytest.mark.asyncio
async def test_dispatch_full_pipeline_spawns_named_task(monkeypatch) -> None:
    ran = asyncio.Event()

    async def fake_runner(deps, session_id, topic) -> None:
        ran.set()

    monkeypatch.setattr(
        "src.services.pipeline_dispatch._run_full_pipeline", fake_runner
    )
    registry = SessionTaskRegistry()
    d = InProcessDispatcher(_RecordingDeps(), registry)  # type: ignore[arg-type]
    sid = uuid4()
    d.dispatch_full_pipeline(sid, topic=None)  # type: ignore[arg-type]
    await asyncio.wait_for(ran.wait(), timeout=2)


@pytest.mark.asyncio
async def test_cancel_delegates_to_registry(monkeypatch) -> None:
    async def hang(deps, session_id) -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr(
        "src.services.pipeline_dispatch._run_drafting_pipeline", hang
    )
    registry = SessionTaskRegistry()
    d = InProcessDispatcher(_RecordingDeps(), registry)  # type: ignore[arg-type]
    sid = uuid4()
    d.dispatch_drafting(sid)
    await asyncio.sleep(0.05)
    assert d.cancel(sid) is True
    await asyncio.sleep(0.05)
    assert registry.is_running(sid) is False


@pytest.mark.asyncio
async def test_duplicate_dispatch_raises_like_registry(monkeypatch) -> None:
    async def hang(deps, session_id) -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr(
        "src.services.pipeline_dispatch._run_drafting_pipeline", hang
    )
    registry = SessionTaskRegistry()
    d = InProcessDispatcher(_RecordingDeps(), registry)  # type: ignore[arg-type]
    sid = uuid4()
    d.dispatch_drafting(sid)
    await asyncio.sleep(0.05)
    with pytest.raises(RuntimeError):
        d.dispatch_drafting(sid)
    d.cancel(sid)
```

- [ ] **Step 2: Run — FAIL** (module missing)
- [ ] **Step 3: Implement** (`pipeline_runner.py` move + `pipeline_dispatch.py` + the three router/main touch-points)
- [ ] **Step 4: Run the full backend suite** — the outline endpoint tests (`TestCancelDuringDrafting`, `TestDoubleApprove`, `TestNoGateRegression`) are the real seam regression check and must pass unmodified. If any of them needs modifying, STOP — the seam is not behaviour-preserving; fix the dispatcher instead.
- [ ] **Step 5: Commit** — `refactor(pipeline): PipelineDispatcher seam, InProcessDispatcher default (INFRA-007 Task 3)`.

---

### Task 4: Cooperative cancellation (works from any process)

**Files:**
- Modify: `src/services/pipeline_runner.py` (`_drive_to_completion` + a status-check helper)
- Modify: `src/agents/content/pipeline.py` `_wrap_node` (~line 105; file is 307 lines pre-existing-over — keep the addition ≤ 6 lines)
- Test: `tests/unit/services/test_pipeline_cancellation.py`

**Interfaces:**
- Produces: `class PipelineCancelled(Exception)` in `src/services/pipeline_runner.py`; `async def raise_if_cancelled(research_svc, session_id) -> None` (reads `get_session(...).status`, raises `PipelineCancelled` when `"cancelled"`).
- `_wrap_node`'s wrapped fn gains a pre-node check via an optional `cancel_check: Callable[[], Awaitable[None]] | None` on `ContentGraphDeps` (default `None` = no check, zero behaviour change); `ContentService` passes it when it has a research repo. If threading it through `ContentGraphDeps` exceeds the size budget or touches too many call sites, fall back to checking only in `_drive_to_completion` between research→outline→draft phase boundaries and document that in-node cancellation lands with the job-store follow-up.
- `_run_full_pipeline` / `_run_drafting_pipeline` / `_drive_to_completion` catch `PipelineCancelled` and return WITHOUT writing a status (the cancel endpoint already wrote `"cancelled"`; `TERMINAL_STATUSES` already contains it, so SSE closes).

- [ ] **Step 1: Failing test** — seed an in-memory research repo with a session whose status is `"cancelled"`; assert `raise_if_cancelled` raises; assert a `_drive_to_completion` run against it returns without calling `generate` and without overwriting the status (use a generate stub that fails the test if invoked, and assert final status is still `"cancelled"`).

```python
@pytest.mark.asyncio
async def test_drive_to_completion_stops_on_cancelled_status() -> None:
    svc = _FakeResearchSvc(status="cancelled")  # get_session -> detail(status)
    called = False

    async def generate() -> object:
        nonlocal called
        called = True
        return object()

    await _drive_to_completion(svc, SESSION_ID, generate)
    assert called is False
    assert svc.status_writes == []          # nothing overwrote "cancelled"
```

(Read `_drive_to_completion`'s current body first — it writes `generating_article` before calling `generate`; the check must run before that write.)

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** (guard at the top of `_drive_to_completion`, catch in both runners; `_wrap_node` check only if the size budget allows, per the fallback note)
- [ ] **Step 4: Full backend suite green** (the AUTHOR-002 cancel tests must still pass — in-process cancel now has both mechanisms).
- [ ] **Step 5: Commit** — `feat(pipeline): cooperative cancellation via DB status (INFRA-007 Task 4)`.

---

### Task 5: Celery app, tasks, and `CeleryDispatcher`

**Files:**
- Create: `src/tasks/__init__.py`, `src/tasks/celery_app.py`, `src/tasks/pipeline_tasks.py` (each < 200 lines)
- Modify: `src/services/pipeline_dispatch.py` (add `CeleryDispatcher`)
- Modify: `src/api/main.py` `_lifespan` (choose dispatcher on `settings.task_dispatch`)
- Test: `tests/unit/tasks/test_pipeline_tasks.py`

**Interfaces:**

`src/tasks/celery_app.py`:
```python
from celery import Celery
from src.config.settings import Settings

def make_celery(settings: Settings) -> Celery:
    broker = settings.celery_broker_url or settings.redis_url
    backend = settings.celery_result_backend or settings.redis_url
    app = Celery("cognify", broker=broker, backend=backend)
    app.conf.update(
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
    )
    return app

celery_app = make_celery(Settings())   # module-level for `celery -A src.tasks.celery_app`
```

`src/tasks/pipeline_tasks.py` (sync task bodies; each wraps one `asyncio.run` inside a **fresh contextvars context** — prefork workers reuse processes and `orchestrator._record_step` calls `.set()` without reset, so stale session ids would otherwise leak between tasks and corrupt `llm_calls` attribution):
```python
_services: PipelineServices | None = None   # lazy per-worker-process singleton

def _get_services() -> PipelineServices:
    # first call: Settings() → asyncio.run(resolve_runtime_settings) →
    # asyncio.run(build_pipeline_services); cache in _services
    ...

def _run_in_fresh_context(coro_factory: Callable[[], Coroutine[Any, Any, None]]) -> None:
    contextvars.copy_context().run(asyncio.run, coro_factory())

@celery_app.task(name="cognify.run_full_pipeline", bind=True)
def run_full_pipeline_task(self, session_id: str, topic_json: dict[str, object]) -> None:
    ps = _get_services()
    deps = PipelineDeps(ps.research_service, ps.content_service, ps.outline_gate)
    topic = TopicInput.model_validate(topic_json)
    _run_in_fresh_context(lambda: _run_full_pipeline(deps, UUID(session_id), topic))

@celery_app.task(name="cognify.run_drafting_pipeline", bind=True)
def run_drafting_pipeline_task(self, session_id: str) -> None: ...
```
Both tasks get an `on_failure` that writes `article_failed` (best-effort, own `asyncio.run`, swallow errors) so a dead worker terminates the SSE stream instead of hanging it to the 1800s timeout. On `PipelineCancelled` bubbling out: catch inside the task body and return cleanly (not a failure).

`CeleryDispatcher` in `pipeline_dispatch.py`:
```python
class CeleryDispatcher:
    def __init__(self, celery: Celery) -> None: ...
    def dispatch_full_pipeline(self, session_id, topic) -> None:
        self._celery.send_task(
            "cognify.run_full_pipeline",
            args=[str(session_id), topic.model_dump(mode="json")],   # L-001
            task_id=str(session_id),
        )
    def dispatch_drafting(self, session_id) -> None:
        self._celery.send_task("cognify.run_drafting_pipeline",
                               args=[str(session_id)], task_id=f"draft-{session_id}")
    def cancel(self, session_id) -> bool:
        self._celery.control.revoke(str(session_id))
        self._celery.control.revoke(f"draft-{session_id}")
        return True   # cooperative check (Task 4) is the reliable stop
```
(`task_id` must be unique per enqueue — a session that goes create→approve uses two distinct ids, hence the `draft-` prefix. Revoke both on cancel.)

`main.py` `_lifespan`: `if resolved.task_dispatch == "celery" and db_url: app.state.pipeline_dispatcher = CeleryDispatcher(make_celery(resolved))` else the Task 3 `InProcessDispatcher`. Import `make_celery` lazily inside the branch so the API process without celery configured never imports it at module load.

- [ ] **Step 1: Failing tests** (`tests/unit/tasks/test_pipeline_tasks.py`; celery tasks are called as plain functions — no broker needed):

```python
def test_run_full_pipeline_task_drives_runner(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake_runner(deps, session_id, topic) -> None:
        seen["session_id"] = session_id
        seen["topic_title"] = topic.title

    monkeypatch.setattr("src.tasks.pipeline_tasks._run_full_pipeline", fake_runner)
    monkeypatch.setattr("src.tasks.pipeline_tasks._get_services", lambda: _fake_services())
    sid = uuid4()
    run_full_pipeline_task.run(str(sid), _topic().model_dump(mode="json"))
    assert seen["session_id"] == sid


def test_pipeline_cancelled_is_not_a_task_failure(monkeypatch) -> None:
    async def cancelled(deps, session_id, topic) -> None:
        raise PipelineCancelled()

    monkeypatch.setattr("src.tasks.pipeline_tasks._run_full_pipeline", cancelled)
    monkeypatch.setattr("src.tasks.pipeline_tasks._get_services", lambda: _fake_services())
    run_full_pipeline_task.run(str(uuid4()), _topic().model_dump(mode="json"))  # must not raise


def test_celery_dispatcher_serializes_and_uses_session_task_id() -> None:
    sent: list[tuple] = []

    class _FakeCelery:
        def send_task(self, name, args, task_id):  # noqa: ANN001
            sent.append((name, args, task_id))

    d = CeleryDispatcher(_FakeCelery())  # type: ignore[arg-type]
    sid = uuid4()
    d.dispatch_full_pipeline(sid, _topic())
    name, args, task_id = sent[0]
    assert name == "cognify.run_full_pipeline"
    assert args[0] == str(sid)
    assert isinstance(args[1], dict)     # json-mode dump, no UUID/datetime objects
    assert task_id == str(sid)
```

Build `_topic()` from the real `TopicInput` model (read its module for required fields) and `_fake_services()` as a namedtuple-shaped stub with the three service attributes.

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** (celery_app, tasks, CeleryDispatcher, main.py branch)
- [ ] **Step 4: Full backend suite + `uv run ruff check src/ tests/` + `uv run mypy src/tasks/ src/services/pipeline_dispatch.py --ignore-missing-imports`** — PASS, no new errors.
- [ ] **Step 5: Commit** — `feat(tasks): Celery app + pipeline tasks + CeleryDispatcher (INFRA-007 Task 5)`.

---

### Task 6: Worker container, compose wiring, health checks

**Files:**
- Modify: `Dockerfile.worker` (HF pre-bake + offline env + real CMD)
- Modify: `docker-compose.yml` (worker env + volume; api env)
- Modify: `src/api/routers/health.py` `_run_checks` (~line 48; file 96 lines)
- Test: `tests/unit/api/test_health.py` (extend)

**Steps:**

- [ ] **Step 1: Dockerfile.worker** — copy the HF pre-bake block from `Dockerfile.api` (~lines 53-60: `HF_HOME=/opt/hf-cache`, model download layer, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`) into `Dockerfile.worker` at the same relative position, and replace the placeholder CMD:

```dockerfile
CMD ["celery", "-A", "src.tasks.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
```

- [ ] **Step 2: docker-compose.yml** — worker service: add `COGNIFY_REDIS_URL=redis://redis:6379/0`, `COGNIFY_TASK_DISPATCH=celery`, and the `generated_assets` volume mount copied from the api service (worker-rendered images must land on the filesystem the API serves). api service: add `COGNIFY_REDIS_URL=redis://redis:6379/0` (task_dispatch stays env-driven via `.env`, defaulting inprocess — put `COGNIFY_TASK_DISPATCH=${COGNIFY_TASK_DISPATCH:-inprocess}` so flipping one `.env` line switches modes).

- [ ] **Step 3: Health checks (TDD)** — failing test first in `tests/unit/api/test_health.py`: with `redis_url` unreachable the endpoint still returns 200 with `redis: "unavailable"` (existing behaviour), and (new) monkeypatching the redis ping to succeed yields `redis: "ok"`. Implement in `_run_checks`: `redis` = `redis.asyncio.from_url(settings.redis_url).ping()` under a 1s timeout/try-except; `celery` = only checked when `settings.task_dispatch == "celery"` (a `celery_app.control.inspect(timeout=1.0).ping()` in a thread — or leave `celery: "unavailable"` when inprocess, which keeps today's contract). Keep the function under 20 lines by extracting `_check_redis(settings) -> CheckStatus`.

- [ ] **Step 4: Full backend suite green; commit** — `feat(infra): worker image (HF pre-bake + celery cmd), compose wiring, redis health check (INFRA-007 Task 6)`.

---

### Task 7: Live smoke (celery mode), verification, docs, PR

- [ ] **Step 1: Full suites + lint** — `uv run pytest tests/unit/ -q` (target: all green), `cd frontend && npx vitest run` (untouched — must stay 542), full ruff/mypy line, `npx tsc --noEmit` (13 pre-existing only).

- [ ] **Step 2: Live smoke in celery mode** — copy `.env` from the main checkout into the worktree; set `COGNIFY_TASK_DISPATCH=celery` in the environment; `docker compose -p cognify up --build -d api worker frontend` from the worktree (same compose project as the running stack). Then:
  1. `docker logs cognify-worker-1` shows celery banner + registered tasks `cognify.run_full_pipeline` / `cognify.run_drafting_pipeline`.
  2. Generate an article from the UI (Topics → Generate). Verify: API process logs show NO pipeline step logs (they're in `docker logs cognify-worker-1`); `/research/{id}` SSE streams steps live (DB-tailing from worker writes); article completes; images render and are visible in the article (generated_assets volume shared); `llm_calls` rows carry the session id (contextvars rebound correctly — spot-check `SELECT call_name, session_id FROM llm_calls ORDER BY started_at DESC LIMIT 5`).
  3. Cancel path: start another generation → click Cancel during drafting → session status lands `cancelled` and STAYS cancelled ≥60s (cooperative stop worked; no late `article_complete` overwrite); worker log shows the run stopping.
  4. Outline-gate path (if `COGNIFY_REQUIRE_OUTLINE_APPROVAL` on for the session): approve → drafting runs on the worker.
  5. `GET /api/v1/health` shows `redis: "ok"` and `celery: "ok"`.
  6. Flip back: remove `COGNIFY_TASK_DISPATCH` (default inprocess), restart api, generate once — behaviour identical to before the ticket.
  Delete the worktree `.env` afterwards.

- [ ] **Step 3: Docs** — PROGRESS.md (row → Done + smoke results in the RESUME block; note the deliberate scope cuts: no `is_running` in celery mode, job-status store deferred, `outline/regenerate` still synchronous), BACKLOG.md (row → DONE, velocity +5 SP), CLAUDE.md (status + "Next action": AUTHOR-006 per program plan Phase B — or per the user), `.env.example` (document `COGNIFY_TASK_DISPATCH` / `COGNIFY_REDIS_URL`), tick this plan's checkboxes (UTF-8-safe: `[System.IO.File]::ReadAllText/WriteAllText`, NOT `Get-Content|Set-Content`).

- [ ] **Step 4: Push + PR** — `git push -u origin feature/INFRA-007-celery`; `gh pr create --base develop --body-file <scratchpad>/pr-body-infra007.md` (body-file, not inline — inline body broke last time). PR body: what moved to the worker, the dispatch flag defaulting to inprocess, cooperative cancel design, the two infra traps fixed (HF pre-bake, generated_assets volume), scope cuts, smoke evidence. Standard footer.

---

## Self-Review (done at plan time)

- **Spec coverage:** program plan §9 INFRA-007 row = CeleryDispatcher (Task 5) + worker wiring for `_run_full_pipeline` (Tasks 5–6) + "DB-tailing works unchanged from a worker" (verified in recon; smoke step 2.2 proves it live). Review §5's freeze risk addressed at the root (worker) and the known relocation trap (HF pre-bake) closed in Task 6.
- **Deviations named:** the ticket title's "CeleryDispatcher" historically pointed at the facet-level `TaskDispatcher` (RESEARCH-era note); the actual seam is the pipeline scheduler — stated in "Not in scope" with rationale.
- **Type consistency:** `PipelineDispatcher` methods used by routers (Task 3) match `CeleryDispatcher` (Task 5); `PipelineServices` fields consumed by `_lifespan` (Task 2) and `_get_services` (Task 5) are identical; `PipelineCancelled` produced in Task 4 is consumed in Task 5's task body.
- **Known-risk callouts for the executor:** Task 2 is the highest-risk move (lifespan extraction) — its gate is the full suite, not new tests; Task 3 must not require editing the AUTHOR-002 outline tests (explicit STOP condition); Task 4 has an explicit fallback if `ContentGraphDeps` threading blows the size budget; `TopicInput`'s exact fields must be read before writing `_topic()`.
