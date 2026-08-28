import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config (Phase 8 follow-up — VISUAL-011 / VISUAL-008).
 *
 * Currently runs ONE smoke test that boots the Next.js dev server and
 * loads the dashboard. The deferred VISUAL-008 / VISUAL-011 E2E flows
 * (plan → render → refine; hover section → AI rewrite → save) need
 * backend mocks via `page.route()` and live next to this config when
 * implemented — see `tests/e2e/README.md`.
 *
 * Browser binaries are NOT pre-installed by `npm ci`. Run
 * `npx playwright install` once locally; CI does the same step in
 * `.github/workflows/e2e.yml` and caches the result.
 */
// Local Docker compose publishes the frontend on 3000. Set
// PLAYWRIGHT_PORT to run the E2E lane beside it (the dev server is
// started on the same port so `reuseExistingServer` never picks up
// the Docker build by accident).
const port = Number(process.env.PLAYWRIGHT_PORT ?? 3000);
const baseURL = `http://localhost:${port}`;

export default defineConfig({
  testDir: "./tests/e2e",
  // Default per-test timeout; smoke flows finish well under this.
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // Playwright kills the dev server it spawned at the end of a run; the
    // Turbopack state that leaves under `.next` can wedge the next run's
    // first route compile (observed: `/research/[id]` never finished).
    // Start from a clean cache whenever we own the server.
    command: `node -e "require('fs').rmSync('.next',{recursive:true,force:true})" && npm run dev -- --port ${port}`,
    url: baseURL,
    // Same-origin API base so every `apiClient` / SSE call is a relative
    // `/api/v1/...` request: no CORS preflight, and `page.route("**/api/v1/**")`
    // in the specs intercepts it before Next.js (whose middleware matcher
    // already skips `api`). Shell env beats `.env.local` in Next.
    env: { NEXT_PUBLIC_API_BASE_URL: "/api/v1" },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
