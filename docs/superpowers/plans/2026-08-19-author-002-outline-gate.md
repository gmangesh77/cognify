# AUTHOR-002 — Outline Approval Gate + Cancel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user opt in to reviewing, editing, regenerating and approving the article outline before ~3 minutes of drafting starts — and cancel any active session — without changing the autonomous default.

**Architecture:** Two graph runs around the existing `ArticleDraft` (ADR-006 Option C). Run 1 = research → outline + queries (new `stop_after_outline` flag on `ContentGraphDeps` routes `generate_queries → END`), persisted as `ArticleDraft(status=outline_complete)`; session → new status `awaiting_outline_review`. The user edits/regenerates via `/research/sessions/{id}/outline*`. Approve = run 2: the existing full graph with `outline` pre-seeded in state (`outline_node` already no-ops when an outline is present), then the same persist path as `generate_full_article`. Cancel uses a small in-process `SessionTaskRegistry` (asyncio tasks keyed by session) — the seam INFRA-007 will replace with Celery revocation. Gate is off by default (`COGNIFY_REQUIRE_OUTLINE_APPROVAL=false`) with a per-session override on the create request (persisted on the session row). Frontend: `OutlineReviewStep` inside `SessionProgress`, a Cancel button, and a "Review outline before drafting" checkbox in the Generate modal. All status consumers updated per L-003.

**Tech Stack:** FastAPI, LangGraph, SQLAlchemy async + Alembic, pydantic-settings, pytest/FakeListChatModel; Next.js 16 / React 19 / TanStack Query / Vitest.

