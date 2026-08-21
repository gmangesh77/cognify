# Epic 11 — Supervised Authoring: Implementation Plan

> **For agentic workers:** This is the *program-level* plan (one Epic, three phases, 15 tickets). It fixes architecture, data model, interfaces, sequencing and acceptance criteria. Following repo convention (Epic 10), each ticket gets its own bite-sized TDD plan in `docs/superpowers/plans/` when it is started — use `superpowers:writing-plans` then `superpowers:subagent-driven-development` per ticket. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Cognify's blind 2–5 minute article pipeline into a supervised, streaming, resumable authoring flow (brief → outline gate → streamed sections → per-section regenerate → cost visibility → drafts/resume), importing the *authoring model* of ImpactAI without importing its architecture.

**Architecture:** Keep the LangGraph pipeline as the single source of truth and add three thin layers around it: (1) DB-tailing of `agent_steps` (SSE) that nodes' persisted step rows are diffed against and an SSE endpoint streams from — Redis pub/sub optional later for lower latency; (2) an **outline gate** implemented as two graph runs around the existing `ArticleDraft` (no checkpointer needed), feature-flagged so the autonomous default is unchanged; (3) a first-class **Brief** table that the Generate modal reads/writes and the session references. Frontend gets an `useSessionEvents` SSE hook, an `OutlineReviewStep`, a Brief picker, and a cost badge — all reusing existing components (`UsageBadge`, `SectionContextToolbar`, `WordDiffView`).

**Tech Stack:** Python 3.12, FastAPI `StreamingResponse` (SSE), DB-tailing of `agent_steps` (SSE); Redis pub/sub optional later, LangGraph, SQLAlchemy async + Alembic, pydantic-settings; Next.js 16 / React 19 / TanStack Query 5, `fetch` + `ReadableStream` SSE consumer, Vitest + Testing Library, Playwright.

**Spec:** [`docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md`](../../architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md) §4 (UX gap analysis) and §6 (ranked adoptions). This plan implements §6 Tier 1 fully, Tier 2 items 7/8/9/10/14/15/16, and Tier 3 items 12/13/20 as a final phase.

## Global Constraints

