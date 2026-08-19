# Cognify vs ImpactAI — August 2026 Review

> **Date:** 2026-08-18
> **Compared:** Cognify `develop` @ `a0c1c5a` (post PR #72) vs ImpactAI/ContentAI `development` @ `eddee66d` (2026-08-14)
> **Supersedes / extends:** [`COGNIFY_VS_IMPACTAI_REVIEW.md`](./COGNIFY_VS_IMPACTAI_REVIEW.md) (May 2026, `feat/content-hub`). Everything that review recommended on image generation has since shipped in Cognify (Epic 10 + PRs #64–#72), so this document does **not** re-cover the image stack. It focuses on the two things that moved: (1) ImpactAI's **content-creation UX**, which is the reason for this review, and (2) the ~433 commits of new ImpactAI backend (Persona Engine, Strategist bridge, streaming, versions, cost admin, Presenton).
> **Method:** three read-only code sweeps (ImpactAI frontend, ImpactAI backend, Cognify content-creation surface). Line counts are `wc -l` on the stated commits.

---

## 1. TL;DR

| | Cognify | ImpactAI |
|---|---|---|
| **What it is** | Autonomous pipeline: trend → parallel research → RAG-grounded article → visuals → multi-platform publish. Dashboard *observes* the pipeline. | Hands-on writing workbench: wizard-driven, streaming, section-by-section, human in the loop at every step. Pipeline *serves* the editor. |
| **Architecture** | Clearly better — service/repository layers, LangGraph, CanonicalArticle boundary, Alembic, pydantic-settings, structlog, 1,419 backend + ~357 frontend tests, ADRs. | Clearly worse and getting worse — 9,018-line `generate.py`, 7,668-line wizard component, raw SQL re-applied at boot, ~0 tests, 178 `os.getenv`, secrets in a vendored subtree. |
| **Content-creation UX** | Weak — two modals → toast → "check the Research page" → fake % bar → 2–5 min blind wait → article appears elsewhere. Editing = per-section `<textarea>`. | Strong — persistent brief, editable outline, SSE-streamed sections with per-section regenerate+feedback, Refine→Validate→Polish, humanize with word-diff accept/reject, three-layer resume, live cost badge, review/approval workflow. |
| **Verdict** | Keep Cognify's architecture. **Import ImpactAI's authoring *model* (not its code)**: streaming, brief object, outline gate, per-section regenerate, resume, cost badge, persona/voice. Every one of those maps onto a LangGraph interrupt or a thin SSE layer over existing nodes. | Nothing in ImpactAI's *implementation* should be copied literally — the patterns are good, the files are not. |

**Top 5 adoptions, in order:** (1) SSE streaming of pipeline steps + section text, (2) outline approval gate via LangGraph `interrupt`, (3) a saved **Brief** object (persona/audience/tone/keywords/angle) reused across runs, (4) per-section *Regenerate with feedback* + editable outline (add/reorder/delete), (5) live per-session cost badge. Details and phasing in §6.

---

## 2. What changed since the May review

**Cognify (May → Aug):** Epic 10 shipped (style catalogue, providers, MinIO, planner, Visual Studio, per-section prose editing + AI rewrite + history, humanization diff panel), Mermaid toggle + server-side render, embedding model baked into image. The visual-generation gap the May review called "5–10×" is closed. Cognify is now *ahead* on visuals architecture (planner owns visuals, spec IDs anchor into markdown, ADR-bounded).

**ImpactAI (May → Aug, 433 commits, +1.16M lines incl. vendored Presenton):**
- **Persona Engine** — stylometric voice fingerprint (40 dims, spaCy/textstat), pgvector few-shot retrieval, sigma-based voice-match scoring, targeted sentence auto-fix, provenance of sample IDs (`services/persona_engine/`, 2,087 lines + 954-line router).
- **Strategist bridge** — server-to-server integration with a separate "Content Strategist" app: briefs → prefilled wizard → Send-for-Review / Publish with approval gate.
- **Streaming everywhere** — POST-SSE for outline/section/humanize with a robust client consumer (pause/abort/chunk-carry).
- **Content versions**, audit log, notifications, module-level RBAC with email-link approvals, admin cost dashboard incl. external (Presenton) cost sync, user-editable prompt registry.
- **Presenton** (open-source deck generator) vendored into the monorepo + Gamma; LinkedIn Post/Pulse dedicated wizards; RichTextEditor (TipTap) with tables.

---

## 3. Architecture comparison (updated scorecard)

| Dimension | Cognify | ImpactAI | Winner |
|---|---|---|---|
| Layering | Route → Service → Repository → DB; LangGraph nodes for AI work | Routers call `services/db.py` directly; "services" are utility modules; prompts, SQL, retries, SDK calls inline in 9k-line routers | **Cognify** |
| Data / migrations | SQLAlchemy async + Alembic (versioned) | psycopg3 raw SQL; `schema.docker.sql` (`CREATE TABLE IF NOT EXISTS` + `ALTER … ADD COLUMN IF NOT EXISTS`) re-run on **every boot**, failures logged at DEBUG; two hand-synced schema files (Supabase vs plain PG) | **Cognify** |
| Config | pydantic-settings, `COGNIFY_*` prefix | 178 scattered `os.getenv`; model IDs as string literals in ~40 places | **Cognify** |
| Background work | FastAPI `BackgroundTasks` in-process (known freeze risk, PR #72 mitigated one cause); `AsyncIODispatcher` with Celery seam | `asyncio.create_task` fire-and-forget in the web process; Redis job store w/ 1 h TTL; Celery scaffolded with one task | **Tie (both weak)** — Cognify has the cleaner seam to fix it |
| Auth | RS256 JWT + RBAC (admin/editor/viewer), Fernet-encrypted keys | HS256 shared secret w/ insecure default, Supabase JWT, Google, demo tokens; **live re-check of role/status per request** (good); JWT in iframe query string, non-constant-time key compare | **Cognify** (but see §5 for one ImpactAI idea) |
| Observability | structlog + correlation IDs, `llm_calls` table, pipeline-debug page | stdlib logging, request-id middleware, two overlapping cost trackers | **Cognify** |
| Cost tracking | `llm_calls` table (tokens/duration per call), no $ or per-session rollup, no UI badge | `MODEL_PRICING` table, `api_usage` rows, per-session `UsageBadge`, admin cost dashboard by user/day/op, external cost sync | **ImpactAI** |
| Testing | 1,419 backend unit + ~357 Vitest + 1 Playwright; TDD culture | 3 backend test files (684 lines, ~1 real unit test); Playwright e2e with effectively **no `expect()`**; CI gate = ruff + `import main` | **Cognify** (by a mile) |
| Frontend architecture | Next 16 / React 19 / Tailwind v4 / TanStack Query; DESIGN.md tokens mostly honoured; hand-rolled modals/toasts; biggest file 523 lines | Next 14 / React 18; zustand+persist; **~4,956 inline `style={{}}`**, Tailwind config empty; wizards of 7,668 / 5,287 / 5,067 / 4,529 lines with 40–93 `useState` each; V1 and V2 web-page wizards both live | **Cognify** |
| Design system | Yes (DESIGN.md, Pencil source, tokens) | No (hex literals threaded by hand; `wizardShell` primitives exist but the main wizard ignores them) | **Cognify** |
| Content model | `CanonicalArticle` (ADR-003) → Transformer/Adapter per platform (ADR-004) | `content` row with `raw_text/humanized_text/final_text` + JSON `creation_state`; per-wizard slices | **Cognify** |
| Publishing | Ghost, Medium, LinkedIn adapters + tracking (WordPress open) | DOCX/PDF/HTML/MD export, HubSpot/CMS HTML upload, LinkedIn queue, PPTX/Gamma | Different scopes; Cognify for CMS, ImpactAI for documents/decks |
| Research grounding | Parallel research agents, Milvus RAG, citations, key claims | SERP snapshot (Serper) for SEO brief; no RAG | **Cognify** |
| Voice / persona | 8 fixed audience-persona keys, image-planner only | Measured voice fingerprint + few-shot + scoring loop; brand personas from crawl | **ImpactAI** |
| Humanization | Slop scorer + structure-aware rewrite (CONTENT-007) + diff panel (DASH-007) | Rule preprocessor + iterative Claude passes + GPTZero/Copyleaks scoring + **learning loop** (which transformations survive edits) + word-diff UI | **ImpactAI** on loop sophistication; Cognify on structural safety |
| Prompt management | Prompts in code | `prompt_defaults.py` (2,153 lines, ~30 named templates w/ `{{vars}}`) + per-user overrides + reset | **ImpactAI** (as a product feature) |
| Multi-app integration | None | Strategist bridge (proxy endpoints hold key; deep links carry ids; inbound callback) | **ImpactAI** |
| Content-creation UX | See §4 | See §4 | **ImpactAI, decisively** |

Bottom line unchanged from May: **Cognify is the better platform; ImpactAI is the better authoring product.** What's new is that ImpactAI has added *three* genuinely novel product ideas (Persona Engine, Strategist bridge, editable prompt registry) alongside its UX lead — and its engineering debt has roughly doubled.

---

## 4. Content-creation UX — the deep comparison

This is the section that motivated the review. Walked step-by-step, "what does the user do, see, and control".

### 4.1 Step-by-step

| Stage | Cognify today | ImpactAI today | Gap |
|---|---|---|---|
| **Entry** | Topics page → *Generate* on a card, or *Create Topic* modal (`topics/page.tsx`, `create-topic-modal.tsx` 251 l.) | `/dashboard/create` → `CreateScreen` (5,287 l.) — content-type picker gated on choosing a brand persona; dedicated wizards dispatched by registry (`lib/createWizardRouter.ts`) | Cognify has one content type (blog article) and no persona gate |
| **Brief / details** | `GenerateArticleModal` (277 l.): description, keywords, audience, tone (5 fixed), angle, diagram style. Auto-fill via `/topics/analyze` with per-field ↻. **Not persisted** — retyped every run. | Topic textarea → *Suggest Titles* / *Enhance Prompt*; keyword chips with intent colour + volume; per-content-type custom fields (`CT_FIELDS`); tone from industry list; length Short/Medium/Long/Pillar; compliance banner (healthcare/finance); Persona Engine voice select; strategist brief prefill | Cognify lacks: length, content type, persona/voice, saved/reusable brief, keyword intelligence, prefill from an upstream brief |
| **SEO & outline** | None. Outline is generated inside the pipeline and never shown before drafting. | `SeoBriefStep` (431 l.): meta title 50–60 counter, meta description 150–160, H1, slug, each with ↻; recommended H2s; SERP snapshot. **Editable outline**: per-section ↑/↓/✎/🗑, add section, regenerate outline | **Biggest single UX gap.** Cognify has zero human checkpoint before ~3 minutes of drafting |
| **Generation** | `POST /research/sessions` → toast "Research started… check Research page" → user navigates manually → list card doesn't auto-refresh (staleTime 15 min); expanded card polls 5 s; **progress bar is a hard-coded % per status** (`planning`=10, `researching`=35 …); step timeline shows names (new planner steps unlabeled) | Sequential per-section **SSE streaming** into cards with caret + live word count; per-section *Edit* (TipTap), *Infographic*, **Regenerate with optional feedback**; pause/abort; `beforeunload` guard | Cognify: no streaming, no cancel, no per-section action, no auto-navigation |
| **Review** | Article detail page (`articles/[id]/page.tsx` 423 l.): hover toolbar → textarea edit / AI rewrite (4 tone presets, word-diff) / HTML refine / history restore; Visual Studio panel; humanize preview | Whole doc in RichTextEditor; AI-detection score; **Refine → Validate → Polish** staged buttons; Save Draft / Save to Library / Submit for Review / Publish (approval gate) | Cognify's per-section tooling is actually comparable or better *per section*; it lacks whole-doc editing, title/SEO editing, add/reorder/delete sections, regenerate-from-scratch, drafts vs final state |
| **Humanize** | `HumanizationDiffPanel` (preview + slop score) | SSE humanize with per-pass detector score tiles, activity log, cancel, paragraph-aligned word-diff compare modal, Accept / Keep original | Cognify has the diff; lacks iteration visibility and accept-per-change |
| **Persist / resume** | Nothing client-side; server has per-section `section_versions` only. Textarea draft lost on navigation. | Three layers: sessionStorage per type, zustand-persist (base64 stripped, quota-guarded), server `creation_state` JSON snapshot on step change → `?resume=<id>` from Library | Cognify has no draft concept and no resume |
| **Cost** | None visible (data exists in `llm_calls`) | `UsageBadge`: `$ · tokens · images` per session, expandable by op | Easy win for Cognify |
| **Publish** | `PublishModal` (78 l.): 4 checkboxes, sequential POST, toast | Export DOCX/PDF/HTML/MD, HubSpot/CMS upload, LinkedIn queue; approval-gated Publish | Cognify: no per-platform preview, no schedule, no draft/publish state |
| **After** | Article list (no status filter, 43 l.) | Library (1,245 l.): filters all/published/humanized/draft/archived, search, review-status chips, Resume, voice-match chip, export, archive | Cognify has no library semantics beyond a list |

### 4.2 What is genuinely good about ImpactAI's authoring UX (ranked)

1. **Human-in-the-loop by construction.** Every expensive step is preceded by something the user can inspect and change (brief → SEO/outline → sections → review → humanize). The wizard is the state machine.
2. **Streaming with per-section agency.** Text appears in seconds; a bad section is regenerated with a one-line note instead of re-running everything.
3. **The Brief is a first-class object.** Persona, audience, keywords, tone, length, and an upstream strategist brief all feed one prefill; it survives reloads and can be resumed from the Library.
4. **Trust surfaces:** AI-detection score, voice-match %, per-pass humanize scores, word-diff accept/reject, cost badge. The user always knows *why* the output looks the way it does and what it cost.
5. **Editable outline** with add/reorder/delete/regenerate — cheap to build, huge perceived control.
6. **Review workflow** (Submit for Review → approved → Publish) with status chips in the Library.
7. **Registry-dispatched wizards** (`createWizardRouter.ts`) — the one piece of ImpactAI *frontend architecture* worth copying.

### 4.3 What is weak in ImpactAI's UX implementation (do **not** copy)

- 5–7k-line god components with 40–93 `useState`s and four setState setters passed as props; V1+V2 wizards coexisting.
- ~5k inline style objects, no tokens, industry colour threaded by hand; a11y ≈ 3 `aria-*` in the main wizard, `<div onClick>`, `window.confirm`.
- Mirrored catalogues (image types, styles, modules, personas, industries with **fake demo stats in the prod bundle**).
- Version API with zero UI call sites; orphaned `PersonaPicker`; dead `useKeyboardShortcuts`; `setTimeout(…,300)` sequencing; `eslint-disable exhaustive-deps` on generation effects.
- Security: JWT in iframe query string, `postMessage` without origin check, hardcoded internal CMS IP, internal error hints ("check port 8000 / ANTHROPIC_API_KEY") shown to end users.

### 4.4 Where Cognify is already ahead on authoring

- Per-section prose editing with **anchor validation** (422 on dropped `data-spec-id`), append-only section history + restore.
- Visual Studio (plan/render/refine/import/gallery) is more coherent than ImpactAI's scattered image modals.
- Structure-aware humanization (headings/code/tables survive) — ImpactAI has the parser but its editor round-trips markdown↔HTML through hand regex + showdown/turndown.
- Pipeline-debug page (per-step LLM prompt/response) — nothing comparable in ImpactAI.
- Design-system compliance and testability of every component.

---

## 5. What's best in what — summary

**Cognify is best at:** system architecture and boundaries; data layer and migrations; config; auth model; observability; testing; design system; visuals pipeline (post-Epic 10); RAG-grounded research and citations; multi-platform CMS publishing.

**ImpactAI is best at:** the *shape* of the authoring experience (§4.2); voice/persona modelling (Persona Engine); cost transparency to the end user; humanization iteration + learning loop; multi-app workflow integration (Strategist bridge); user-editable prompts; content breadth (blog, LinkedIn post/pulse, whitepaper, case study, carousel, FAQ, product, landing/service page, presentations, email).

**Both are weak at:** running long generation inside the web process (Cognify: `BackgroundTasks`; ImpactAI: `asyncio.create_task`). Cognify's `AsyncIODispatcher` → `CeleryDispatcher` seam is the cleaner path out; ImpactAI's Redis `job_store` with TTL + in-memory fallback is a reasonable *status surface* to borrow while doing it.

---

## 6. Worth adopting in Cognify — ranked, with fit and effort

Everything below is expressed as a Cognify-shaped change (LangGraph node/interrupt, service, SSE endpoint, component), never as "port the ImpactAI file". Effort is a rough SP guess.

### Tier 1 — the authoring loop (do these; they change what the product *feels* like)

| # | Adopt | Cognify shape | Effort |
|---|---|---|---|
| 1 | **Streaming progress + section text** | `GET /research/sessions/{id}/stream` (SSE) emitting typed events (`step_started`, `step_done`, `section_delta`, `visual_rendered`, `done`, `error`) from a Redis pub/sub or in-process queue that the pipeline nodes publish to; frontend `consumeSse` hook (copy the *behaviour* of ImpactAI's consumer: chunk-carry, JSON-string chunks, abort). Replace the fake %-by-status bar with real step + section progress; auto-navigate from Generate → session view. | 8 |
| 2 | **Outline approval gate** | LangGraph `interrupt_before=["draft_sections"]` (needs a persistent checkpointer — the already-planned `PostgresSaver`); `GET/PUT /research/sessions/{id}/outline` for edit (add/reorder/delete/rename sections, regenerate outline); `POST …/resume`. New `OutlineReviewStep` component. Also gives cancel-for-free. | 8 |
| 3 | **Brief object** | New `briefs` table + Pydantic `Brief` (title, description, audience, tone, angle, keywords, length, content_type, persona_id, diagram mode). Generate modal becomes "pick or edit a Brief"; briefs listed/reused/duplicated; `research_sessions.brief_id`. Prefill from topic analysis stays. | 5 |
| 4 | **Per-section *Regenerate with feedback*** | `POST /content/section-regenerate` — re-runs the `draft_section` node for one section with an instruction and previous-section context (unlike `section-rewrite`, it does not need current markdown). Button in `SectionContextToolbar`. | 3 |
| 5 | **Live cost badge** | Add `MODEL_PRICING` to settings, compute `$` from existing `llm_calls` (+ image renders), expose `GET /research/sessions/{id}/usage`; reuse the existing `UsageBadge` from Visual Studio at the session/article level. | 3 |
| 6 | **Draft persistence + resume** | Autosave the article-detail editor draft (`localStorage` keyed by section id) and show "unsaved draft" state; refetch article after `onPersisted` (fixes the stale-view bug); Articles list gets status filter + "Resume" for `generating`/`failed` sessions. | 3 |

### Tier 2 — trust and control surfaces

| # | Adopt | Cognify shape | Effort |
|---|---|---|---|
| 7 | **Editable title / SEO metadata** | `PATCH /articles/{id}` (title, subtitle, seo title/description, keywords, slug) with the same char-counter UI as ImpactAI's `SeoBriefStep`; per-field ↻ using existing SEO service. | 3 |
| 8 | **Length + content-type at generation** | Expose `ContentType` (article/how-to/analysis/report) and a length target in the Brief; thread to outliner (word budgets per section like ImpactAI's `_normalize_section_budgets`). | 3 |
| 9 | **Humanize iteration visibility** | Extend `humanize-preview` to stream per-pass slop score + which sentences changed; accept/reject per change in `HumanizationDiffPanel`. | 3 |
| 10 | **Draft / in-review / published state on articles** | Add `status` to `canonical_articles` (draft → in_review → approved → published) + Library-style filters. Prerequisite for any approval workflow and for scheduling. Beware L-003 (status consumers). | 3 |
| 11 | **Whole-article rich-text editing** | Optional; only if section-level editing proves insufficient. If done, use TipTap with a proper markdown extension (not regex round-trip) and keep anchor validation. | 8 |

### Tier 3 — platform ideas from ImpactAI's backend

| # | Adopt | Cognify shape | Effort |
|---|---|---|---|
| 12 | **Persona Engine (voice fingerprint → prompt → score → auto-fix)** | New `services/persona/` (fingerprint via textstat/spaCy, pgvector or Milvus few-shot store, sigma scoring); LangGraph node cycle `draft → score_voice → fix_deviations` guarded by threshold; `personas` table with samples. Replaces the 8 fixed persona keys with measured voices for *text* as well as images. Big, but it is the most differentiating idea in ImpactAI. | 13 |
| 13 | **Editable prompt registry** | Move node prompts to named templates with declared variables; `prompt_overrides` table + Settings tab (view/edit/reset). Cheap to do now that prompts are already centralized per node. | 5 |
| 14 | **Model tiering per step** | Settings-driven map step → model (e.g. Haiku for queries/outline/validate, Sonnet for drafting) instead of one model; already half-exists via `TrackedChatModel`. | 2 |
| 15 | **Off-loop model warm-up with graceful degradation** | Already partly done (baked model, PR #72). Add ImpactAI's `warm_up_in_background()` + `try_embed()` returning `None`-while-cold so a cold cache never blocks a request. | 1 |
| 16 | **Live role/status re-check per request** | `get_current_user` re-reads role/active flag (cache 30 s) so demotion/deactivation is immediate. | 1 |
| 17 | **Server-to-server integration pattern** | Only when a second app appears. The pattern (proxy endpoints hold the key, deep links carry ids, inbound callback with same key, 503 if unconfigured, `hmac.compare_digest`) is the right one. | — |
| 18 | **Job status store** | Redis hash w/ TTL + in-memory fallback behind `GET /jobs/{id}` — pair with the `CeleryDispatcher` work, not before. | 3 |
| 19 | **Humanize learning loop** | Record which slop-fix transformations survive user edits; re-prioritise the fixer. Nice-to-have after #9. | 5 |
| 20 | **More content types (LinkedIn post, newsletter)** | Cognify already has a LinkedIn *adapter*; a "repurpose CanonicalArticle → LinkedIn post" transformer + tiny wizard is cheap and stays inside ADR-003/004. | 5 |

### Suggested phasing
- **Phase A (≈25 SP): #1 #2 #3 #4 #5 #6** — turns the blind pipeline into a supervised one. This is "the ImpactAI feel" on Cognify's spine.
- **Phase B (≈20 SP): #7 #8 #9 #10 #14 #15 #16** — control, trust, cheap platform wins.
- **Phase C (≈25 SP): #12 #13 #20** — differentiation (voice), prompt ownership, content breadth.
- Do the **Celery/threadpool offload** (already flagged) alongside Phase A — streaming from a background worker needs Redis pub/sub anyway.

---

## 7. Explicitly *not* worth adopting

- Wizard-as-architecture (client-orchestrated multi-endpoint generation with state in the browser). Cognify's graph + interrupts gives the same UX with server-side truth.
- Raw SQL / startup DDL / dual schema files; `os.getenv` sprawl; model IDs as literals.
- Inline-style UI, mirrored catalogues, per-industry hardcoded config (Cognify's "catalogue is fetched, never mirrored" rule stands).
- HS256 shared-secret auth, JWT-in-URL, demo-token branches in every handler.
- Vendoring a third-party monorepo (Presenton) into the product repo; if deck generation is ever wanted, integrate it as a service.
- Two overlapping cost trackers.

---

## 8. Risks / caveats

- ImpactAI's *ideas* look polished partly because they are unconstrained by tests and boundaries. Budget for doing them properly (TDD, <200-line files, ADRs — at least ADR-005 "supervised pipeline via LangGraph interrupts" and ADR-006 "Brief as authoring contract").
- The outline gate changes `research_sessions.status` semantics (add `awaiting_outline_review`) — L-003 applies: grep all eight consumer sites first.
- Streaming from an in-process `BackgroundTasks` pipeline works but keeps the freeze risk; treat the worker offload as part of Phase A, not an afterthought.
- Persona Engine adds spaCy/textstat + a vector store for text; keep it optional (feature flag) so the default pipeline stays lean.

---

## Appendix A — File-size sanity check (Aug 2026)

| File | LoC |
|---|---:|
| `impactai/apps/api/routers/generate.py` | **9,018** (was 4,580 in May) |
| `impactai/apps/api/routers/wizards.py` | 4,926 |
| `impactai/apps/api/services/prompt_defaults.py` | 2,153 |
| `impactai/apps/api/services/persona_engine/` (pkg) | 2,087 |
| `impactai/apps/web/components/create/WebPageCreateScreenV2.tsx` | **7,668** |
| `impactai/apps/web/components/create/CreateScreen.tsx` | 5,287 |
| `impactai/apps/web/components/create/WebPageCreateScreen.tsx` | 5,067 (V1, still live) |
| `impactai/apps/web/components/create/PresentationCreateScreen.tsx` | 4,529 |
| `impactai/apps/web/components/create/VisualLayoutStep.tsx` | 1,965 |
| `impactai/apps/web/components/library/LibraryScreen.tsx` | 1,245 |
| `cognify/frontend/src/components/visuals/VisualStudio.tsx` | 523 |
| `cognify/frontend/src/app/(dashboard)/articles/[id]/page.tsx` | 423 |
| `cognify/frontend/src/components/visuals/SpecCard.tsx` | 413 |

Cognify's two largest frontend files also breach the <200-line rule and should be split when Phase A touches them.

## Appendix B — Sources
- `D:/Workbench/gitlab/impactai` — `PERSONA_ENGINE_OVERVIEW.md`, `STRATEGIST_BRIDGE_GUIDE.md`, `PRODUCT_SCOPE.md`, `HANDOVER.md`, `apps/web/lib/api.ts` (SSE consumer), `apps/web/store/contentStore.ts`, `apps/api/services/persona_engine/*`, `apps/api/routers/strategist_bridge.py`, `apps/api/services/usage.py`
- Cognify: `frontend/src/components/topics/*`, `frontend/src/app/(dashboard)/{research,articles,pipeline-debug}/**`, `src/api/routers/research.py`, `src/services/task_dispatch.py`, `src/agents/content/pipeline.py`
- May 2026 review: [`COGNIFY_VS_IMPACTAI_REVIEW.md`](./COGNIFY_VS_IMPACTAI_REVIEW.md)
