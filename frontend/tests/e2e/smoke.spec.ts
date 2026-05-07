import { expect, test } from "@playwright/test";

/**
 * Smoke E2E test — proves the Playwright pipeline works end-to-end
 * (dev server boots, browser launches, app shell renders).
 *
 * The richer flows from the Visual Generation Overhaul plan
 * (Visual Studio plan→render→refine, per-section AI rewrite +
 * history restore, anchor-violation rejection) live next to this
 * file once their fixtures land — see `README.md`.
 */
test("dashboard shell renders", async ({ page }) => {
  // Stub the auth check so the unauthenticated dev server doesn't
  // bounce us to /login. The smoke test only cares that Next.js
  // rendered the route.
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "u1", email: "smoke@test", role: "editor" }),
    }),
  );
  await page.goto("/login");
  // The login page is the public landing route; we just assert the
  // build produced *something* renderable.
  await expect(page.locator("body")).toBeVisible();
});
