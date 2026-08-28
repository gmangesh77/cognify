import { expect, test } from "@playwright/test";
import { ARTICLE, ARTICLE_ID, BRIEFS, OUTLINE, SESSION_ID, TOPIC } from "./support/create-article-fixtures";
import { installMockBackend } from "./support/mock-backend";
import type { MockBackend } from "./support/mock-backend";

/**
 * AUTHOR-014 — the supervised-authoring journey end to end, against a fully
 * mocked backend (see `support/mock-backend.ts`):
 *
 *   /topics → Generate modal (saved brief) → POST /research/sessions
 *   → /research/{id} live progress (SSE) → outline review gate
 *   → edit a heading → Approve & write (PUT + approve) → drafting progress
 *   → article_complete → View article → /articles/{id}
 *
 * Auth is cookie-presence only (`middleware.ts`); the bearer token lives in
 * localStorage under the same key. No `/auth/me` bootstrap exists.
 */
const TOKEN_KEY = "cognify_access_token";
const OUTLINE_PATH = `/research/sessions/${SESSION_ID}/outline`;
const ARTICLE_LOOKUP_PATH = `/research/sessions/${SESSION_ID}/article`;
const EDITED_TITLE = "Getting Started";
// Route changes compile the target page on demand on a cold `next dev`.
const NAVIGATION_TIMEOUT = 30_000;

test.describe("create article (supervised authoring, mocked backend)", () => {
  const browserLog: string[] = [];
  let backend: MockBackend;

  // `next dev` compiles routes on first hit (7-30 s cold). Warm the two
  // dynamic routes once so the timed flow below measures the app, not the
  // compiler. Unmocked API calls here just 404 — never 401 — so nothing
  // redirects; only the server-side compile matters.
  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    await context.addCookies([{ name: TOKEN_KEY, value: "1", domain: "localhost", path: "/" }]);
    const page = await context.newPage();
    for (const path of [`/research/${SESSION_ID}`, `/articles/${ARTICLE_ID}`]) {
      await page.goto(path, { timeout: 120_000 });
    }
    await context.close();
  });

  test.beforeEach(async ({ context, page }) => {
    await context.addCookies([{ name: TOKEN_KEY, value: "1", domain: "localhost", path: "/" }]);
    await page.addInitScript((key) => window.localStorage.setItem(key, "e2e-token"), TOKEN_KEY);
    backend = await installMockBackend(page);
    browserLog.length = 0;
    page.on("pageerror", (err) => browserLog.push(`pageerror: ${err.message}`));
    page.on("console", (msg) => {
      if (msg.type() === "error" || msg.type() === "warning") {
        browserLog.push(`console.${msg.type()}: ${msg.text()}`);
      }
    });
  });

  // Attach browser errors + every API call the mock saw, so a CI failure
  // explains itself without a rerun.
  test.afterEach(async ({}, testInfo) => {
    if (testInfo.status === testInfo.expectedStatus) return;
    await testInfo.attach("browser-log", { body: browserLog.join("\n"), contentType: "text/plain" });
    await testInfo.attach("api-calls", {
      body: JSON.stringify(backend.calls, null, 2),
      contentType: "application/json",
    });
  });

  test("brief → outline review → drafting → article page", async ({ page }) => {
    test.setTimeout(60_000);

    // --- Topics page → Generate modal with a saved brief ------------------
    await page.goto("/topics");
    await expect(page.getByText(TOPIC.title).first()).toBeVisible();
    await page.getByRole("button", { name: "Generate Article" }).first().click();

    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "Generate Article" })).toBeVisible();
    await dialog.getByLabel("Brief", { exact: true }).selectOption({ label: BRIEFS[0].name });
    await expect(dialog.getByLabel("Review outline before drafting")).toBeChecked();
    await dialog.getByRole("button", { name: "Generate", exact: true }).click();

    // --- Auto-navigate to the session page; request contract ---------------
    await expect(page).toHaveURL(new RegExp(`/research/${SESSION_ID}$`), {
      timeout: NAVIGATION_TIMEOUT,
    });
    const created = backend.callsTo("POST", "/research/sessions");
    expect(created).toHaveLength(1);
    expect(created[0].body).toMatchObject({
      topic_id: TOPIC.id,
      brief_id: BRIEFS[0].id,
      require_outline_approval: true,
    });

    // --- Live progress reaches the outline gate ---------------------------
    await expect(page.getByText("Outline review", { exact: true })).toBeVisible();
    await expect(page.getByRole("listitem").filter({ hasText: "Generate Outline" })).toBeVisible();

    // --- Outline review: edit a heading, approve ---------------------------
    await expect(page.getByLabel("Title", { exact: true })).toHaveValue(OUTLINE.title);
    await expect(page.getByLabel("Section 2 title")).toHaveValue(OUTLINE.sections[1].title);
    await page.getByLabel("Section 1 title").fill(EDITED_TITLE);
    await page.getByRole("button", { name: "Approve & write" }).click();

    await expect.poll(() => backend.callsTo("PUT", OUTLINE_PATH).length).toBe(1);
    const saved = backend.callsTo("PUT", OUTLINE_PATH)[0].body as { sections: { title: string }[] };
    expect(saved.sections[0].title).toBe(EDITED_TITLE);
    await expect.poll(() => backend.callsTo("POST", `${OUTLINE_PATH}/approve`).length).toBe(1);

    // --- Drafting: sections appear (progress derived from the edited outline)
    await expect(page.getByText("Generating Article", { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(`Drafting 1 / 2 — ${EDITED_TITLE}`)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("listitem").filter({ hasText: "Draft Sections" })).toBeVisible();

    // --- Completion → View article → article page --------------------------
    backend.completeArticle();
    await expect(page.getByText("Article Ready", { exact: true })).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "View article" }).click();
    await expect.poll(() => backend.callsTo("GET", ARTICLE_LOOKUP_PATH).length).toBe(1);

    await expect(page).toHaveURL(new RegExp(`/articles/${ARTICLE_ID}$`), {
      timeout: NAVIGATION_TIMEOUT,
    });
    await expect(page.getByRole("heading", { level: 1, name: ARTICLE.title })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Getting Started" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Deep Dive" })).toBeVisible();
  });
});
