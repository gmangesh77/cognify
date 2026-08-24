# AUTHOR-006 — Article Metadata PATCH + Header/SEO Editor + Autosave

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Editors can edit an article's title/subtitle/SEO metadata in place (with live length counters, per-field AI regenerate, and SEO-length *warnings*), the article view never goes stale after a persist, and unsaved section-editor drafts survive accidental closes via localStorage autosave.

**Architecture:** A new `PATCH /articles/{id}` (schema-validated, editor+) persists through a new `ArticleRepository.update_metadata` (protocol + in-memory + PG; scalar columns `title`/`subtitle`, JSONB-reassigned `seo`). `POST /articles/{id}/seo/regenerate` calls the existing pure `generate_seo_metadata(title, body_text, llm)` with the content service's `TrackedChatModel` (contextvars bound to the draft's real session id — L-013 — so the call lands in Pipeline Debug and the AUTHOR-005 usage badge) and returns the one requested field **without persisting**; the user saves via PATCH. Both routes live in a new `src/api/routers/article_metadata.py` (`canonical_articles.py` is already over the 200-line cap). Frontend: `article-header-editor.tsx` replaces the static header on the article page, driven by a `useArticleMetadata` mutation hook that `refetch()`es on success; the page's editing-state cluster moves to `hooks/article-editing-state.ts` to stay under 200 lines; the history-restore path gets the missing `refetch()`; `InlineProseEditor` autosaves its draft to `localStorage["cognify:draft:{sectionId}"]` (sectionId already = `{articleId}:{sectionIndex}`) with an "Unsaved draft" chip.

**Tech Stack:** FastAPI + Pydantic (backend), TanStack Query v5 `useMutation` + axios (frontend), pytest / Vitest.

**Spec:** `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §5.7 + §6 (article-page bullets); `docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md` §6 #6 (metadata editing) + #7 (stale view).

**Deliberate deviations from spec §5.7 (state in the PR):**
- **No `slug`.** Nothing in the codebase has a slug today (no model field, no column, no UI consumer; Ghost publishing derives one from the title at transform time via `_slugify`). Adding a column + unique index + Alembic migration + backfill for a field nothing reads is scope creep on a 5 SP UX ticket — file it to ride along with AUTHOR-007's `status` migration if ever needed.
- **No `status` in the PATCH.** `canonical_articles` has no status column; AUTHOR-007 owns that migration and its L-003 blast radius.

## Global Constraints

- Functions < 20 lines, prod files < 200 lines, max 3 params. `canonical_articles.py` (258) and `page.tsx` (194) must not grow — new router module; page must shrink via the state-hook split.
- `PATCH` is currently **missing from the CORS `allow_methods`** (`src/api/main.py`, `allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]`) — add `"PATCH"` or the browser preflight fails.
- `CanonicalArticle` is frozen — mutate via `model_copy(update=...)`; `SEOMetadata` caps are hard 422s (title ≤ 70, description ≤ 170, keywords ≤ 20) — the PATCH schema mirrors them so `model_copy` can never produce an invalid article. The 50–60 / 150–160 SEO ranges are **warnings in the response**, never errors.
- L-013: resolve article→session ONLY via `ArticleDraftRepository.find_by_article_id → draft.session_id` (for the tracked-LLM contextvars). Never `provenance.research_session_id`.
- L-001: PG JSONB writes use `model_dump(mode="json")`; reassign the whole `seo` JSONB value (dirty-tracking pattern from `append_visual`, `src/db/repositories.py:692-712`).
- Backend test fixtures must read the repo via `app.state.content_service` / an explicitly-set `app.state.article_repo` — the `finalize_app` fixture (test_article_endpoints.py:499) does not set `article_repo`.
- No `.env` in the worktree while running tests. Frontend: no inline styles; tokens per `frontend/DESIGN.md`; localStorage access SSR-guarded (`typeof window === "undefined"`) and try/caught.
- TDD red/green per step; commit per task.

---

### Task 1: `ArticleRepository.update_metadata` (protocol + in-memory + PG)

**Files:**
- Modify: `src/services/content_repositories.py` (protocol :62-70, `InMemoryArticleRepository` :73-101)
- Modify: `src/db/repositories.py` (`PgArticleRepository`, after `append_visual` ~line 712)
- Test: `tests/unit/services/test_article_update_metadata.py`

**Interfaces:**
- Produces (used by Task 2):

```python
class ArticleRepository(Protocol):
    async def update_metadata(
        self, article_id: UUID, fields: dict[str, object]
    ) -> CanonicalArticle | None: ...
    # fields keys: "title" | "subtitle" | "seo" (a complete SEOMetadata).
    # Returns the updated article, or None when the id is unknown.
