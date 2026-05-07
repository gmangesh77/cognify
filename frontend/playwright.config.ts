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
    baseURL: "http://localhost:3000",
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
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
