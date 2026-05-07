# Playwright E2E Tests

Minimal scaffolding shipped alongside DASH-007. The single existing
test (`smoke.spec.ts`) boots the Next.js dev server, loads the
dashboard route, and asserts the app shell rendered — proving the
build, dev server, and Playwright browser launch all work together.

## Running locally

```bash
cd frontend
npx playwright install   # one-time: download chromium ~170MB
npm run e2e
```

`npm run e2e` runs `playwright test`. The `webServer` block in
`playwright.config.ts` starts `npm run dev` on port 3000 if it isn't
already running.

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
