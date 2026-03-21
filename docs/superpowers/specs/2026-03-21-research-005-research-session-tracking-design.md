# RESEARCH-005: Research Session Tracking — Design Spec

## Overview

Wire the existing research infrastructure end-to-end so sessions are trackable with real data. The orchestrator will persist `AgentStep` records at each node boundary (including per-facet steps), API responses will carry step details and source/embedding counts, and the frontend will connect to real API data instead of mock data.

**Scope boundaries:**
- No WebSocket — frontend polling (already implemented at 10s intervals for active sessions) is sufficient
- No global Milvus stats endpoint — per-session counts satisfy the acceptance criteria
- No PostgreSQL migration — continues using in-memory repositories (future ticket)
- No Celery integration — continues using `AsyncIODispatcher` (future ticket)

## Acceptance Criteria (from BACKLOG.md)

1. Dashboard shows session status (queued, in progress, complete, failed)
2. Each agent step logged with duration and result summary
3. Sources used count and embedding count displayed
4. ~~Real-time status updates via WebSocket~~ → Deferred; polling sufficient for MVP

## Section 1: App Initialization Wiring

**Problem:** `ResearchService` exists but isn't created in `create_app()`. The API endpoints reference `request.app.state.research_service` but it's never initialized, so all research endpoints are non-functional.

**Solution:** In `src/api/main.py`, add initialization during `create_app()`:

1. Create in-memory repositories:
   - `InMemoryResearchSessionRepository`
   - `InMemoryAgentStepRepository`
   - `InMemoryTopicRepository`
2. Create `LangGraphResearchOrchestrator` with the configured LLM (or skip if no API key)
3. Wire into `ResearchService`, attach to `app.state.research_service`

**Config guard:** If `ANTHROPIC_API_KEY` is not configured, skip orchestrator init. Research endpoints return 503 Service Unavailable with a message indicating the research service is not configured.

**Files modified:**
- `src/api/main.py` — add `_init_research_service()` helper

## Section 2: Agent Step Tracking in Orchestrator

**Problem:** The orchestrator runs its LangGraph but doesn't persist `AgentStep` records. There is no visibility into what happened during a research session beyond the final status.

**Solution:** Instrument each graph node to create and update `AgentStep` records.

### Orchestrator Changes

- Add `step_repo: AgentStepRepository | None` as an optional field on `LangGraphResearchOrchestrator`. When `None`, step tracking is silently skipped (preserves backward compatibility with existing tests).
- Each graph node wraps its work with step lifecycle:
  1. Create `AgentStep(status="in_progress", started_at=now())`
  2. Execute node logic
  3. Update `AgentStep(status="complete", duration_ms=elapsed, output_data=summary_dict)`
  4. On exception: `AgentStep(status="failed", output_data={"error": str(e)})`

### Steps Recorded Per Session

| Step Name | When Created | Output Summary |
|-----------|-------------|---------------|
| `plan_research` | `plan_research` node | `{"facet_count": N, "facet_titles": [...]}` |
| `research_facet_0..N` | `dispatch_agents` node (one per facet) | `{"sources_found": N, "claims_extracted": N, "facet_title": "..."}` |
| `index_findings` | `index_findings` node | `{"embeddings_created": N}` |
| `evaluate_completeness` | `evaluate_completeness` node | `{"is_complete": bool, "weak_facets": [...], "reasoning": "..."}` |
| `finalize` | `finalize` node | `{"total_sources": N, "total_duration_ms": N}` |

For a typical 4-facet research session, this produces ~8-9 steps total.

### Per-Facet Step Tracking

Inside `dispatch_agents`, each `agent_fn(facet)` call is wrapped with step creation. The `AsyncIODispatcher` is not modified — instead, the wrapping happens in the `dispatch_agents` node function itself, which has access to `step_repo` via closure.

Pattern:
```python
async def dispatch_agents(state: ResearchState) -> dict:
    for facet in facets:
        step = create_step(f"research_facet_{facet.index}", ...)
        result = await agent_fn(facet)
        update_step(step, result)
```

### Retry Round Handling

If `evaluate_completeness` triggers a retry (round 2), additional `research_facet_*` steps are created for the weak facets. Step names include the round: `research_facet_{index}_round_{round}` for rounds > 1.

**Files modified:**
- `src/agents/research/orchestrator.py` — add step_repo, instrument nodes

## Section 3: API Response Enrichment

**Problem:** API responses don't carry source/embedding counts or step output summaries.

**Solution:** Additive changes to existing schemas.

### Schema Changes

**`ResearchSessionResponse`** (detail endpoint):
- Already includes `steps: list[AgentStepResponse]` — works once real steps exist
- Add `sources_count: int` — total sources found across all facets
- Add `embeddings_count: int` — total embeddings created during indexing

