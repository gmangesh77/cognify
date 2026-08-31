# AUTHOR-014: Playwright Create-Article Flow (Mocked SSE) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** One Playwright spec, `frontend/tests/e2e/create-article.spec.ts`, drives the whole supervised-authoring journey through the real Next.js UI against a fully mocked backend: `/topics` → Generate modal (saved brief picked) → `POST /research/sessions` → auto-navigate to `/research/{id}` → live SSE progress → `awaiting_outline_review` → edit a section title → **Approve & write** (PUT + approve) → drafting progress bar → `article_complete` → **View article** → `/articles/{id}` renders the article. No backend, no LLM, no database.

**Architecture:** All HTTP is intercepted with a single `page.route("**/api/v1/**")` dispatcher backed by a small in-test phase machine (`MockBackend`). The SSE endpoint is fulfilled with a finite `text/event-stream` body for the *current* phase; because `useSessionEvents` resets its backoff on every received event and reconnects 1 s after a stream that ends without a terminal `done`, the page keeps re-requesting the stream and picks up each phase change deterministically — no streaming server needed. Phases advance either server-side (research → outline review, mirroring the real backend) or under test control (approve → drafting; `backend.completeArticle()` → done).

**Tech Stack:** Playwright 1.59 (`@playwright/test`), Next.js 16.1.6 dev server (Turbopack), TypeScript strict. No production code changes.