```

In-memory impl: `existing.model_copy(update=fields)`; PG impl: set `title`/`subtitle` scalar columns when present, assign `row.seo = seo.model_dump(mode="json")` when present (L-001), return `self._to_model(row)`.

- [x] **Step 1: Write the failing tests**

```python
"""ArticleRepository.update_metadata (AUTHOR-006)."""

from uuid import uuid4

from src.models.content import SEOMetadata
from src.services.content_repositories import InMemoryArticleRepository
from tests.unit.api.test_article_endpoints import _build_article


async def test_updates_title_subtitle_and_seo() -> None:
    repo = InMemoryArticleRepository()
    article = _build_article(uuid4())
    await repo.create(article)
    new_seo = article.seo.model_copy(update={"title": "New SEO title"})
    updated = await repo.update_metadata(
        article.id,
        {"title": "New title", "subtitle": "New sub", "seo": new_seo},
    )
    assert updated is not None
    assert updated.title == "New title"
    assert updated.subtitle == "New sub"
    assert updated.seo.title == "New SEO title"
    stored = await repo.get(article.id)
    assert stored is not None and stored.title == "New title"
    # untouched fields survive
    assert stored.body_markdown == article.body_markdown


async def test_partial_update_keeps_other_fields() -> None:
    repo = InMemoryArticleRepository()
    article = _build_article(uuid4())
    await repo.create(article)
    updated = await repo.update_metadata(article.id, {"subtitle": "Only sub"})
    assert updated is not None
    assert updated.title == article.title
    assert updated.subtitle == "Only sub"


async def test_unknown_article_returns_none() -> None:
    repo = InMemoryArticleRepository()
    assert await repo.update_metadata(uuid4(), {"title": "x"}) is None
```

(Import `_build_article` from `tests/unit/api/test_article_endpoints.py` — read its signature first; if it needs extra args, adapt. If importing it creates fixture side-effects, inline a minimal builder instead — `CanonicalArticle` requires seo/provenance etc.; copy the shape `_build_article` uses.)

- [x] **Step 2: Run — FAIL** (`uv run pytest tests/unit/services/test_article_update_metadata.py -q` → no attribute `update_metadata`)
- [x] **Step 3: Implement** all three (protocol line, in-memory ~6 lines, PG ~15 lines following `append_visual`'s row-fetch + reassignment pattern; only touch `title`, `subtitle`, `seo` keys — ignore anything else defensively).
- [x] **Step 4: Run — PASS**; `uv run ruff check` + `uv run mypy src/services/content_repositories.py src/db/repositories.py --ignore-missing-imports` (no new errors; repositories.py is pre-existing over 200 lines — do not grow other methods).
- [x] **Step 5: Commit** — `feat(db): ArticleRepository.update_metadata (AUTHOR-006 Task 1)`.

---

### Task 2: `PATCH /articles/{article_id}` + warnings + CORS

**Files:**
- Create: `src/api/routers/article_metadata.py` (< 200 lines; docstring notes the canonical_articles.py size rationale, mirroring `content_regenerate.py`)
- Create: `src/api/schemas/article_metadata.py`
- Modify: `src/api/main.py` (router import + `include_router` next to `canonical_articles_router`; add `"PATCH"` to CORS `allow_methods`)
- Test: `tests/unit/api/test_article_metadata_endpoints.py`

**Interfaces:**
- Consumes: Task 1 `update_metadata`; `require_editor_or_above`; `limiter`; `app.state.content_service` (repos via `content_service.repos.articles` — check the attribute name on `ContentService`: read `src/services/content/__init__.py` for how repos are exposed; `content_regenerate.py` accesses them — mimic it) with `app.state.article_repo` as fallback when present.
- Produces (used by Tasks 3–5): wire shape

```python
class ArticleMetadataPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=500)
    seo_title: str | None = Field(default=None, min_length=1, max_length=70)
    seo_description: str | None = Field(default=None, min_length=1, max_length=170)
    keywords: list[str] | None = Field(default=None, max_length=20)