- All functions < 20 lines, files < 200 lines, max 3 params (CLAUDE.md). Where an existing file is already over (e.g. `articles/[id]/page.tsx` 423 l., `VisualStudio.tsx` 523 l.), the ticket that touches it splits it.
- TDD: failing test first, ≥80 % coverage on new code; backend `uv run pytest tests/unit/ -q` (with `COGNIFY_ANTHROPIC_API_KEY` blanked — see memory note on Milvus hang), frontend `cd frontend && npx vitest run`.
- L-001 (`model_dump(mode="json")` for JSONB), L-002 (`parse_llm_json`), **L-003 (status consumers — every new session status must be added to all 8 consumer sites)**, L-006/L-007 (full-graph FakeLLM response counts).
- No new colour/font tokens; follow `frontend/DESIGN.md`. Catalogue-style data (pricing, presets) is fetched from the API, never mirrored in TS.
- Every new setting is `COGNIFY_*` in `src/config/settings.py`; nothing hardcoded.
- Feature flags default to **current behaviour** (`require_outline_approval=False`) so the self-driving pipeline is unchanged until a user opts in.
- One PR per ticket, off `develop`, never stacked (see PROGRESS.md lesson from PR #68/#69). AB#<id> in commits when Azure Boards items exist.
- New ADRs required before Phase A code: **ADR-006 Supervised pipeline (event bus + outline gate)**, **ADR-007 Brief as authoring input contract**.

---

## 1. Why this plan exists

The August 2026 review found Cognify architecturally superior but decisively behind ImpactAI on authoring UX: no streaming, no human checkpoint before ~3 minutes of drafting, no persistent brief, no per-section regenerate, no cost visibility, no drafts/resume, and a "Generate → toast → go find it" flow. All six gaps can be closed on top of the existing graph without adopting ImpactAI's wizard-as-architecture. Non-goals are listed in §2 to keep this honest.

## 2. Non-goals (this epic)

- Token-level streaming of prose (v1 streams **step and section granularity**; token deltas need streaming LLM plumbing through `TrackedChatModel` — recorded as follow-up §13.1).
- Whole-article WYSIWYG editor (TipTap) — evaluated after Phase B; section-level editing already exists.
- Multi-app "Strategist bridge" integration — no second app exists.
- Vendoring deck generation (Presenton/Gamma).
- Replacing `AsyncIODispatcher` with Celery is **INFRA-007**, scheduled *alongside* Phase A but tracked separately (it is infrastructure, not authoring).

## 3. Target architecture

```
                 ┌────────────────────────────────────────────────────────────┐
                 │  POST /research/sessions  (brief_id | inline brief)         │
                 │  → ResearchService.start_session(brief)                     │
                 │  → BackgroundTasks / (INFRA-007: Celery) _run_full_pipeline │
                 └───────────────┬────────────────────────────────────────────┘
                                 │ publishes
   research nodes ──┐            ▼
   content nodes  ──┼──► tail_session over agent_steps (DB polling + diff, no bus)
   (via _wrap_node) │            │  step_started / step_done / section_done /
                    │            │  visual_rendered / awaiting_outline_review /
                    │            │  done / error / usage
                    │            ▼
                    │   GET /research/sessions/{id}/events  (SSE, replay-then-live)
                    │            │
                    │            ▼
                    │   frontend useSessionEvents() → SessionProgress / OutlineReviewStep
                    │
   Outline gate (flag require_outline_approval):
     run 1: generate_outline → generate_queries → [persist ArticleDraft status=outline_ready,
            session=awaiting_outline_review] → END
     user:  GET/PUT /research/sessions/{id}/outline, POST …/outline/approve | /regenerate
     run 2: draft_sections → … → END   (entry point = draft_sections, outline from draft)
```

Key invariants:
- Nodes never know about SSE; they record step state via `ContentGraphDeps` (already exists for step recording) — `tail_session` polls and diffs `agent_steps`, no publish call in the node path.
- The SSE endpoint is read-only and idempotent: on connect it replays the current step list from `agent_steps` (so a page refresh shows state), then keeps tailing the same table (see §5.1 "as built").
- DB-tailing works unchanged from a worker or in-process; no separate bus to keep available.

## 4. Data model changes

### 4.1 `briefs` table (Alembic migration `add_briefs`)
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| owner_id | uuid | from JWT `sub` |
| name | text | user label ("Q3 security explainer") |
| title | text nullable | working title |
| description | text nullable | |
| target_audience | text nullable | |
| content_tone | text nullable | existing 5 values |
| preferred_angle | text nullable | |
| keywords | jsonb (list[str]) | |
| content_type | text | `article\|how_to\|analysis\|report` (existing `ContentType` enum) |
| length_target | text | `short\|medium\|long\|pillar` → word budgets in settings |
| structural_diagram_mode | text | `illustration\|mermaid` |
| audience_persona | text nullable | existing 8 keys (image planner) |
| created_at / updated_at | timestamptz | |

Pydantic: `Brief`, `BriefCreate`, `BriefUpdate` in `src/models/brief.py`. `research_sessions.brief_id uuid nullable FK` (+ migration). `CreateResearchSessionRequest` accepts **either** `brief_id` **or** the existing inline fields (inline path is kept for backwards compatibility and for "Create & Generate" from the topic modal, which will auto-create a brief).

### 4.2 Session status
Add `awaiting_outline_review` to the research session status set. Consumers to update (L-003): `frontend/src/types/research.ts`, `session-filters.tsx`, `use-research-sessions.ts` (polling set), `session-status-badge.tsx`, `session-card.tsx` (progress map), `src/db/repositories.py` list filter map (`repositories.py:147-149`), `src/services/content/__init__.py::_load_session` whitelist, `session-steps.tsx` labels. Add `content_image_planner`, `content_image_render`, `content_outline_review` to `STEP_LABELS` (currently missing).

### 4.3 `ArticleDraft`
Add `DraftStatus.OUTLINE_READY` (between none and `DRAFT_COMPLETE`); `outline` is already stored. No column change (status is a string).

### 4.4 `canonical_articles`
- `status text default 'draft'` (`draft | in_review | approved | published`) — migration `add_article_status`. Note: frontend currently hardcodes `status: "complete"` in `use-article.ts:79`; that mapping is replaced.
- Editable metadata: `title, subtitle, seo_title, seo_description, keywords, slug` already exist on the model; add `PATCH` support only.

### 4.5 Usage
No new table: `llm_calls` already has model + tokens per call per session; image renders are recorded in `image_render` step output. Add `LlmPricing` map to settings (`COGNIFY_LLM_PRICING_JSON`, default table for Haiku/Sonnet/gpt-image-1/gemini) and a pure `compute_session_cost(calls, renders, pricing) -> SessionUsage`.

### 4.6 Prompt overrides (Phase C)
`prompt_overrides(id, owner_id, prompt_key, template, updated_at)`; defaults stay in code as a registry `src/agents/prompts/registry.py` (`PromptTemplate(key, template, variables)`).

## 5. Backend changes

### 5.1 Session events (as built in AUTHOR-001 — supersedes the Redis design below)

> **Built:** `src/utils/step_progress.py` (`report_progress()` contextvar bound by `_wrap_node`; draft node reports `sections_done/total/current_section`), `src/models/session_events.py` (`SessionEvent`, `TERMINAL_STATUSES`), `src/services/session_events.py` (`diff_steps`, `tail_session`, `TailOptions`), `src/api/routers/session_events.py` (`GET /research/sessions/{id}/events` SSE + `GET …/article`), settings `COGNIFY_SESSION_EVENTS_{POLL,KEEPALIVE,COMPLETE_GRACE,MAX}_SECONDS`, `ArticleRepository.find_by_session`. Transport is **DB tailing** (no Redis); see ADR-006 "Transport (v1)". The original Redis-bus sketch is kept below for the optional latency upgrade.

### 5.1a `src/services/pipeline_events.py` (optional future upgrade)
```python
class SessionEvent(BaseModel):
    session_id: UUID
    type: Literal["step_started","step_done","step_failed","section_done",
                  "visual_rendered","awaiting_outline_review","usage","done","error"]
    step: str | None = None          # e.g. "content_draft"
    payload: dict[str, JsonValue] = {}
    ts: datetime

class EventBus(Protocol):
    async def publish(self, event: SessionEvent) -> None: ...
    def subscribe(self, session_id: UUID) -> AsyncIterator[SessionEvent]: ...

class RedisEventBus(EventBus): ...   # channel f"cognify:session:{id}", JSON via model_dump(mode="json")
class NullEventBus(EventBus): ...    # publish no-op, subscribe yields nothing
```
Wired in `create_app()` → `app.state.event_bus`; `ContentGraphDeps` gains `event_bus: EventBus | None`; `_wrap_node` publishes `step_started/step_done/step_failed` next to `_record_step/_complete_step`; the research orchestrator's step recorder does the same for research steps; the draft node publishes `section_done {index, heading, word_count}` after each section (it already loops sections); `image_render` publishes `visual_rendered {spec_id, url}`.

### 5.2 SSE endpoint — `src/api/routers/session_events.py` (new)
`GET /api/v1/research/sessions/{id}/events` (editor-or-above, `30/minute`): `StreamingResponse(media_type="text/event-stream")`; first yields one `replay` event with the current `agent_steps` + session status, then iterates `bus.subscribe(id)` until `done|error`, with a 15 s `: keepalive` comment. Auth: bearer header (frontend uses `fetch`, not `EventSource`).

### 5.3 Outline gate — `src/services/content/outline_gate.py` (new) + `pipeline.py`
- `build_content_graph(..., stop_after_outline: bool)` — when true, edges end after `generate_queries`; `build_content_graph(..., start_from_draft: bool)` — entry point `draft_sections`, state seeded with the stored outline (`ArticleDraft.outline`) and queries.
- `ContentService.generate_outline_only(session_id) -> ArticleDraft` (status `outline_ready`), `ContentService.update_outline(draft_id, outline: ArticleOutline)`, `ContentService.regenerate_outline(draft_id, instruction: str | None)`, `ContentService.generate_from_outline(draft_id) -> CanonicalArticle`.
- `_run_full_pipeline` (research router) branches on `settings.require_outline_approval` **or** the brief's `require_outline_approval` flag: research → outline-only → set `awaiting_outline_review` → publish event → return. `POST /research/sessions/{id}/outline/approve` schedules `generate_from_outline` in the background and sets `generating_article`.
- Endpoints (`src/api/routers/outline.py`, new): `GET …/outline`, `PUT …/outline` (body `ArticleOutline`; validates ≥1 section, unique headings), `POST …/outline/regenerate {instruction}`, `POST …/outline/approve`, `POST …/cancel` (any active status → `cancelled`, best-effort `asyncio.Task.cancel()` via a `SessionTaskRegistry` kept in `app.state`).

### 5.4 Briefs — `src/services/briefs.py`, `src/db/repositories_briefs.py`, `src/api/routers/briefs.py`
CRUD `GET/POST /briefs`, `GET/PATCH/DELETE /briefs/{id}`, `POST /briefs/{id}/duplicate`. `ResearchService.start_session` accepts `Brief` and copies its fields onto the session (existing columns) + `brief_id`. Topic analyze (`/topics/analyze`) response gains `suggested_brief: BriefCreate` so the modal can prefill.

### 5.5 Section regenerate — `POST /content/section-regenerate`
Body `{article_id, section_index, instruction: str | None}`. Loads the draft's outline + previous sections' markdown as context, runs `make_draft_node`'s per-section function for one section (extract `draft_one_section(llm, retriever, ctx) -> str` from the draft node — it must be importable without the graph), runs the anchor validator (existing `section_anchors.py`) against the *old* section to preserve `data-spec-id`s, writes a `section_versions` row with `source="regenerate"`, returns `{markdown, diff}` using the existing `word_diff`. Rate-limit `10/minute`.

### 5.6 Usage — `GET /research/sessions/{id}/usage` and `GET /articles/{id}/usage`
`SessionUsage {llm_calls, input_tokens, output_tokens, images, cost_usd, by_operation: list[{op, cost_usd}]}` computed from `llm_calls` + step outputs with the pricing map. Pure function + repo query; no writes.

### 5.7 Article metadata + status — `PATCH /articles/{id}`
`ArticlePatch {title?, subtitle?, seo_title?, seo_description?, keywords?, slug?, status?}` (editor-or-above). Slug uniqueness check; SEO field length **warnings** (not errors) returned in response. `POST /articles/{id}/seo/regenerate {field}` reuses the existing SEO service for one field.

### 5.8 Model tiering — settings
`COGNIFY_LLM_MODEL_BY_STEP` (JSON map step→model, default `{}` = current single model). `TrackedChatModel` factory reads it per node name.

### 5.9 Auth hardening (small)
`get_current_user` re-reads role/active from DB with a 30 s in-memory TTL cache; deactivated users get 401 within 30 s.

### 5.10 Embedding warm-up
`EmbeddingService.warm_up_in_background()` at lifespan; `try_embed()` returns `None` while cold; retriever skips vector search (keyword-only) when `None`. Complements PR #72.

### 5.11 Phase C — Persona voice loop, prompt registry, LinkedIn repurpose
- `src/services/persona/` — `fingerprint.py` (textstat-based dims: sentence length mean/std, FK grade, TTR, contraction rate, hedge/booster rate, punctuation per 1k words, paragraph length), `store.py` (`personas`, `persona_samples` tables; embeddings via existing `EmbeddingService`, similarity via Milvus collection `persona_samples`), `scoring.py` (sigma per dimension, confidence-weighted 0–100), `prompt_block.py` (confidence-gated instructions + few-shot block). Graph: new nodes `score_voice` → conditional `fix_voice_deviations` (max 1 loop) inserted after `humanize`, only when `state.persona_id` is set.
- `src/agents/prompts/registry.py` + `prompt_overrides` + `GET/PUT/DELETE /prompts/{key}`; every node reads via `resolve_prompt(key, owner_id)`.
- `src/services/publishing/linkedin/repurpose.py` — `CanonicalArticle → LinkedInPostDraft` (hook + 3 beats + CTA, ≤3,000 chars) as a Transformer per ADR-004; `POST /articles/{id}/repurpose/linkedin`; small modal in article page.

## 6. Frontend changes

- `frontend/src/lib/sse/consumeSse.ts` — `consumeSse(url, {token, signal, onEvent})`: `fetch` + `getReader()` + `TextDecoder(stream:true)`, line-carry buffer across chunks, `data:` parse, JSON events, ignores `:` comments, resolves on `done|error`, rejects on network error; unit-tested with a mocked `ReadableStream`.
- `frontend/src/hooks/use-session-events.ts` — `useSessionEvents(sessionId) → {steps, sections, status, usage, lastEvent, error, reconnect}`; reconnects with backoff (1s→30s) while status is active; falls back to the existing 5 s poll if SSE fails twice.
- `components/research/session-progress.tsx` (new, replaces the %-by-status bar): real step list with states, per-section rows as `section_done` arrives, ETA text from settings, **Cancel** button.
- Generate flow: `GenerateArticleModal` → on success **router.push(`/research/${id}`)** (new session detail route `app/(dashboard)/research/[id]/page.tsx`, ≤200 l.) instead of a toast.
- `components/research/outline-review-step.tsx` — editable outline (heading text, key points, ↑/↓, add, delete, "Regenerate outline" with instruction), **Approve & write** primary CTA; visible when status `awaiting_outline_review`.
- `components/briefs/brief-picker.tsx` + `brief-form.tsx` + `lib/api/briefs.ts` + `hooks/use-briefs.ts`; `GenerateArticleModal` becomes: pick existing brief | new brief (prefilled from topic analysis) | edit fields; "Save as brief" checkbox; length + content type selects.
- `SectionContextToolbar` gains **Regenerate** (with optional instruction popover, reusing `AIRewritePopover`'s layout and `WordDiffView` accept/reject); on accept calls existing `section-update`.
- `UsageBadge` (existing, `components/visuals/UsageBadge.tsx`) reused in session progress header and article sidebar via `hooks/use-session-usage.ts`.
- Article page: `article-header-editor.tsx` (title/subtitle/SEO fields with 50–60 / 150–160 char counters and per-field ↻), status pill + transitions (draft → in_review → approved → published), `PATCH` via `useMutation`; **refetch after `onPersisted`** (fixes stale view); autosave of the inline textarea draft to `localStorage` keyed `cognify:draft:{articleId}:{sectionIndex}` with an "unsaved draft" chip; `articles/[id]/page.tsx` split into `article-page-shell.tsx` + `article-editing-state.ts` (custom hook) to get under 200 l.
- Articles list: status filter pills + "Resume" for `generating*/awaiting_outline_review/failed` sessions (links to `/research/{id}`).
- Settings: Prompts tab (Phase C), Personas tab (Phase C), model-by-step (Phase B, read-only display + edit JSON).
- Replace hand-rolled toasts with a single `components/ui/toaster.tsx` (context + `useToast()`), used by the 4 pages that currently duplicate `setTimeout` toasts.

## 7. Testing strategy

- Backend unit: `tests/unit/services/test_pipeline_events.py` (Redis via `fakeredis` or an in-memory bus double), `test_outline_gate.py` (FakeLLM, both graph halves, status transitions), `test_briefs.py`, `test_section_regenerate.py` (anchor preservation), `test_usage.py` (pricing math), `test_article_patch.py`, `test_persona_scoring.py`. FakeLLM response counts per L-007 for each half-graph.
- Backend integration: `tests/integration/api/test_session_events.py` (httpx streaming client reads ≥3 events), `test_outline_flow.py` (create → awaiting → PUT → approve → article), `test_briefs_api.py`.
- Frontend: `consumeSse.test.ts` (chunk boundaries, keepalive comments, abort), `use-session-events.test.tsx` (fallback to polling), `outline-review-step.test.tsx`, `brief-picker.test.tsx`, `article-header-editor.test.tsx` (char counters), `session-progress.test.tsx`.
- Playwright: extend the smoke lane with `create-article.spec.ts` (mocked backend SSE via route interception): brief → outline approve → sections appear → article page.

## 8. Feature flags & backwards compatibility

- `COGNIFY_REQUIRE_OUTLINE_APPROVAL=false` (global default) + per-brief override. False ⇒ identical to today's flow but with real progress + cost + cancel.
- SSE endpoint is additive; polling stays.
- Inline session fields remain accepted; `brief_id` optional.
- `canonical_articles.status` defaults `draft` for existing rows via migration; publish sets `published`.

## 9. Sequenced delivery (3 phases / 15 tickets / ~70 SP)

Ticket IDs are proposed as `AUTHOR-0xx`; INFRA-007 runs in parallel with Phase A.

### Phase A — Supervised loop (≈25 SP)
| Ticket | Title | SP | Depends on |
|---|---|---:|---|
| ADR-006/007 | ADRs: supervised pipeline; Brief contract | 1 | — |
| AUTHOR-001 | Session events (DB-tailing) + SSE endpoint + `useSessionEvents` + `SessionProgress` + session detail route + auto-navigate — **DONE (merged `06439e9`)** | 8 | ADRs |
| AUTHOR-002 | Outline gate: half-graphs, `awaiting_outline_review`, outline endpoints, cancel, `OutlineReviewStep` (flagged) — **DONE (PR #73, `30f1a36`)** | 8 | AUTHOR-001 |
| AUTHOR-003 | Brief model/table/CRUD + Generate modal rework (picker, length, content type, save-as-brief) + topic-analyze `suggested_brief` — **DONE (`feature/AUTHOR-003-brief`)** | 5 | ADRs |
| AUTHOR-004 | Section regenerate endpoint + toolbar action + diff accept | 3 | — |
| AUTHOR-005 | Session/article usage endpoint + pricing settings + `UsageBadge` in progress header & article sidebar | 3 | AUTHOR-001 |
| INFRA-007 | `CeleryDispatcher` + worker wiring for `_run_full_pipeline`; DB-tailing works unchanged from a worker | 5 | AUTHOR-001 |

**Phase A acceptance criteria**
- [x] Clicking Generate navigates to `/research/{id}` and shows live step + section progress within 2 s of each event; no fake percentages remain in `session-card.tsx`. *(AUTHOR-001; verified live)*
- [x] With `require_outline_approval=true`, the run stops at `awaiting_outline_review`; the user can edit/reorder/add/delete/regenerate sections and approve; the final article reflects the edited outline (headings match). With the flag false, behaviour is byte-identical to today except progress/usage/cancel. *(AUTHOR-002; covered by endpoint flow tests — live smoke deferred until the stack's Anthropic key is refreshed)*
- [x] Cancel moves any active session to `cancelled` within 5 s and no further steps are recorded. *(AUTHOR-002; tested incl. cancel during running drafting)*
- [x] A Brief can be created from topic analysis, reused on a second topic, and its fields appear on the session and article; "Create & Generate" from the topic modal forwards keywords + diagram mode (fixes the current drop). *(AUTHOR-003; picker/save-as-brief covered by Vitest; create-from-analysis via `suggested_brief`; session/article carry `brief_id`, `content_type`, `length_target`)*
- [ ] Regenerate on a section returns a diff, preserves all `data-spec-id` anchors, appends a `section_versions` row with `source=regenerate`.
- [ ] Usage badge shows `$ · tokens · images` matching a hand-computed value from `llm_calls` for a FakeLLM run with configured pricing.
- [ ] SSE unavailable ⇒ hook reaches `error`, polling still works.

### Phase B — Control & trust (≈20 SP)
| Ticket | Title | SP | Depends on |
|---|---|---:|---|
| AUTHOR-006 | `PATCH /articles/{id}` + `article-header-editor` (title/SEO counters/↻) + refetch-after-save + textarea autosave chip | 5 | — |
| AUTHOR-007 | Article `status` (draft/in_review/approved/published) + list filters + Resume links + publish sets `published` | 3 | AUTHOR-006 |
| AUTHOR-008 | Length target + content type through outliner (per-section word budgets) | 3 | AUTHOR-003 |
| AUTHOR-009 | Humanize per-pass streaming (score per pass, sentence-level accept/reject in `HumanizationDiffPanel`) | 3 | AUTHOR-001 |
| AUTHOR-010 | Model tiering per step (`COGNIFY_LLM_MODEL_BY_STEP`) + Settings display | 2 | — |
| INFRA-008 | Embedding warm-up with graceful degradation; live role/status re-check with 30 s cache; shared `useToast` replacing hand-rolled toasts; split `articles/[id]/page.tsx` & `VisualStudio.tsx` under 200 l. | 4 | — |

**Phase B acceptance criteria**
- [ ] Title/SEO edits persist and are reflected in Ghost/Medium/LinkedIn payloads (transformer tests updated).
- [ ] Article list filters by status; publishing flips status; a `failed` session shows Resume → session page with the error step highlighted.
- [ ] Choosing `short` yields an outline whose section budgets sum within ±15 % of the configured target; `pillar` likewise.
- [ ] Humanize preview streams ≥2 events and per-sentence accept/reject round-trips through `section-update` with anchors intact.
- [ ] Deactivating a user in DB blocks their next request within 30 s without restart.
- [ ] No page/component file in `frontend/src` over 200 lines after INFRA-008.

### Phase C — Differentiation (≈25 SP)
| Ticket | Title | SP | Depends on |
|---|---|---:|---|
| AUTHOR-011 | Persona voice engine v1: personas + samples, fingerprint, scoring, prompt block, `score_voice`/`fix_voice_deviations` nodes (flagged), Settings Personas tab, voice-match chip on article | 13 | Phase A |
| AUTHOR-012 | Prompt registry + per-user overrides + Settings Prompts tab (view/edit/reset, variable validation) | 5 | — |
| AUTHOR-013 | LinkedIn repurpose transformer + modal (hook/beats/CTA, ≤3,000 chars, publish via existing adapter) | 5 | AUTHOR-007 |
| AUTHOR-014 | Playwright `create-article.spec.ts` covering brief → outline → article with mocked SSE | 2 | Phase A |

**Phase C acceptance criteria**
- [ ] A persona built from ≥5 samples yields a fingerprint with per-dimension `{value, stddev, confidence}`; generation with that persona scores ≥ threshold or triggers exactly one fix pass; the article stores `voice_match_score` and `few_shot_sample_ids`.
- [ ] Editing a prompt override changes the next run's prompt (visible in pipeline-debug); reset restores the default; templates with missing variables are rejected at save.
- [ ] Repurpose produces a ≤3,000-char LinkedIn post that publishes through the existing LinkedIn adapter and is tracked as a publication.
- [ ] Playwright spec passes in the opt-in CI lane.

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| New session status breaks consumers (L-003) | AUTHOR-002 plan enumerates all 8 sites; grep gate in PR checklist |
| SSE through in-process `BackgroundTasks` still exposes the API-freeze risk | INFRA-007 in Phase A; transport is DB-tailing from day 1 so moving the producer to a worker changes nothing on the consumer side |
| Half-graph split diverges from full graph over time | Both are built by the same `build_content_graph` with two booleans; a unit test asserts node/edge sets are the same minus the split point |
| Persona engine adds heavy deps (spaCy) | Use `textstat` + regex only in v1; feature-flag the nodes; measure latency in `llm_calls` |
| Brief vs inline fields drift | Session always denormalises brief fields at start; brief edits never mutate past sessions |
| Frontend `fetch`-SSE and Next proxy buffering | Frontend calls the API origin directly (already does via `apiClient`), no Next rewrite in the path |
| Scope creep toward a full wizard | Non-goals §2; whole-doc editor decision deferred to a post-Phase-B review |

## 11. Effort summary

| Phase | SP | Calendar (1 dev + agents) |
|---|---:|---|
| A | 25 (+5 INFRA-007) | ~2.5 weeks |
| B | 20 | ~2 weeks |
| C | 25 | ~2.5 weeks |
| **Total** | **~75** | ~7 weeks |

## 12. Sign-off checklist (before Phase A code)

- [x] ADR-006 and ADR-007 written and reviewed
- [ ] Azure Boards: Epic 11 + AUTHOR-001…014 + INFRA-007/008 created; PROGRESS.md/BACKLOG.md rows added (done in this PR)
- [ ] Decision confirmed: outline gate default **off**
- [x] Decision confirmed: v1 streaming granularity = step + section (token streaming = follow-up)
- [ ] In-memory `ResearchService` double (done) approved as the unit-test strategy for the event bus

## 13. Follow-ups recorded (out of scope)

### 13.1 Token-level streaming
Requires `TrackedChatModel` to expose `astream` and the draft node to publish `section_delta` events; adds LLM streaming to `llm_calls` accounting. Do after Phase A proves the event bus.

### 13.2 Whole-article rich-text editor
Only if section-level editing proves insufficient. Must keep anchor validation; use a real markdown extension, not regex round-trip.

### 13.3 Humanize learning loop
Record which slop-fix transformations survive user edits (`section_versions` diff) and re-prioritise the fixer (ImpactAI `humanize_learner` idea).

### 13.4 Job status store
Redis hash + TTL behind `GET /jobs/{id}` — natural companion to INFRA-007 once Celery exists.

## 14. References
- Review: `docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md`, `docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW.md`
- Code seams: `src/api/routers/research.py:78-161` (kickoff + `_run_full_pipeline`), `src/agents/content/pipeline.py:90-273` (`_wrap_node`, graph), `src/services/content/__init__.py:100` (`generate_full_article`), `src/services/task_dispatch.py`, `src/models/llm_call.py`, `src/db/repositories.py:147-149` (status filter map), `frontend/src/components/topics/generate-article-modal.tsx`, `frontend/src/components/research/session-card.tsx`, `frontend/src/app/(dashboard)/articles/[id]/page.tsx`, `frontend/src/components/visuals/UsageBadge.tsx`
- Precedent: `docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md` (Epic 10 program plan)