**Spec:** program plan `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §7 ("extend the smoke lane with `create-article.spec.ts` (mocked backend SSE via route interception): brief → outline approve → sections appear → article page") and acceptance item "Playwright spec passes in the opt-in CI lane".

## Global Constraints

- Files < 200 lines (the Vitest budget guard covers `src/app` + `src/components` only, but keep the e2e files under it anyway); named exports; no `any`.
- `tests/e2e` is inside `tsconfig.json` `include` and is linted by `eslint-config-next` — new files must pass `tsc --noEmit` and `npm run lint`.
- **Never fulfil a 401**: `apiClient`'s interceptor redirects the whole page to `/login` (`src/lib/api/client.ts:45-66`). Unmatched API calls get a JSON 404.
- Auth is cookie-presence only (`middleware.ts`: `cognify_access_token`); the bearer token lives in `localStorage` under the same key. No `/auth/me` call exists.
- The reducer switches on the JSON payload's `type` field, not the SSE `event:` line (`src/hooks/use-session-events.ts:86`). Frames end with `\n\n`.
- `step_progress` for `content_draft` with `sections_done/sections_total/current_section` is what renders `Drafting n / m — <section>`; `step_done` on `content_draft` hides it.
- Local Docker publishes the frontend on 3000: the config must allow running the lane on another port (`PLAYWRIGHT_PORT`).

---

### Task 1: Playwright config — port override + same-origin API base

**Files:**
- Modify: `frontend/playwright.config.ts`

- [x] **Step 1: `PLAYWRIGHT_PORT`** — `baseURL` and `webServer.command` (`npm run dev -- --port N`) derive from `process.env.PLAYWRIGHT_PORT ?? 3000` so the lane can run beside the Docker frontend.
- [x] **Step 2: same-origin API** — `webServer.env: { NEXT_PUBLIC_API_BASE_URL: "/api/v1" }` so the browser calls relative `/api/v1/...` (no CORS preflight; the Next middleware matcher already excludes `api`). The route glob `**/api/v1/**` also matches the absolute default, and the dispatcher answers `OPTIONS` with 204 + CORS headers, so a reused dev server without the env still works.
- [x] **Step 3: verify** — `PLAYWRIGHT_PORT=3100 npx playwright test smoke` still passes.

### Task 2: Fixtures + SSE frame helpers

**Files:**
- Create: `frontend/tests/e2e/support/create-article-fixtures.ts` — `TOPIC`, `DOMAINS`, `BRIEFS`, `ANALYSIS`, `OUTLINE`, `USAGE`, `ARTICLE` (lifted from the Vitest fixtures in `use-article.test.ts`, `outline-review-step.test.tsx`, `generate-article-modal.test.tsx`, `session-progress.test.tsx`) plus `SESSION_ID`/`ARTICLE_ID`.
- Create: `frontend/tests/e2e/support/sse.ts` — `sseFrame(event)` (`event: …\ndata: …\n\n`), `stepRow(name, status)`, `snapshot(status, steps)`, `stepProgress(...)`, `done(status)`.

- [x] **Step 1: write the fixture module** (data only; typed with the app's own types via `@/types/*` imports — path alias resolves through `tsconfig.json`).
- [x] **Step 2: write the SSE helpers**; wire format per `src/models/session_events.py:36-38`.

### Task 3: `MockBackend` route dispatcher

**Files:**
- Create: `frontend/tests/e2e/support/mock-backend.ts`

**Interface:** `installMockBackend(page): Promise<MockBackend>`; `MockBackend { phase; calls: {method,path,body}[]; completeArticle(); }`.

- [x] **Step 1: dispatcher** — one `page.route("**/api/v1/**")`: parse `new URL(request.url()).pathname` after `/api/v1`, dispatch on `method + path`:
  - `GET /settings/domains` → `{items: DOMAINS}`; `GET /topics` → `{items:[TOPIC], total:1, page:1, size:50}`; `GET /briefs` → `BRIEFS`
  - `POST /topics/analyze` → `ANALYSIS`; `POST /research/sessions` → 201 `{session_id, status:"planning", started_at}`
  - `GET /research/sessions/{id}` → detail with `status = phase`; `GET …/usage` → `USAGE`; `GET …/events` → `text/event-stream` body for the phase (research body auto-advances phase → `awaiting_outline_review`)
  - `GET …/outline` → `{draft_id, session_id, status:"outline_complete", outline}`; `PUT …/outline` → stores body as the outline; `POST …/outline/approve` → 202, phase → `generating_article`
  - `GET …/article` → `{article_id}`; `GET /articles/{id}` → `ARTICLE`; `GET /articles/{id}/usage` → `USAGE`; `GET /settings/general` → `{}`
  - anything else → 404 `{detail:"e2e: unmocked"}`; `OPTIONS` → 204.
- [x] **Step 2: phase bodies** — `researching`: snapshot(researching; plan_research ✓, research_facet_0 ✓, content_outline running) + step_done(content_outline) + status_changed(awaiting_outline_review). `awaiting_outline_review`: snapshot only. `generating_article`: snapshot(generating_article; …, content_draft running) + step_progress(content_draft, done=1, total=outline.sections.length, current_section=outline.sections[0].title). `article_complete`: snapshot(all ✓) + done(article_complete).
- [x] **Step 3: record every call** (`method`, `path`, parsed JSON body) so the spec can assert the request contracts (session body carries `brief_id` + `require_outline_approval`; PUT outline carries the edited title).

### Task 4: The spec

**Files:**
- Create: `frontend/tests/e2e/create-article.spec.ts`

- [x] **Step 1: auth bootstrap** — `context.addCookies([{name:"cognify_access_token", value:"1", domain:"localhost", path:"/"}])` + `page.addInitScript` setting `localStorage.cognify_access_token`.
- [x] **Step 2: topics → modal** — goto `/topics`, `getByRole("button", {name:"Generate Article"})`, dialog visible, `getByLabel("Brief")` select `Saved brief` → `getByLabel("Review outline before drafting")` is checked, click `getByRole("button", {name:"Generate", exact:true})`.
- [x] **Step 3: session page** — `expect(page).toHaveURL(/\/research\/sess-e2e-1$/)`; assert `POST /research/sessions` body (`topic_id`, `brief_id:"b1"`, `require_outline_approval:true`); badge text `Outline review`; step `Generate Outline` listed.
- [x] **Step 4: outline review** — title input has `Zero Trust Architecture`; fill `Section 1 title` with `Getting Started`; click `Approve & write`; assert PUT body `sections[0].title === "Getting Started"` and approve call recorded.
- [x] **Step 5: drafting** — badge `Generating Article`; text `Drafting 1 / 2 — Getting Started` (proves the edit reached the "backend"); step `Draft Sections`.
- [x] **Step 6: completion** — `backend.completeArticle()`; badge `Article Ready`; click `View article`; `toHaveURL(/\/articles\/art-e2e-001$/)`; h1 = article title; h2s `Getting Started` + `Deep Dive`.
- [x] **Step 7: run** — `PLAYWRIGHT_PORT=3100 npx playwright test` → 2 passed; run it 3× to shake out timing flakes.

### Task 5: Docs + gates

- [x] `frontend/tests/e2e/README.md`: document the new spec, `PLAYWRIGHT_PORT`, the phase-machine pattern and why finite SSE bodies work; keep the VISUAL-008/011 deferred list.
- [x] `.github/workflows/e2e.yml` header comment mentions the create-article spec (job name → "Playwright suite").
- [x] `npm run lint`, `npx tsc --noEmit` (no new errors vs the 13 pre-existing), `npx vitest run` (599, budget guard green). Playwright full suite 3× green on a Playwright-owned clean server (2 passed; 34 s / 49 s / 29 s incl. boot).
- [x] PROGRESS.md / BACKLOG.md / CLAUDE.md status; tick this plan; PR #86 (`AB#`-less — Epic 11 has no Azure Boards items), labelled `e2e`; lane green in CI (1m27s). Review (no Critical): `beforeAll` timeout raised + `/topics` warmed; `.next/dev` (not `.next`) wiped; research→review phase advanced by the client's outline GET (non-vacuous under StrictMode); test split into `test.step` helpers.