class FieldWarning(BaseModel):
    field: str
    message: str

class ArticleMetadataResponse(BaseModel):
    id: UUID
    title: str
    subtitle: str | None
    seo: SEOMetadataResponse          # reuse from src/api/schemas/articles.py
    warnings: list[FieldWarning]
```

Warning rules (pure helper `seo_length_warnings(seo: SEOMetadata) -> list[FieldWarning]` in the schemas module): seo title outside 50–60 chars → `"SEO title is N chars; 50-60 recommended"`; seo description outside 150–160 → same shape. Computed on the PERSISTED values, returned on every PATCH (and by Task 3's regenerate).

Handler flow: parse UUID (400 on bad) → load article via repo `get` (404 `NotFoundError` if missing) → build `fields` dict from the non-None patch fields (seo_* / keywords fold into one `article.seo.model_copy(update=...)`) → reject empty patch with 422 (`CognifyValidationError`, "no fields to update") → `update_metadata` → respond with warnings. `@limiter.limit("30/minute")`, `require_editor_or_above`, `request: Request` first param.

- [x] **Step 1: Write the failing endpoint tests** — new file mimicking `test_article_endpoints.py`'s `finalize_app`/`finalize_client` fixture pattern (bare `create_app(auth_settings)`? No — copy the fixture body: those tests build a bare app; read :499-538 and reuse via import if importable, else copy). ALSO set `app.state.article_repo = <the same InMemoryArticleRepository>` so the router may use either access path. Cases:

```python
class TestPatchArticleMetadata:
    async def test_editor_updates_title_and_seo(...):
        # PATCH {"title": "New", "seo_title": "Short"} -> 200
        # body: title == "New", seo.title == "Short",
        # warnings contains a seo_title entry ("Short" is 5 chars < 50)
        # follow-up GET /articles/{id} shows the persisted values
    async def test_in_range_seo_yields_no_warnings(...):
        # seo_title 55 chars, seo_description 155 chars -> warnings == []
    async def test_viewer_gets_403(...)
    async def test_unknown_article_404(...)
    async def test_empty_patch_422(...)
    async def test_over_cap_seo_title_422(...):   # 71 chars -> schema 422
    async def test_keywords_replace_list(...)
```

- [x] **Step 2: Run — FAIL** (module missing)
- [x] **Step 3: Implement** schemas + router + registration + CORS `"PATCH"`.
- [x] **Step 4: Run new tests + FULL backend suite** (regression gate; baseline at branch: run `uv run pytest tests/unit/ -q` and record the count — develop is at 1683+). Ruff + mypy on new files clean.
- [x] **Step 5: Commit** — `feat(api): PATCH /articles/{id} metadata with SEO length warnings (AUTHOR-006 Task 2)`.

---

### Task 3: `POST /articles/{article_id}/seo/regenerate` (single field, tracked, non-persisting)

**Files:**
- Modify: `src/api/routers/article_metadata.py` + `src/api/schemas/article_metadata.py`
- Test: extend `tests/unit/api/test_article_metadata_endpoints.py`

**Interfaces:**

```python
class SeoRegenerateRequest(BaseModel):
    field: Literal["seo_title", "seo_description", "keywords"]

class SeoRegenerateResponse(BaseModel):
    field: str
    value: str | list[str]
    warnings: list[FieldWarning]      # for the proposed value