**`ResearchSessionSummary`** (list endpoint items):
- Add `sources_count: int`
- Add `embeddings_count: int`

**`AgentStepResponse`**:
- Already has `step_name`, `status`, `duration_ms`, `started_at`, `completed_at`
- Add `output_summary: str | None` — human-readable one-liner derived from `output_data`

### Count Computation

`sources_count` and `embeddings_count` are computed in `ResearchService.get_session()` and `list_sessions()` by reading from the session's `findings_count` and `indexed_count` fields (already populated by `run_and_finalize`).

**Files modified:**
- `src/api/schemas/research.py` — add fields
- `src/services/research.py` — compute counts in service methods

## Section 4: Frontend Connection

**Problem:** Frontend hooks return mock data with TODO comments marking where to connect real API.

### Hook Changes

**`useResearchSessions(status?, page?, size?)`:**
- Replace `getMockSessions()` with `fetch('/api/v1/research/sessions?status=...&page=...&size=...')`
- Response shape already matches `ResearchSessionSummary` with new count fields

**`useResearchSession(sessionId)`:**
- Replace `mockSessionDetails` with `fetch('/api/v1/research/sessions/{sessionId}')`
- Existing polling logic (10s refetch for active sessions) preserved

### API Client

Add `researchApi` module following existing patterns in the frontend:
- `fetchSessions(params)` — GET list with query params
- `fetchSession(id)` — GET detail
- `createSession(topicId)` — POST new session
- Auth token handling (read from auth context/cookie)

### Type Updates

**`types/research.ts`:**
- Add `sources_count: number` and `embeddings_count: number` to `ResearchSessionSummary`
- Add `output_summary: string | null` to `AgentStep`

### KnowledgeBaseStub → Real Component

Transform from placeholder to computed stats display:
- Total sources: sum of `sources_count` across all sessions
- Total embeddings: sum of `embeddings_count` across all sessions
- Data derived from the sessions list response (no new API call)

**Files modified:**
- `frontend/src/hooks/use-research-sessions.ts` — swap mock → fetch
- `frontend/src/types/research.ts` — add fields
- `frontend/src/lib/api/research.ts` (new) — API client module
- `frontend/src/components/research/knowledge-base-stub.tsx` — real stats

## Section 5: Testing Strategy

### Backend Unit Tests

- **Step recording:** Verify each graph node creates an `AgentStep` with correct status, duration, and output summary. Test with mock `AgentStepRepository` to inspect created steps.
- **Service enrichment:** `ResearchService.get_session()` returns `sources_count` and `embeddings_count` computed from step data.
- **Schema serialization:** New fields serialize correctly in `ResearchSessionResponse` and `ResearchSessionSummary`.
- **Config guard:** When no API key configured, research endpoints return 503.

### Backend Integration Tests

- **Full flow:** `POST /research/sessions` → poll `GET /research/sessions/{id}` → verify steps populated with durations and output summaries.
- **List endpoint:** Returns `sources_count`/`embeddings_count` per session item.
- **App initialization:** `create_app()` attaches `research_service` to `app.state`.

### Frontend Tests

- **Hook tests:** Mock fetch responses matching real API shape; verify data flows to components.
- **KnowledgeBaseStub:** Renders aggregate stats computed from session list data.
- **Type compatibility:** New fields render correctly in `SessionCard` and `SessionSteps`.

### Backward Compatibility

- `step_repo` is optional on the orchestrator — all existing orchestrator tests pass without changes.
- New schema fields have defaults (`sources_count=0`, `embeddings_count=0`, `output_summary=None`) — existing API consumers unaffected.

## File Change Summary

| File | Change Type | Description |
|------|------------|-------------|
| `src/api/main.py` | Modified | Add `_init_research_service()` in `create_app()` |
| `src/agents/research/orchestrator.py` | Modified | Add `step_repo`, instrument all nodes |
| `src/api/schemas/research.py` | Modified | Add count fields and `output_summary` |
| `src/services/research.py` | Modified | Compute counts in service methods |
| `frontend/src/hooks/use-research-sessions.ts` | Modified | Swap mock data → real API fetch |
| `frontend/src/types/research.ts` | Modified | Add new fields |
| `frontend/src/lib/api/research.ts` | New | Research API client module |
| `frontend/src/components/research/knowledge-base-stub.tsx` | Modified | Real stats from session data |
| `tests/unit/agents/research/test_step_tracking.py` | New | Step recording unit tests |
| `tests/unit/api/test_research_schemas.py` | New or modified | Schema serialization tests |
| `tests/integration/test_research_session_tracking.py` | New | Full flow integration test |
| `frontend/src/hooks/__tests__/use-research-sessions.test.ts` | Modified | Real API response mocks |
| `frontend/src/components/research/__tests__/knowledge-base-stub.test.tsx` | Modified | Real stats tests |
