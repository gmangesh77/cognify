---

## status: "accepted"
date: 2026-08-19
decision-makers: ["Engineering Team"]
informed-by: "docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md"
depends-on: "ADR-001 (LangGraph orchestration), ADR-003 (CanonicalArticle boundary)"

# ADR-006: Supervised Pipeline — Event Bus, SSE Progress and Outline Gate

## Context and Problem Statement

The content pipeline (research → outline → draft → validate → citations → humanize → SEO → visuals) runs unattended for 2–5 minutes. The dashboard observes it only by polling a status enum and renders a hard-coded percentage per status. Users cannot see real progress, cannot cancel, and cannot intervene before drafting starts. The August 2026 review (§4) identified this as the single largest UX gap versus hands-on authoring tools, whose model is: brief → editable outline → streamed sections → per-section regenerate.

We need real-time progress and a human checkpoint **without** giving up the autonomous, server-side-truth pipeline (ADR-001) or turning the frontend into the orchestrator.

## Decision Drivers

- **Server-side truth**: the graph and the database remain the only state; the browser is a view.
- **Zero regression for autonomous mode**: the self-driving flow must be byte-identical unless a user opts in.
- **Worker-ready**: progress must keep working when the pipeline moves from FastAPI `BackgroundTasks` to a Celery worker (INFRA-007).
- **Restart-safe**: a page refresh or API restart must not lose the ability to show current state or resume.
- **Small blast radius**: nodes must not know about HTTP/SSE.

## Considered Options

### Option A: LangGraph checkpointer + `interrupt_before=["draft_sections"]`
Idiomatic LangGraph. **Rejected for v1**: the only checkpointer wired today is `MemorySaver` (state lost on restart); `PostgresSaver` is unscheduled work; and the stored `ArticleDraft` already *is* a durable outline checkpoint. Revisit if a second interrupt point is ever needed.

### Option B: Frontend-orchestrated multi-endpoint generation (ImpactAI model)
Browser calls outline → section → section … **Rejected**: moves orchestration and state to the client, duplicates the graph, breaks observability (`llm_calls`, steps) and worker offload.

### Option C: Event bus + SSE + two graph runs around `ArticleDraft` (Selected)
1. Typed `SessionEvent`s are derived from the persisted `agent_steps` + session status (`diff_steps` / `tail_session` in `src/services/session_events.py`); the existing node wrapper (`_wrap_node`) binds a `report_progress()` reporter so nodes can surface sub-step progress (e.g. per-section drafting). A Redis pub/sub bus is the optional low-latency upgrade.
2. `GET /research/sessions/{id}/events` streams SSE: first a `replay` of persisted `agent_steps` + status, then live events until `done|error`. Polling remains as fallback.
3. Outline gate: `build_content_graph(stop_after_outline=True)` ends after `generate_queries` and persists the outline to `ArticleDraft(status=outline_ready)`; session → `awaiting_outline_review`; the user edits/approves via `GET/PUT/POST …/outline*`; `build_content_graph(start_from_draft=True)` enters at `draft_sections` seeded from the stored outline. Feature flag `COGNIFY_REQUIRE_OUTLINE_APPROVAL` (default `false`) + per-brief override.
4. Cancel: `POST …/cancel` sets `cancelled` and best-effort cancels the in-process task via a `SessionTaskRegistry`.

## Decision Outcome

Chosen option: **C**. It adds three thin, independently testable pieces, keeps nodes pure, and makes the producer location (API process vs worker) irrelevant to the consumer.

**Transport (v1, AUTHOR-001):** the SSE endpoint *tails the persisted `agent_steps` rows* (1 s poll, configurable via `COGNIFY_SESSION_EVENTS_*`) rather than subscribing to Redis pub/sub — the API has no Redis client today, DB-tailing is worker-safe by construction, and replay-on-connect falls out naturally. Nodes publish sub-step progress by merging into their running step's `output_data` via `report_progress()` (`src/utils/step_progress.py`). Redis pub/sub remains the documented upgrade path if sub-second latency is ever required; the `SessionEvent` contract and the frontend consumer stay unchanged.

**Implementation note (AUTHOR-002):** the outline gate as shipped diverges from the Option C sketch in three small ways:
- There is no separate `start_from_draft=True` entry point. Both graph runs share the same entry point, `generate_outline` — `OutlineGateService.generate_from_outline()` seeds `state["outline"]` (and `state["status"] = "outline_complete"`) from the persisted `ArticleDraft` before calling `graph.ainvoke()`, and the `outline_node` factory (`src/agents/content/nodes.py::make_outline_node`) short-circuits (no LLM call) whenever `state["outline"]` is already present. Section-drafting queries are regenerated from the (possibly editor-edited) outline on resume — this is intentional, not a gap: it keeps `generate_queries` as the single source of section queries so an edited outline never drafts against stale queries.
- The draft status used for the outline-only stop is the existing `DraftStatus.OUTLINE_COMPLETE`, not a new `outline_ready` value — no new enum member was needed since the session-level status (`awaiting_outline_review`) is what the frontend and status consumers key off, and the draft's own status already had a suitable value.
- The per-brief override is `ResearchSession.require_outline_approval` (`src/models/research_db.py`), set from the `POST /research/sessions` request body at session-creation time and read by `_run_full_pipeline`. It is a per-session flag, not yet a reusable per-brief default — a standalone per-brief override (settable independent of session creation) is deferred to AUTHOR-003.

**Implementation note (AUTHOR-004, 2026-08-21):** per-section regenerate is a graph-free re-entry: `SectionRegenerateService` calls `draft_one_section` (`src/agents/content/section_drafter.py`) directly with the live previous sections as context and never executes the compiled graph. No pipeline events are emitted (there is no `AgentStep` for an ad-hoc regenerate). Cost IS captured — the service binds `current_session_id` (to `draft.session_id`, the real research-session id; `provenance.research_session_id` is the topic id, see L-013) and `current_step_name="section_regenerate"` so `TrackedChatModel` writes one `llm_calls` row per regenerate. v1 returns un-humanized prose by design (one LLM call; AUTHOR-009 owns per-pass humanize). The public `section_id` contract was fixed to the outline index in the same ticket (L-013).

### Consequences

- Good: real progress and cancel for everyone; outline approval for those who opt in; SSE works unchanged after Celery offload; replay-on-connect survives refresh/restart.
- Good: no new orchestration surface in the frontend.
- Bad: two half-graphs must stay structurally in sync — mitigated by building both from one function with two booleans and a unit test asserting node/edge parity.
- Bad: a new session status (`awaiting_outline_review`) touches all status consumers (L-003) — enumerated in the AUTHOR-002 plan.
- Neutral: token-level streaming is deferred (§13.1 of the program plan); v1 granularity is step + section.

### Invariants

- Nodes surface progress only via `report_progress()` (or a future event bus); they never import HTTP modules.
- Events are additive telemetry; the database remains the source of truth. If publish fails, the node still completes.
- The SSE endpoint is read-only, idempotent, and rate-limited.
- The outline gate never mutates research findings; approving re-enters the graph at `generate_outline` with the stored (possibly editor-edited) outline seeded into state — the node no-ops on that outline, and `generate_queries` re-derives section queries from it.

## References

- `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §3, §5.1–5.3
- `src/agents/content/pipeline.py` (`_wrap_node`, `build_content_graph`), `src/api/routers/research.py` (`_run_full_pipeline`)
