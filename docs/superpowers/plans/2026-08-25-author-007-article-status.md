# AUTHOR-007 — Article Status + List Filters + Resume

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Articles carry a real editorial status (`draft → in_review → approved → published`) editable from the article page, the articles list gets status filter pills, and in-flight/failed research sessions surface a "Resume" strip on the articles list linking to `/research/{id}`.

**Architecture:** New `ArticleStatus(StrEnum)` + `status` field on the frozen `CanonicalArticle` (defaulted `draft` so both construction sites keep compiling), `canonical_articles.status String(40) NOT NULL server_default 'draft'` via migration `add_article_status` (head `c4d8e2f1a9b7`). Status rides the existing AUTHOR-006 `PATCH /articles/{id}` (`fields["status"]`, whitelists widened in BOTH repos), the list endpoint gains a `status` filter (applied to the count query too), and a successful publish marks the article `published` in `PublishingService._persist_result` (duck-typed guard — the service's repo is typed `object`). Frontend: `ArticleStatus` union becomes the four real values (`"complete"` stays in the badge maps as a legacy alias for the dashboard), the three hardcoded `status: "complete"` mappers read the real field, `StatusBadge` gains `in_review`/`approved`, the articles page gets filter pills (copy of `session-filters.tsx`) and a resumable-sessions strip fed by `fetchSessions` (sessions in `generating_article`/`awaiting_outline_review`/failed states have NO article row — the strip is a second query, not a card field). Status transitions are NOT enforced server-side (any valid value, editor+) — the UI presents forward steps; document as a deliberate choice.

**Tech Stack:** Alembic + SQLAlchemy + FastAPI; TanStack Query + Tailwind pills; pytest / Vitest.

**Spec:** program plan §4.4 + §6 (Articles list bullet) + Phase-B acceptance ("a `failed` session shows Resume → session page"); review doc §6 #10 (+#6 Resume half). **L-003 applies** — the full consumer list is enumerated in the tasks; `"complete"` disappears only from `types/articles.ts`, nowhere else.

## Global Constraints

- Files < 200 lines: `canonical_articles.py` (257) and `src/db/repositories.py` (943) are pre-existing violations — minimal additions only; `articles/[id]/page.tsx` is at 195 — the status control mounts inside `article-header-editor.tsx` (187), NOT the page. The articles list page (43) is the safe place to grow.
- Migration: `String(40)` (match `research_sessions.status` post-#75 width — L-003's column-width lesson), `nullable=False`, `server_default="draft"`; plus the repo-precedent metadata test (`tests/unit/db/test_article_status_column_width.py`, mirror of `test_session_status_column_width.py` — SQLite doesn't enforce VARCHAR).
- slowapi decorator order: route decorator OUTERMOST (the AUTHOR-006 lesson) for any new/touched route.
- Repo whitelists: `update_metadata` ignores unknown keys in BOTH `PgArticleRepository` (`repositories.py:716`, docstring says so) and `InMemoryArticleRepository` (`content_repositories.py:116`) — forgetting either makes status PATCH a silent no-op.
- List filter must hit BOTH the count query and the page query (`repositories.py:149-166` session precedent).
- No `.env` in the worktree during tests; delete after docker smokes.
- TDD red/green per step; commit per task.

---

### Task 1: Backend model + migration + repositories

**Files:**
- Modify: `src/models/content.py` (add `ArticleStatus(StrEnum)` after `ContentType` :16-22; `status: ArticleStatus = ArticleStatus.DRAFT` next to `ai_generated` :113)
- Modify: `src/db/tables.py` (`CanonicalArticleRow` — `status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="draft")` after `ai_generated` :204; match the file's column style)
- Create: `alembic/versions/d5e8f2a1c3b9_add_article_status.py` (down_revision `c4d8e2f1a9b7`; mimic `a9d4e2f7c1b8`'s add_column with server_default)
- Modify: `src/db/repositories.py` — `PgArticleRepository.create` (~:630 write `status=article.status.value`), `_to_model` (~:771 `status=ArticleStatus(row.status or "draft")`), `update_metadata` (whitelist + `row.status = str(fields["status"])`), `list` gains `status: str | None = None` applied to count + page queries
- Modify: `src/services/content_repositories.py` — Protocol: add `list` declaration (`async def list(self, page: int = 1, size: int = 20, status: str | None = None) -> tuple[list[CanonicalArticle], int]`) and widen `update_metadata` docs; `InMemoryArticleRepository`: widen whitelist to include `"status"`, add `list` (newest-first by `generated_at`, optional equality filter)
- Tests: `tests/unit/db/test_article_status_column_width.py` (new, mirror of `test_session_status_column_width.py` with the 4 statuses), extend `tests/unit/services/test_article_update_metadata.py` (status update via whitelist; unknown key still ignored; in-memory `list` filter), extend `tests/integration/db/test_pg_article_metadata.py` (status round-trip: create → status defaults draft → update_metadata to in_review → list(status="in_review") finds it)

- [ ] **Step 1: Write the failing tests** (column-width file, update_metadata status cases, in-memory list cases — real code, mimic the named files)
- [ ] **Step 2: Run — FAIL** (`uv run pytest tests/unit/db/test_article_status_column_width.py tests/unit/services/test_article_update_metadata.py -q`)
- [ ] **Step 3: Implement** (enum, field, column, migration file, both repos)
- [ ] **Step 4: Run unit tests + FULL backend suite** (both `CanonicalArticle(` construction sites compile via the default; `_build_article` fixtures unchanged); apply the migration to the live DB (`uv run alembic upgrade head` with the compose postgres up — worktree needs no `.env` for this if `COGNIFY_DATABASE_URL` is exported inline for the one command) and run the integration test. Lint/mypy clean on touched files.
- [ ] **Step 5: Commit** — `feat(db): ArticleStatus enum + canonical_articles.status migration + repo support (AUTHOR-007 Task 1)`

---

### Task 2: API surface — PATCH status, list filter, publish → published

**Files:**
- Modify: `src/api/schemas/article_metadata.py` (`ArticleMetadataPatch.status: ArticleStatus | None = None`; `ArticleMetadataResponse.status: str`)
- Modify: `src/api/routers/article_metadata.py` (`_build_fields`: `if patch.status is not None: fields["status"] = patch.status`; `_to_metadata_response`: `status=article.status.value`)
- Modify: `src/api/schemas/articles.py` (`CanonicalArticleResponse.status: str = "draft"`)
- Modify: `src/api/routers/canonical_articles.py` (list endpoint gains `status: ArticleStatus | None = None` → `repo.list(page, size, status.value if status else None)`; `_to_canonical_response` adds `status=article.status.value`) — minimal lines, file is over budget
- Modify: `src/services/publishing/service.py` (`_persist_result` success path: `update = getattr(self._article_repo, "update_metadata", None); if update is not None: await update(article.id, {"status": ArticleStatus.PUBLISHED})` — duck-typed because the repo is typed `object`; import under TYPE_CHECKING/local)
- Tests: extend `tests/unit/api/test_article_metadata_endpoints.py` (PATCH `{"status": "in_review"}` → 200 + persisted + response carries it; invalid value → 422 via enum), new `TestListArticlesFilter` in a small new file `tests/unit/api/test_article_list_filter.py` (seed 3 articles with mixed statuses on an `app.state.article_repo` = InMemoryArticleRepository; `GET /articles?status=approved` → only that one, `total` correct; no filter → all; NOTE the list endpoint reads `app.state.article_repo`, not content_service), publishing test (existing publishing service tests file — add: successful publish calls `update_metadata` with `PUBLISHED` when the repo has it; a repo without the method doesn't crash)

- [ ] **Step 1: failing tests** → **Step 2: RED** → **Step 3: implement** → **Step 4: full backend suite + lint/mypy** → **Step 5: Commit** — `feat(api): article status through PATCH/list/publish (AUTHOR-007 Task 2)`

---

### Task 3: Frontend types, mappers, StatusBadge

**Files:**
- Modify: `frontend/src/types/articles.ts` (`ArticleStatus = "draft" | "in_review" | "approved" | "published"`)
- Modify: `frontend/src/lib/api/articles.ts` (`ArticleResponse.status?: string` — optional so old fixtures compile)
- Modify: `frontend/src/hooks/use-article.ts` :67 and `use-article-list.ts` :11 (`status: (a.status as ArticleStatus) ?? "draft"`), `use-articles.ts` :14 (dashboard union has no in_review/approved: map `published → "live"`, else `"complete"` — behaviour-preserving for the dashboard)
- Modify: `frontend/src/components/common/status-badge.tsx` (add `in_review` [info style, label "In Review"] and `approved` [success style, label "Approved"]; KEEP `complete` as legacy alias)
- Tests: `status-badge.test.tsx` (+2 cases), `article-card.test.tsx` (fixture status → `"approved"`, assert "Approved" renders), `use-article-list.test.ts` (fixture gains `status: "in_review"`, assert mapped through; absent status → `"draft"`)

- [ ] Steps 1–5 (RED → implement → full frontend suite + tsc no-new → Commit `feat(frontend): real ArticleStatus through mappers + badge variants (AUTHOR-007 Task 3)`)

---

### Task 4: Status transition control on the article page

**Files:**
- Modify: `frontend/src/components/articles/article-header-editor.tsx` (187 — add a status pill + a compact next-step control in VIEW mode: current `StatusBadge` + a small "Move to <next>" ghost button for draft→in_review→approved→published, using `useArticleMetadata.save({ status })`; nothing added to page.tsx). If the addition pushes the file over 200, extract `article-status-control.tsx` and mount it from the editor's view mode.
- Tests: extend `article-header-editor.test.tsx` (renders current status badge; clicking "Move to In Review" calls `save({status: "in_review"})`; published shows no next-step button)

- [ ] Steps 1–5 (Commit `feat(frontend): status pill + next-step transition on article header (AUTHOR-007 Task 4)`)

---

### Task 5: List filter pills + Resume strip

**Files:**
- Create: `frontend/src/components/articles/article-filters.tsx` (copy `session-filters.tsx` shape: All | Draft | In Review | Approved | Published + `{totalCount} Articles`)
- Modify: `frontend/src/hooks/use-article-list.ts` (`useArticleList(status?: ArticleStatus)` → `fetchArticles(1, 20, status)`, query key `["article-list", status ?? "all"]`)
- Modify: `frontend/src/lib/api/articles.ts` (`fetchArticles(page, size, status?)` adds the `status` param)
- Modify: `frontend/src/lib/research/session-status.ts` (add `RESUMABLE_SESSION_STATUSES = ["planning","in_progress","researching","evaluating","running","generating_article","awaiting_outline_review","failed","article_failed"]` — read `src/db/repositories.py:149-166` first: statuses must be requested via values/groups the backend filter map actually supports; `failed` is a GROUP alias covering `failed`+`article_failed`)
- Create: `frontend/src/hooks/use-resumable-sessions.ts` (parallel `fetchSessions` per needed backend filter value — likely `generating_article`, `awaiting_outline_review`, `failed` — merged, deduped by id, errors → `[]`)
- Create: `frontend/src/components/articles/resume-sessions-strip.tsx` (renders nothing when empty; otherwise a `bg-warning-light`-tinted card listing topic title + `SessionStatusBadge` + "Resume →" link to `/research/{id}`)
- Modify: `frontend/src/app/(dashboard)/articles/page.tsx` (43 → ~70: filter state à la `research/page.tsx:17-31`, `<ArticleFilters/>`, `<ResumeSessionsStrip/>` above the grid)
- Tests: new `frontend/src/app/(dashboard)/articles/page.test.tsx` (mock `@/lib/api/articles` + `@/lib/api/research`; default shows all + strip renders a failed session with a `/research/{id}` link; clicking the "Approved" pill refetches with `status="approved"`; empty resumables → no strip), `use-resumable-sessions.test.tsx`

- [ ] Steps 1–5 (Commit `feat(frontend): articles status filters + resumable-sessions strip (AUTHOR-007 Task 5)`)

---

### Task 6: Verification, migration smoke, docs, review, PR

- [ ] **Step 1:** Full suites (backend unit + the PG integration file, frontend vitest, ruff/format, mypy/tsc no-new).
- [ ] **Step 2: Live smoke** — copy `.env` in; `docker compose -p cognify up --build -d api frontend`; **verify the migration ran** (entrypoint runs `alembic upgrade head` — check `alembic_version` = new head; existing articles have `status='draft'`); UI: articles list shows Draft badges; header status control: Draft → "Move to In Review" → badge updates without reload → DB row `in_review`; filter pills narrow the list (and `total`); publish an article to Ghost if configured OR skip publish smoke and note it; Resume strip: the cancelled/failed sessions from earlier smokes appear with working `/research/{id}` links; dashboard still renders (legacy `complete` alias). Delete `.env` after.
- [ ] **Step 3: Docs** — PROGRESS (row + RESUME item; note the no-transition-enforcement decision and the dashboard alias), BACKLOG (+3 SP → 386), CLAUDE.md (status line + next action AUTHOR-008), tick plan checkboxes UTF-8-safely.
- [ ] **Step 4:** Code review vs `develop` → fix findings → push → PR via `--body-file` (deviations: no server-side transition graph — any valid status, editor+; `complete` kept as badge alias; sessions strip is a second query because resumable sessions have no article row).

---

## Self-Review (at plan time)

- Spec §4.4 column+migration ✅ (T1), use-article hardcode replaced ✅ (T3), §6 filter pills + Resume ✅ (T5), status pill + transitions ✅ (T4 — UI-guided, server permissive: deliberate, documented), publish marks published ✅ (T2). L-003: every consumer enumerated in T2/T3 (backend had zero article-status consumers; frontend list is exhaustive from recon incl. the second union in `types/api.ts` which is left intact via the alias strategy).
- Risk callouts: whitelists in two repos (T1), count-query filter (T1), `app.state.article_repo` in list tests (T2), backend session-filter map values for the strip (T5 — read before coding), entrypoint migration check (T6).