```

Flow: load article (404) → LLM = `content_service.deps.llm` (503 `ServiceUnavailableError` when None — mimic `content_regenerate._resolve_regenerate_state`) → resolve the draft via `drafts.find_by_article_id(article_id)` and bind `current_session_id`/`current_step_name("seo_regenerate")` contextvars with tokens around the call (copy the pattern from `src/services/content/section_regenerate.py:121-129`; if no draft exists, skip binding — the call simply goes untracked) → `seo = await generate_seo_metadata(article.title, article.body_markdown, llm)` (`src/agents/content/seo_optimizer.py:126`) → pick the one field → respond. **Does not persist** — the UI fills the input and the user saves via PATCH. `@limiter.limit("10/minute")`, editor+.

- [x] **Step 1: Failing tests** — FakeLLM (`FakeListChatModel`) with a valid SEO JSON response (copy a fixture response from the seo_node/optimizer tests — grep `tests/unit/agents/content` for `generate_seo_metadata`); assert 200 + the requested field only; assert a `llm_calls`-style tracking seam is exercised when a draft exists (seed `InMemoryLlmCallRepository` via a `TrackedChatModel(inner=fake, repo=...)` as the service LLM and assert one row with `call_name == "seo_regenerate"` and the draft's session id); 503 when no LLM; 404 unknown article; viewer 403.
- [x] **Step 2: Run — FAIL**
- [x] **Step 3: Implement**
- [x] **Step 4: New tests + full backend suite PASS; lint/mypy clean**
- [x] **Step 5: Commit** — `feat(api): single-field SEO regenerate, tracked via session llm_calls (AUTHOR-006 Task 3)`.

---

### Task 4: Frontend API functions + `useArticleMetadata` hook

**Files:**
- Modify: `frontend/src/lib/api/articles.ts` (~124 lines)
- Modify: `frontend/src/types/articles.ts` (add wire types)
- Create: `frontend/src/hooks/use-article-metadata.ts`
- Test: `frontend/src/hooks/use-article-metadata.test.tsx`

**Interfaces (produced for Task 5):**

```ts
// types/articles.ts additions (wire, snake_case)
export interface ArticleMetadataPatch {
  title?: string; subtitle?: string;
  seo_title?: string; seo_description?: string; keywords?: string[];
}
export interface FieldWarning { field: string; message: string }
export interface ArticleMetadataResult {
  id: string; title: string; subtitle: string | null;
  seo: { title: string; description: string; keywords: string[] };
  warnings: FieldWarning[];
}
export interface SeoRegenerateResult {
  field: string; value: string | string[]; warnings: FieldWarning[];
}

// lib/api/articles.ts
export async function patchArticleMetadata(
  articleId: string, patch: ArticleMetadataPatch,
): Promise<ArticleMetadataResult>            // apiClient.patch
export async function regenerateSeoField(
  articleId: string, field: "seo_title" | "seo_description" | "keywords",
): Promise<SeoRegenerateResult>              // apiClient.post

