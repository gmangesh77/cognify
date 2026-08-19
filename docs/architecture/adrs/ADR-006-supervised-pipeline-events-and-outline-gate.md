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
1. A `PipelineEventBus` (Redis pub/sub, channel `cognify:session:{id}`; `NullEventBus` when Redis is absent) receives typed `SessionEvent`s published from the existing node wrapper (`_wrap_node`) and from the draft/render nodes.
2. `GET /research/sessions/{id}/events` streams SSE: first a `replay` of persisted `agent_steps` + status, then live events until `done|error`. Polling remains as fallback.
3. Outline gate: `build_content_graph(stop_after_outline=True)` ends after `generate_queries` and persists the outline to `ArticleDraft(status=outline_ready)`; session → `awaiting_outline_review`; the user edits/approves via `GET/PUT/POST …/outline*`; `build_content_graph(start_from_draft=True)` enters at `draft_sections` seeded from the stored outline. Feature flag `COGNIFY_REQUIRE_OUTLINE_APPROVAL` (default `false`) + per-brief override.
4. Cancel: `POST …/cancel` sets `cancelled` and best-effort cancels the in-process task via a `SessionTaskRegistry`.

## Decision Outcome

Chosen option: **C**. It adds three thin, independently testable pieces, keeps nodes pure, and makes the producer location (API process vs worker) irrelevant to the consumer.

### Consequences

- Good: real progress and cancel for everyone; outline approval for those who opt in; SSE works unchanged after Celery offload; replay-on-connect survives refresh/restart.
- Good: no new orchestration surface in the frontend.
- Bad: two half-graphs must stay structurally in sync — mitigated by building both from one function with two booleans and a unit test asserting node/edge parity.
- Bad: a new session status (`awaiting_outline_review`) touches all status consumers (L-003) — enumerated in the AUTHOR-002 plan.
- Neutral: token-level streaming is deferred (§13.1 of the program plan); v1 granularity is step + section.

### Invariants

- Nodes publish via `deps.event_bus.publish(SessionEvent)` only; they never import HTTP modules.
- Events are additive telemetry; the database remains the source of truth. If publish fails, the node still completes.
- The SSE endpoint is read-only, idempotent, and rate-limited.
- The outline gate never mutates research findings; approving re-enters the graph with the stored outline and queries.

## References

- `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §3, §5.1–5.3
- `src/agents/content/pipeline.py` (`_wrap_node`, `build_content_graph`), `src/api/routers/research.py` (`_run_full_pipeline`)
