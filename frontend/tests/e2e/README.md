# Playwright E2E Tests

Scaffolding shipped alongside DASH-007; the first real journey landed
with AUTHOR-014.

| Spec | Covers |
|------|--------|
| `smoke.spec.ts` | Dev server boots, browser launches, app shell renders. |
| `create-article.spec.ts` | The supervised-authoring journey (Epic 11) against a fully mocked backend: `/topics` → Generate modal (saved brief) → `POST /research/sessions` → `/research/{id}` live SSE progress → outline gate → edit a heading → **Approve & write** (PUT + approve) → drafting progress → `article_complete` → **View article** → `/articles/{id}`. |

## Running locally

```bash
cd frontend
npx playwright install   # one-time: download chromium ~170MB
npm run e2e
```

`npm run e2e` runs `playwright test`. The `webServer` block in
`playwright.config.ts` starts `npm run dev` on port 3000 if it isn't
already running.

- **Docker stack on 3000?** Set `PLAYWRIGHT_PORT=3100` (any free port):
  `PLAYWRIGHT_PORT=3100 npm run e2e` (sh) or
  `$env:PLAYWRIGHT_PORT=3100; npm run e2e` (PowerShell). The dev server is
  started on that port and `baseURL` follows, so `reuseExistingServer`
  never silently tests the Docker build.
- When Playwright owns the server it wipes `.next/dev` first (Next 16's
  dev output; `next build` output is untouched): the state a killed
  `next dev` leaves behind can wedge the next run's first route compile
  (Turbopack, observed on `/research/[id]`). This assumes no *other* local
  `next dev` shares the checkout — the side-by-side case is the Docker
  frontend.
- The dev server gets `NEXT_PUBLIC_API_BASE_URL=/api/v1`, so every API
  call is a same-origin relative request that `page.route("**/api/v1/**")`
  intercepts before Next.js sees it — no CORS, no real backend.

## Mocking the backend (`support/`)

`create-article.spec.ts` shows the pattern the deferred flows below
should follow:

- `support/mock-backend.ts` — one `page.route("**/api/v1/**")` dispatcher
  over a `[method, path, handler]` table, backed by a small **phase
  machine** (`researching → awaiting_outline_review → generating_article
  → article_complete`). Every call is recorded (`backend.calls`), so specs
  assert request contracts (the session body carries `brief_id`, the PUT
  carries the edited heading), not just rendered text. Unmatched calls get
  a JSON 404 — **never fulfil a 401**: `apiClient`'s interceptor redirects
  the whole page to `/login`.
- `support/sse.ts` — frame builders for the mocked
  `GET /research/sessions/{id}/events` stream. Bodies are **finite**:
  `useSessionEvents` treats a stream that ends without a terminal `done`
  as a drop and reconnects after 1 s (any event resets its backoff), so
  the page keeps re-requesting the stream and picks up whichever phase the
  mock is in. No streaming server needed. Two consequences: the connection
  chip flips Live → Reconnecting… every second, so never assert on it; and
  the research → outline-review transition is advanced by the client's
  first `GET …/outline` (which only happens after it consumed the
  `status_changed` frame), not by the stream being served — that keeps the
  research frames non-vacuous even when React StrictMode aborts the first
  mount's stream.
- `support/create-article-fixtures.ts` — response fixtures typed with the
  app's own contracts (`@/types/*`, `@/lib/api/*`), so a backend-shape
  change fails `tsc` before it fails the browser run.

Auth is cookie-presence only (`middleware.ts` checks `cognify_access_token`
exists); the bearer token lives in `localStorage` under the same key.
There is no `/auth/me` bootstrap to mock (`smoke.spec.ts` still stubs it
defensively; nothing requests it).

`next dev` compiles routes on first hit (7–30 s cold), so the spec warms
the dynamic routes in `beforeAll`; the timed flow then measures the app,
not the compiler. On failure the spec attaches `browser-log` (page errors,
console errors/warnings) and `api-calls` (everything the mock saw) to the
Playwright report.

## Running in CI

`.github/workflows/e2e.yml` runs the same suite on the `e2e` GitHub
Actions label or on push to `main`. Browsers are downloaded once per
CI run and cached.

## Deferred test coverage (next-up work)

Two flows from the Visual Generation Overhaul plan still need real
E2E coverage. They were intentionally scoped out of the original
phases (VISUAL-008 §11.5, VISUAL-011 §11.8) because the scaffolding
above didn't exist. With Playwright now in place, both can land as
a single follow-up ticket.

### 1. Visual Studio plan → render → refine (VISUAL-008)

```
open article-detail
→ open Visual Studio panel
→ Plan visuals on a section
→ pick a variant
→ Render (gemini_flash)
→ verify image rendered
→ Refine with prompt
→ verify refined image differs
```

Backend mocks needed:
- `POST /api/v1/visuals/plan` → fixture spec list
- `POST /api/v1/visuals/render` → small base64 PNG
- `POST /api/v1/visuals/section-html-refine` → fixture HTML

Use Playwright's `page.route()` to intercept at the network layer —
no real backend required for E2E.

### 2. Per-section content editing (VISUAL-011)

```
hover a section
→ toolbar appears
→ click Edit text
→ select paragraph
→ AI rewrite "shorter"
→ verify diff shown with accept/reject
→ click Accept
→ verify markdown updated
→ open History
→ click Restore on prior version
→ verify original restored
```

Backend mocks needed:
- `POST /api/v1/content/section-rewrite`
- `POST /api/v1/content/paragraph-tone`
- `POST /api/v1/content/section-update`
- `GET  /api/v1/content/section/{id}/history`
- `POST /api/v1/content/section/{id}/restore`

### 3. Anchor-violation rejection path

The 422 branch on `section-update` has Vitest coverage but is worth
reproducing E2E so the editor sees the actual red-bordered
violations list rendered.