// hooks/use-article-metadata.ts
export function useArticleMetadata(articleId: string) {
  // useMutation(patchArticleMetadata) with onSuccess:
  //   queryClient.invalidateQueries({ queryKey: ["article", articleId] })
  //   (explicit invalidate bypasses use-article's 5-min staleTime)
  // useMutation(regenerateSeoField)
  return { save, saving, saveWarnings, regenerate, regenerating };
}
```

- [x] **Step 1: Failing hook test** — mimic `use-briefs.test.tsx` (auto-mock `@/lib/api/articles`, QueryClient wrapper with `retry:false`, `vi.clearAllMocks()` in beforeEach): save calls `patchArticleMetadata` with the patch and invalidates `["article", id]` (spy on `queryClient.invalidateQueries` via a wrapper client or assert refetch by seeding a query); regenerate returns the field value; warnings surfaced from the save result.
- [x] **Step 2: Run — FAIL** → **Step 3: Implement** → **Step 4: PASS** (`npx vitest run src/hooks/use-article-metadata.test.tsx`)
- [x] **Step 5: Commit** — `feat(frontend): article metadata api + useArticleMetadata mutations (AUTHOR-006 Task 4)`.

---

### Task 5: Header editor component + page split + restore-refetch fix

**Files:**
- Create: `frontend/src/components/articles/article-header-editor.tsx` (< 200)
- Create: `frontend/src/hooks/article-editing-state.ts` (the page's section-editing state cluster)
- Modify: `frontend/src/app/(dashboard)/articles/[id]/page.tsx` (194 → must END under 200: mount the editor in place of the `<Header>` block at :69-80, use the new hook, and add `void refetch()` in `onRestored` — the remaining stale-view hole)
- Test: `frontend/src/components/articles/article-header-editor.test.tsx`; adjust page-level tests if any break (grep first — page.tsx itself has no direct test; `SectionEditingWorkbench.test.tsx` and `article-content*.test.tsx` must stay green)

**Component anatomy (`article-header-editor.tsx`):**
- View mode: renders exactly what `<Header title subtitle>` renders today (`text-3xl font-heading font-semibold` per DESIGN.md; keep the children slot for the AI-Generated/contentType pills) + a ghost "Edit" button (Pencil icon).
- Edit mode: inputs for title, subtitle, SEO title, SEO description, keywords (comma-separated text input → `split(",").map(trim).filter(Boolean)`).
  - Char counters under SEO title (`{n}/50–60`) and SEO description (`{n}/150–160`); counter text `text-xs`, `text-neutral-500` in range, `text-warning` out of range.
  - Per-field ↻ (RefreshCw) beside SEO title/description/keywords → `regenerate(field)` fills the input (does not save).
  - Footer: Cancel (ghost) + Save (primary, disabled while nothing changed or `saving`).
  - After save: show returned `warnings` (if any) as a `text-warning` list; call `onSaved()` (parent refetches via the hook's invalidate + closes edit mode).
- Props: `{ article: ArticleDetail; onSaved?: () => void; children?: ReactNode }` — internal `useArticleMetadata(article.id)`.

**Page split (`article-editing-state.ts`):** move the cohesive cluster out of `page.tsx` — `activeSection`, `panel`, `historySectionId`, `focusVisualSection`, `openSection`, plus their setters — as `useArticleEditingState()`. Pure state hook, no fetching. Keep `publishOpen/studioOpen/galleryOpen/importOpen/toast` in the page.

- [x] **Step 1: Failing component test** — mock `@/hooks/use-article-metadata`; cases: renders title/subtitle in view mode; Edit → inputs prefilled from `article` (incl. `seo.title`); typing 20-char SEO title shows an out-of-range counter class; Save calls `save` with only changed fields (snake_case keys); regenerate button calls `regenerate("seo_title")` and fills the input from its resolved value; warnings from save are rendered.
- [x] **Step 2: Run — FAIL** → **Step 3: Implement component + hook split + mount + `onRestored` refetch fix.**
- [x] **Step 4:** `npx vitest run` (full frontend suite green); `(Get-Content 'src/app/(dashboard)/articles/[id]/page.tsx').Count` < 200; `npx tsc --noEmit` (13 pre-existing errors only).
- [x] **Step 5: Commit** — `feat(frontend): article header/SEO editor, page state split, restore refetch (AUTHOR-006 Task 5)`.

---

### Task 6: Section-draft autosave (localStorage) + "Unsaved draft" chip

**Files:**
- Create: `frontend/src/lib/draft-storage.ts` (SSR-guarded, try/caught helpers)
- Modify: `frontend/src/components/article/InlineProseEditor.tsx` (188 → stays < 200 by delegating storage to the helper)
- Test: `frontend/src/lib/draft-storage.test.ts` + extend `frontend/src/components/article/InlineProseEditor.test.tsx`

**Interfaces:**

```ts
// lib/draft-storage.ts — key format `cognify:draft:{sectionId}` and
// sectionId is already `${articleId}:${sectionIndex}` (makeSectionId),
// so keys match the spec's cognify:draft:{articleId}:{sectionIndex}.
export function loadDraft(sectionId: string): string | null
export function saveDraft(sectionId: string, markdown: string): void
export function clearDraft(sectionId: string): void
```

Every function: `if (typeof window === "undefined") return null/void;` + try/catch (quota, privacy mode) swallowing to no-op.

**Editor behaviour (InlineProseEditor):**
- On mount: `const stored = loadDraft(sectionId); if (stored !== null && stored !== initialMarkdown)` → initialize `draft` from `stored` and set `restoredFromStorage = true` (renders the chip).
- Chip: `Unsaved draft restored` — `rounded-full bg-warning-light text-warning px-2.5 py-0.5 text-xs font-medium`, next to the editor header; includes a "Discard" text-button that resets `draft` to `initialMarkdown` + `clearDraft`.
- On every draft change: `saveDraft(sectionId, next)` when `next !== initialMarkdown`, else `clearDraft(sectionId)` (debounce not required at this size; direct write is fine).
- On successful save (`onPersisted`) and on Cancel: `clearDraft(sectionId)`.

- [x] **Step 1: Failing tests** — `draft-storage.test.ts`: round-trip, clear, key format `cognify:draft:<id>` (`localStorage.clear()` in beforeEach — jsdom provides a real localStorage; this is the repo's first localStorage test, no setup changes needed). `InlineProseEditor.test.tsx` additions: seeding `localStorage.setItem("cognify:draft:art1:1", "stored text")` before render shows the chip and the textarea contains "stored text" while Save is enabled; Discard restores `initialMarkdown` and removes the key; a successful save removes the key (persistSectionUpdate is already mocked in that file).
- [x] **Step 2: Run — FAIL** → **Step 3: Implement** → **Step 4:** full frontend suite green (the `SectionEditingWorkbench.test.tsx` stateful-editor test must still pass — the autosave must not fight the `key=`-remount reset semantics: on panel switch the remount now restores from storage, which is exactly the improved behaviour; update that test's expectations ONLY if it asserts the old data-loss behaviour — read it first).
- [x] **Step 5: Commit** — `feat(frontend): localStorage autosave for section drafts + unsaved-draft chip (AUTHOR-006 Task 6)`.

---

### Task 7: Verification, live smoke, docs, PR

- [x] **Step 1:** Full suites + lint: backend `uv run pytest tests/unit/ -q`, frontend `npx vitest run`, ruff check + format --check, mypy (no new), tsc (13 pre-existing only).
- [x] **Step 2: Live smoke** — copy `.env` in, `docker compose -p cognify up --build -d api frontend` from the worktree, then: open an article → Edit header → change title + SEO title (watch counters) → per-field ↻ fills a generated value → Save → header updates WITHOUT reload (refetch) and a warning shows if out of range; verify persistence via `GET /api/v1/articles/{id}`; `llm_calls` gains a `seo_regenerate` row (usage badge total moves); section editor: type into Edit text, close the panel without saving, reopen → chip + draft restored; Save → chip gone, key removed; History restore → article body updates immediately (stale-view fix). Delete the worktree `.env` afterwards.
- [x] **Step 3: Docs** — PROGRESS row → Done + RESUME note (include the slug/status deviations and any follow-ups), BACKLOG row + velocity +5 SP, CLAUDE.md status/next action (AUTHOR-007), tick this plan's checkboxes UTF-8-safely (`[System.IO.File]` APIs).
- [x] **Step 4:** Code review (dispatch reviewer vs `develop`), fix findings, push, `gh pr create --base develop --body-file <scratchpad file>` with the deviations section. Standard footer.

---

## Self-Review (done at plan time)

- **Spec coverage:** §5.7 PATCH (Task 2), warnings-not-errors (Task 2), per-field regenerate reusing the SEO service (Task 3), §6 header editor with counters + ↻ (Task 5), PATCH via useMutation + refetch-after-persist (Tasks 4/5, incl. the concrete remaining stale hole: history-restore), autosave with the exact key format + chip (Task 6), page split under 200 lines (Task 5). Slug/status cut — documented as deviations with rationale.
- **Type consistency:** wire shape (Task 2/3) ↔ `ArticleMetadataResult`/`SeoRegenerateResult` (Task 4) ↔ component usage (Task 5) use identical field names; `update_metadata`'s `fields` keys (Task 1) match what Task 2's handler builds.
- **Known-risk callouts:** repo-access path in the router must match what test fixtures provide (called out in Task 2 Step 1); `_build_article` import may need inlining (Task 1); the Workbench stateful-editor test interaction with autosave (Task 6 Step 4); CORS PATCH (Global Constraints).