**Spec:** `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §3, §4.2–4.3, §5.3, §9 Phase A AC #2–#3; `docs/architecture/adrs/ADR-006-supervised-pipeline-events-and-outline-gate.md`.

## Global Constraints

- Functions < 20 lines, files < 200 lines, ≤ 3 params (bundle with dataclasses/Pydantic). `src/services/content/__init__.py` (429 l.), `src/api/routers/research.py`, `src/agents/content/nodes.py` are already over — add new code in **new** modules (`src/services/content/outline_gate.py`, `src/services/session_tasks.py`, `src/api/routers/outline.py`) and keep edits to the big files minimal.
- TDD. Backend: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest <path> -q -p no:cacheprovider`. Frontend: `cd frontend && npx vitest run <path>`. Lint: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`; `npx eslint`, `npx tsc --noEmit`.
- **L-003**: new statuses `awaiting_outline_review` and `cancelled` must be added at every consumer: `src/db/repositories.py:147-150` (status_groups), `src/services/content/__init__.py:300-308` (`_load_session` whitelist — add `awaiting_outline_review`), `src/models/session_events.py` (`TERMINAL_STATUSES` already has `cancelled`), frontend `types/research.ts` (`SessionStatus`), `session-status-badge.tsx`, `session-filters.tsx`, `session-card.tsx` (border/progress colours), `hooks/use-research-sessions.ts` (active-poll list: add `awaiting_outline_review`), `lib/research/session-status.ts` (`cancelled` already terminal; `awaiting_outline_review` is NOT terminal), `components/research/session-progress*.tsx`, `session-steps.tsx` labels (`content_outline_review: "Outline review"` not needed — no step is recorded for review).
- L-001: `model_dump(mode="json")` for any JSONB write (outline on `article_drafts.outline` already goes through `_to_jsonb`).
- Feature flag default **off**: with `require_outline_approval` false everywhere, `_run_full_pipeline` behaviour is byte-identical to today.
- Conventional commits; branch `feature/AUTHOR-002-outline-gate`; never stack PRs; trailers on every commit.

---

### Task 1: `stop_after_outline` graph span + `OutlineContext` (regenerate instruction)

**Files:**
- Modify: `src/agents/content/pipeline.py` (`ContentGraphDeps`, `ContentState`, routing after `generate_queries`)
- Modify: `src/agents/content/outline_generator.py:69-100` (bundle kwargs into `OutlineContext`, add `instruction`)
- Modify: `src/agents/content/nodes.py:51-79` (`outline_node` builds `OutlineContext` from state incl. `outline_instruction`)
- Test: `tests/unit/agents/content/test_pipeline_outline_gate.py`, `tests/unit/agents/content/test_outline_generator.py` (adapt to `OutlineContext`)

**Interfaces:**
- `ContentGraphDeps.stop_after_outline: bool = False` — when true, `generate_queries` routes to `END` (no drafting). Docstring updated to "step-tracking deps + graph span options".
- `ContentState.outline_instruction: NotRequired[str | None]`.
- `@dataclass(frozen=True) OutlineContext(target_audience=None, preferred_angle=None, content_tone=None, keywords=None, instruction=None)`; `generate_outline(topic, findings, llm, ctx: OutlineContext | None = None)`. When `ctx.instruction` is set, the prompt gains the line `Editor instructions for this revision: {instruction}` in the context block. Grep all callers of `generate_outline(` (nodes.py, tests, services) and update them.

- [ ] **Step 1: Failing tests**

```python
# tests/unit/agents/content/test_pipeline_outline_gate.py
"""Graph span: stop_after_outline ends after queries; outline-in-state skips outline node."""
import json
from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.pipeline import ContentGraphDeps, build_content_graph
from tests.unit.agents.content.test_pipeline import (  # reuse existing helpers
    _make_findings,
    _make_topic,
    _outline_json,
)


def _queries_json() -> str:
    return json.dumps([{"section_index": 0, "queries": ["q1"]}])


def _state(**extra):  # type: ignore[no-untyped-def]
    base = {
        "topic": _make_topic(), "research_plan": None, "findings": _make_findings(),
        "session_id": uuid4(), "outline": None, "status": "outline_generating",
        "error": None, "target_audience": None, "content_tone": None,
        "preferred_angle": None, "keywords": None, "image_specs": [],
    }
    base.update(extra)
    return base


async def test_stop_after_outline_runs_outline_and_queries_only() -> None:
    llm = FakeListChatModel(responses=[_outline_json(), _queries_json()])
    graph = build_content_graph(llm, deps=ContentGraphDeps(stop_after_outline=True))
    result = await graph.ainvoke(_state())
    assert result["outline"] is not None
    assert result.get("section_queries")
    assert not result.get("section_drafts")


async def test_outline_in_state_skips_outline_generation() -> None:
    from src.models.content_pipeline import ArticleOutline
    outline = ArticleOutline.model_validate(json.loads(_outline_json()))
    # First fake response must be consumed by the QUERIES node, not the outline node.
    llm = FakeListChatModel(responses=[_queries_json()] + ["x"] * 12)
    graph = build_content_graph(llm, deps=ContentGraphDeps(stop_after_outline=True))
    result = await graph.ainvoke(_state(outline=outline, status="outline_complete"))
    assert result["outline"].title == outline.title
    assert result.get("section_queries")


async def test_node_sets_identical_across_spans() -> None:
    llm = FakeListChatModel(responses=["x"])
    full = build_content_graph(llm)
    half = build_content_graph(llm, deps=ContentGraphDeps(stop_after_outline=True))
    assert set(full.get_graph().nodes) == set(half.get_graph().nodes)
```

Check `_make_findings`/`_outline_json` exist with those names in `test_pipeline.py` (they do per the current file); check the queries JSON shape expected by `generate_section_queries` (`src/agents/content/query_generator.py`) and adjust `_queries_json` accordingly.

- [ ] **Step 2: Run → FAIL** (`ContentGraphDeps` has no `stop_after_outline`)

- [ ] **Step 3: Implement** — in `pipeline.py`:

```python
@dataclass
class ContentGraphDeps:
    """Step-tracking deps + graph span options for the content pipeline."""
    step_repo: AgentStepRepository | None = field(default=None)
    session_id: UUID | None = field(default=None)
    llm_call_repo: LlmCallRepository | None = field(default=None)
    stop_after_outline: bool = False
```
```python
def _make_after_queries_router(stop_after_outline: bool):  # type: ignore[no-untyped-def]
    def _route(state: ContentState) -> str:
        if stop_after_outline:
            return END
        return _check_not_failed(state)
    return _route
```
and replace the `generate_queries` conditional edge's router with `_make_after_queries_router(bool(deps and deps.stop_after_outline))`. Add `outline_instruction: NotRequired[str | None]` to `ContentState`.

In `outline_generator.py` add `OutlineContext` and refactor `generate_outline` to take it (keep behaviour identical; add the instruction line). In `nodes.py` `outline_node` builds `OutlineContext(target_audience=state.get(...), preferred_angle=..., content_tone=..., keywords=..., instruction=state.get("outline_instruction"))`. Update every caller found by `rg "generate_outline\("`.

- [ ] **Step 4: Run new tests + `tests/unit/agents/content` → PASS; ruff; mypy on the 3 files (only fix errors you introduce)**

- [ ] **Step 5: Commit** — `feat(pipeline): stop_after_outline graph span + OutlineContext with editor instruction (AUTHOR-002)`

---

### Task 2: Session status/settings/migration + `ResearchService.start_session(require_outline_approval)` + L-003 backend consumers

**Files:**
- Modify: `src/config/settings.py` (`require_outline_approval: bool = False`)
- Modify: `src/models/research_db.py` (`ResearchSession.require_outline_approval: bool = False`), `src/db/tables.py` (`ResearchSessionRow.require_outline_approval: Mapped[bool]`, `Boolean, server_default=sa.false()`), `src/db/repositories.py` (row↔model mapping for the new column; `status_groups` add `"awaiting_outline_review": ["awaiting_outline_review"]`, `"cancelled": ["cancelled"]`, and include `"cancelled"` in the `failed` group? **No** — keep separate; add `"in_progress"` group unchanged)
- Create: `alembic/versions/a9d4e2f7c1b8_add_require_outline_approval_to_research_sessions.py` (`down_revision = "e7c1a9d3f8b2"`; `op.add_column("research_sessions", sa.Column("require_outline_approval", sa.Boolean(), nullable=False, server_default=sa.false()))`; downgrade drops it)
- Modify: `src/api/schemas/research.py` (`CreateResearchSessionRequest.require_outline_approval: bool | None = None`; `ResearchSessionResponse.require_outline_approval: bool = False`)
- Modify: `src/services/research.py:136-160` (`start_session` gains `require_outline_approval: bool = False` — note the function already exceeds 3 params; bundle NEW params into a `SessionOptions` dataclass only if you also move existing ones — **do not**; just add the kwarg and note it), `src/api/routers/research.py:78-110` (pass through; resolve `body.require_outline_approval if not None else settings.require_outline_approval`)
- Modify: `src/services/content/__init__.py:300-308` (`_load_session` valid += `"awaiting_outline_review"`)
- Test: `tests/unit/services/test_research_outline_flag.py`, `tests/unit/api/test_research_endpoints.py` (extend: POST with `require_outline_approval: true` echoes on GET), `tests/unit/db/...` only if a mapping test pattern exists (check `tests/unit/db`)

- [ ] **Step 1: Failing tests** — (a) `start_session(..., require_outline_approval=True)` persists the flag on the returned/stored session; (b) POST `/research/sessions` with the flag → session detail shows `require_outline_approval: true`; (c) `_load_session` accepts `awaiting_outline_review` (unit test via `ContentService` with an in-memory research repo double — see existing content service tests for the pattern, e.g. `tests/unit/services/test_content_service*.py`).
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** (settings, model, table, migration, repo mapping, schema, service, router, whitelist). Check `PgResearchSessionRepository._to_model/_to_row` (or equivalent) in `src/db/repositories.py` and add the field in both directions.
- [ ] **Step 4: Run `tests/unit/services tests/unit/api tests/unit/db -q` → PASS; ruff; mypy touched files**
- [ ] **Step 5: Commit** — `feat(research): require_outline_approval flag (setting + session column + request) and awaiting_outline_review status (AUTHOR-002)`

---

### Task 3: `OutlineGateService` — outline-only run, update, regenerate, approve-run

**Files:**
- Create: `src/services/content/outline_gate.py` (< 200 l.)
- Modify: `src/services/content/__init__.py` — extract from `generate_full_article` two helpers it and the gate can share: `_initial_state(session, topic, findings) -> dict[str, object]` and `_persist_pipeline_result(session, result) -> CanonicalArticle` (the code from `draft = ArticleDraft(...)` to the return). Keep `generate_full_article` behaviour identical (it becomes: load → state → graph → `_persist_pipeline_result`). Add `find_latest_by_session` to `ArticleDraftRepository` protocol + `InMemoryArticleDraftRepository` + `PgArticleDraftRepository` (order by `created_at desc`, limit 1; `ArticleDraftRow.session_id` exists).
- Test: `tests/unit/services/test_outline_gate.py`

**Interfaces (produced):**
```python
class OutlineGateService:
    def __init__(self, content: ContentService) -> None
    async def generate_outline_only(self, session_id: UUID) -> ArticleDraft
        # state = content._initial_state(...); deps = ContentGraphDeps(step_repo, session_id, llm_call_repo, stop_after_outline=True)
        # graph.ainvoke → ArticleDraft(outline=..., status=OUTLINE_COMPLETE) via drafts.create; raises ValueError if outline None
    async def get_outline(self, session_id: UUID) -> ArticleDraft           # latest draft for session; NotFoundError if none
    async def update_outline(self, session_id: UUID, outline: ArticleOutline) -> ArticleDraft
        # validate_outline(outline): ≥1 section, unique titles (case-insensitive), indices renumbered 0..n-1; drafts.update
    async def regenerate_outline(self, session_id: UUID, instruction: str | None) -> ArticleDraft
        # same as generate_outline_only but state["outline_instruction"]=instruction; replaces outline on the latest draft (drafts.update)
    async def generate_from_outline(self, session_id: UUID) -> CanonicalArticle
        # draft = get_outline; state = content._initial_state(...) | {"outline": draft.outline, "status": "outline_complete"}; full graph; content._persist_pipeline_result
def validate_outline(outline: ArticleOutline) -> ArticleOutline  # pure; raises ValueError with a list of messages
```

- [ ] **Step 1: Failing tests** using `FakeListChatModel` + in-memory repos (mirror the fixtures in the existing content-service tests; L-007: give the fake LLM enough responses — outline-only needs 2 (outline, queries); generate_from_outline needs the full-pipeline count minus the outline response). Cases: outline-only stores a draft with `OUTLINE_COMPLETE` and no section drafts; `update_outline` rejects empty sections / duplicate titles (ValueError) and renumbers indices; `regenerate_outline` passes the instruction into the prompt (assert the fake LLM received a HumanMessage containing the instruction — `FakeListChatModel` doesn't record inputs; wrap it in a tiny recording subclass or use `AsyncMock` side_effect returning `AIMessage`s); `generate_from_outline` produces a `CanonicalArticle` whose section headings match the stored outline titles and does not call the outline prompt (first fake response is consumed by the queries node).
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** (new module + the two extracted helpers + repo method). Keep every function < 20 lines; use small helpers.
- [ ] **Step 4: Run `tests/unit/services -q` + `tests/unit/agents/content -q` → PASS (existing `generate_full_article` tests must still pass); ruff; mypy**
- [ ] **Step 5: Commit** — `feat(content): OutlineGateService — outline-only run, validate/update/regenerate, generate_from_outline (AUTHOR-002)`

---

### Task 4: `SessionTaskRegistry` + gated `_run_full_pipeline` + outline/cancel endpoints

**Files:**
- Create: `src/services/session_tasks.py` — `class SessionTaskRegistry: spawn(session_id, coro) -> asyncio.Task; cancel(session_id) -> bool; is_running(session_id) -> bool` (dict, auto-remove on done via `add_done_callback`).
- Modify: `src/api/routers/research.py` — `create_research_session` uses `request.app.state.session_tasks.spawn(session.id, _run_full_pipeline(...))` instead of `BackgroundTasks.add_task` (keep `BackgroundTasks` param removal tidy); `_run_full_pipeline` gate: after research `complete`, if `session.require_outline_approval` (already resolved at create) and `outline_gate` is configured → `await gate.generate_outline_only(session_id)`; `update_session_status(..., "awaiting_outline_review")`; return. Else unchanged. Wrap the body in `try/except asyncio.CancelledError: update_session_status(..., "cancelled"); raise`.
- Create: `src/api/routers/outline.py` (< 200 l.): 
  - `GET /research/sessions/{id}/outline` → `OutlineResponse {draft_id, status, outline: ArticleOutline}` (viewer+)
  - `PUT /research/sessions/{id}/outline` body `ArticleOutline` → 200 `OutlineResponse`; 422 `{"detail": [messages]}` on `ValueError` from `validate_outline` (editor+)
  - `POST /research/sessions/{id}/outline/regenerate` body `{instruction: str | None}` → 200 `OutlineResponse` (editor+, `5/minute`)
  - `POST /research/sessions/{id}/outline/approve` → 202 `{session_id, status: "generating_article"}`; 409 if session status ≠ `awaiting_outline_review`; spawns `_run_drafting_pipeline(session_id)` = `generating_article` → `gate.generate_from_outline` → `article_complete` / `article_failed` (same logging as `_run_full_pipeline`) (editor+)
  - `POST /research/sessions/{id}/cancel` → 200 `{session_id, status: "cancelled"}`; 409 if already terminal; `registry.cancel(id)` best-effort + `update_session_status(id, "cancelled")` (editor+)
- Modify: `src/api/main.py` — `app.state.session_tasks = SessionTaskRegistry()`; `app.state.outline_gate = OutlineGateService(app.state.content_service)` wherever `content_service` is created (both PG and in-memory branches); include `outline_router` (tags `research`).
- Test: `tests/unit/services/test_session_tasks.py`, `tests/unit/api/test_outline_endpoints.py` (reuse `research_app` fixture pattern; install an in-memory `ContentService` + `OutlineGateService` with a FakeLLM on `app.state`; cases: flow create(with flag) → session reaches `awaiting_outline_review` (poll `GET /research/sessions/{id}` a few times with `asyncio.sleep(0)`), GET outline, PUT invalid → 422, PUT valid → 200, regenerate → 200, approve → 202 then session eventually `article_complete`; cancel active → 200 + status cancelled; cancel terminal → 409; approve when not awaiting → 409; flag off → session goes straight to `article_complete` (regression)).

- [ ] **Step 1: Failing tests** → **Step 2: Run → FAIL** → **Step 3: Implement** → **Step 4: `tests/unit/api tests/unit/services -q` PASS; ruff; mypy** → **Step 5: Commit** — `feat(api): outline review endpoints, cancel, SessionTaskRegistry; gated research pipeline (AUTHOR-002)`

Notes: the `FakeOrchestrator` in `test_research_endpoints.py` completes research immediately — good for these flows. Keep the router thin: all logic in `OutlineGateService`/`ResearchService`. Responses are Pydantic models (`src/api/schemas/outline.py`, new).

---

### Task 5: Frontend — types/API, L-003 consumers, `OutlineReviewStep`, Cancel, modal checkbox

**Files:**
- Modify: `frontend/src/types/research.ts` (`SessionStatus` += `"awaiting_outline_review" | "cancelled"`; `ArticleOutline`/`OutlineSection` types; `OutlineResponse`)
- Modify: `frontend/src/lib/api/research.ts` (`fetchOutline`, `updateOutline`, `regenerateOutline`, `approveOutline`, `cancelSession`)
- Modify (L-003): `session-status-badge.tsx` (`awaiting_outline_review: {label: "Outline review", dotClass: "bg-info"}`, `cancelled: {label: "Cancelled", dotClass: "bg-neutral-400"}`), `session-filters.tsx` (+ "Outline review", "Cancelled"), `session-card.tsx` (border/bar colours; `awaiting_outline_review` shows **Review outline →** link to `/research/{id}` instead of "View progress"), `hooks/use-research-sessions.ts` (poll list += `awaiting_outline_review`), `lib/research/session-status.ts` (no change — `cancelled` terminal, `awaiting_outline_review` active), `session-progress.tsx` (status ⇒ render `OutlineReviewStep` when `awaiting_outline_review`; Cancel button in header while active), `session-progress-footer.tsx` (`cancelled` → neutral "Cancelled" panel + Back link)
- Create: `frontend/src/components/research/outline-review-step.tsx` (+ `outline-section-row.tsx` if needed, each < 200 l.), `outline-review-step.test.tsx`; `frontend/src/hooks/use-outline-review.ts` (TanStack `useQuery` for `fetchOutline`, `useMutation`s for update/regenerate/approve with query invalidation)
- Modify: `frontend/src/components/topics/generate-article-modal.tsx` + `create-topic-modal.tsx`/`CreateTopicData` + `types/api.ts` `ArticleParams` (`require_outline_approval?: boolean`) + `use-generate-actions.ts` (forward) — checkbox label **"Review outline before drafting"** (unchecked by default → omitted → server default)

**OutlineReviewStep behaviour:** loads outline; editable title + subtitle; per section: title input, key points textarea (one per line), ↑/↓ reorder, delete, "Add section" (appends `{index, title:"New section", description:"", key_points:[], target_word_count: 300, relevant_facets:[]}`); "Regenerate outline" with an optional instruction input; **Approve & write** primary button (disabled while a mutation is pending; after success the parent `useSessionEvents` stream carries on — no navigation needed). Validation errors from 422 are shown in a red list. Dirty-state: Approve uses the server copy — if local edits are unsaved, **Approve** first PUTs then approves (one handler: save-if-dirty → approve).

- [ ] **Step 1: Failing tests** (component: renders sections from `fetchOutline` mock; reorder/delete/add mutate local state; Approve with dirty state calls `updateOutline` then `approveOutline`; 422 messages render; Regenerate calls `regenerateOutline` with the instruction. Badge/filter tests extended for the two new statuses; `use-generate-actions.test.ts` asserts `require_outline_approval` forwarded; session-card test for the Review outline link.)
- [ ] **Step 2: Run → FAIL** → **Step 3: Implement** → **Step 4: `npx vitest run` (full), `npx eslint` changed files, `npx tsc --noEmit` (only pre-existing errors)** → **Step 5: Commit** — `feat(frontend): outline review step, cancel, new session statuses, review-outline opt-in (AUTHOR-002)`

---

### Task 6: Docs, full suites, live smoke, PR/merge readiness

- [ ] Full suites: backend `tests/unit` + `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`; frontend `npx vitest run`, `tsc`, `eslint`.
- [ ] Migration check: `uv run alembic -c alembic.ini upgrade head` against the running Postgres (compose project `cognify`), then `uv run alembic -c alembic.ini heads` shows the new revision; note the command in the report.
- [ ] Live smoke (controller): rebuild api+frontend from this worktree (`docker compose -p cognify build api frontend && docker compose -p cognify up -d api frontend`), set `COGNIFY_REQUIRE_OUTLINE_APPROVAL` unset (default off) and verify a flag-off run is unchanged via API; then via API create a session with `require_outline_approval: true` on an existing topic, watch it reach `awaiting_outline_review`, GET/PUT/regenerate/approve, confirm `article_complete`; cancel a fresh one. UI: open `/research/{id}` in the awaiting state, screenshot the review step.
- [ ] Docs: `PROGRESS.md` AUTHOR-002 row → Done; program plan §9 row; `CLAUDE.md` Current Status; `docs/LEARNINGS.md` add **L-011**: "Content graph re-entry: `outline_node` no-ops when `outline` is in state — to resume from an approved outline, seed `outline` + `status=outline_complete`; to stop after planning use `ContentGraphDeps(stop_after_outline=True)`; `generate_outline()`/`draft_article()` legacy methods are superseded by `OutlineGateService`"; update L-006 note accordingly.
- [ ] Commit docs; hand off via finishing-a-development-branch (merge/PR decision is the user's).

---

## Self-review
- Spec coverage: ADR-006 §C.3 (two runs, flag, per-session override, endpoints) → T1–T4; C.4 cancel → T4; L-003 consumers → T2 (backend) + T5 (frontend); Phase A AC #2 (edit/reorder/add/delete/regenerate/approve; final article reflects edited outline — T3 test + T6 smoke; flag-off byte-identical — T4 regression test) and AC #3 (cancel within 5 s — T4) covered. Brief per-brief override is AUTHOR-003 (per-session request flag suffices now).
- Placeholders: none; each task names files, interfaces, test cases and commands.
- Type consistency: `ContentGraphDeps.stop_after_outline` (T1) used by T3; `OutlineContext` (T1) used by nodes; `OutlineGateService` method names (T3) used by T4 router; `require_outline_approval` naming identical across settings/model/row/schema/request/frontend (T2/T5); statuses `awaiting_outline_review`/`cancelled` identical everywhere.
