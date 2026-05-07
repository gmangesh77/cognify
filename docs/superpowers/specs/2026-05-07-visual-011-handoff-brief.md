# Handoff Brief — VISUAL-011 (Phase 8 / Per-Section Content Editing)

> **For:** the next Claude Code session that picks up Phase 8 of Epic 10 — the
> last remaining ticket in the Visual Generation Overhaul.
> **Why this exists:** seven phases shipped autonomously on
> `claude/vibrant-chatterjee-1115a8`. This brief captures everything the next
> thread needs to land Phase 8 without re-asking what's done, what the
> boundary rules are, or where the previous session got stuck.

---

## Pre-flight (do this first)

```bash
# Confirm worktree state.
git status -sb
# Expected: claude/vibrant-chatterjee-1115a8 ... [clean].

# Sanity-check the test suite. Expect 1 pre-existing flake; everything
# Phase 1-7 should pass.
uv run pytest tests/unit -q
# Expected: 1298 passed, 1 failed (test_returns_none_when_no_key — .env
# pollution, not your problem).

# Frontend.
cd frontend && npx vitest run src/lib/visuals src/components/visuals src/components/settings/general-tab.test.tsx
# Expected: 49 passed (8 test files).
```

If anything else is failing, **stop and investigate** before adding new code —
Phases 1-7 should be a clean baseline.

---

## Where we are

- **Worktree**: `D:\Workbench\github\cognify\.claude\worktrees\vibrant-chatterjee-1115a8`
- **Branch**: `claude/vibrant-chatterjee-1115a8` (tracks
  `origin/claude/vibrant-chatterjee-1115a8`, fully pushed)
- **Commits ahead of `origin/develop`**: 12

```
0e1fbdc docs(visuals): tracking doc sweep — Epic 10 phases 1-7 marked Done
b96f6b8 feat(visuals): VISUAL-010 Phase 7 — persona settings + asset tags + My Visuals page
c8f4af5 feat(visuals): VISUAL-008 finish — gallery, import modal, article-detail mount, flag flip
fe43343 feat(visuals): VISUAL-009 Phase 6 — MinIO production rollout + cost dashboard
7a49637 feat(visuals): VISUAL-008 Phase 5 — Visual Studio frontend (core slice)
0856f7c feat(visuals): VISUAL-007 Phase 4 — Studio API endpoints
faede4f feat(visuals): VISUAL-006 Phase 3 — multi-anchor markdown injection + publishing
b6dd954 feat(visuals): VISUAL-005 Phase 2 — persona-aware planner + pipeline nodes
c175f70 docs(visuals): make Pencil-as-design-source explicit in handoff brief
154b21f docs(visuals): handoff brief for next thread (Phase 2 / VISUAL-005)
ae0c72a feat(visuals): VISUAL-004 Phase 1 — catalogue, providers, MinIO, SSRF guard
beaca71 docs(visuals): impactai review + visual-generation plan + Pencil design brief
```

- **Pencil designs**: 9 Visual Studio screens at `pencil_designs/cognify.pen`
  (x=3200). Screen 9 (`Eyi7a`) is the per-section context toolbar, which
  drives Phase 8 — read it first via `mcp__pencil__get_screenshot(nodeId="Eyi7a")`.

---

## What's done (Epic 10, Phases 1-7)

Seven of eight tickets shipped:

| Phase | Ticket | Status | Commit |
|-------|--------|--------|--------|
| 1 | VISUAL-004 | Done | `ae0c72a` |
| 2 | VISUAL-005 | Done | `b6dd954` |
| 3 | VISUAL-006 | Done | `faede4f` |
| 4 | VISUAL-007 | Done | `0856f7c` |
| 5 | VISUAL-008 | Done | `7a49637` + `c8f4af5` |
| 6 | VISUAL-009 | Done | `fe43343` |
| 7 | VISUAL-010 | Done | `b96f6b8` |
| 8 | **VISUAL-011** | **Planned** | — |

Foundations Phase 8 builds on (don't re-implement, don't refactor — use them):

- `src/services/visuals/section_html_refiner.py` — the **template** to mirror
  for `section_rewriter.py`. Same Claude-call shape, same return-result
  dataclass shape, same prompt-template pattern.
- `src/utils/llm_json.py::parse_llm_json` — required for any LLM JSON parse
  (L-002).
- `src/services/visuals/persona_directions.py` — single source of truth for
  audience persona register; the prose rewriter must reuse it (don't fork).
- `src/api/routers/visuals.py` `/section-html-refine` — example of the route
  shape: auth-gated (editor or admin), rate-limited, builds the LLM, calls
  the service, returns a typed payload.
- `src/db/image_asset_tag_repository.py` — most recent example of a small
  Postgres repo with idempotent insert + delete + list patterns. The
  Phase 8 `section_versions` repo is the same shape.
- `frontend/src/components/visuals/SectionHtmlRefinePanel.tsx` — most
  recent UI template for "Apply with AI" flows; mirror for
  `AIRewritePopover.tsx` so the diff-view and accept/reject affordances
  feel native to the existing studio.

`enable_image_planner=True` is the default. The legacy DALL-E branch in the
pipeline only fires when an operator opts back in via the env override.

---

## What's next (Phase 8 / VISUAL-011)

Authoritative source: `docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md`
§11.8. Reproduced here for convenience:

### Boundary invariants (do NOT violate)

These are the invariants that make Phase 8 safe to merge alongside the rest
of Epic 10:

- **ADR-003 (CanonicalArticle boundary)** — CanonicalArticle stays the single
  source of truth for the *active* article body. The new `section_versions`
  table is an **append-only audit sidecar** keyed on `section_id`. No other
  subsystem (publishing, planner, RAG, search) reads it.
- **ADR-004 (Transformer/Adapter publishing)** — No transformer or adapter
  is modified in this phase. `src/services/publishing/**` stays out of
  `src/services/content/` and `src/api/routers/content.py`. Ghost / Medium
  / LinkedIn keep consuming CanonicalArticle exactly as before.
- **Anchor invariants** — Image `spec_id` references and
  `ImagePlacement.heading_text` values bound to `before_heading` placements
  are first-class. The rewrite validator
  (`section_rewriter._validate_anchors`) **rejects** edits that drop or
  rename them, returning HTTP 422 with a structured diff so the frontend
  can show the editor what's blocking the save. This protects the Visual
  Studio image specs from drifting silently when prose is edited.
- **No platform leakage** — Tone presets (`shorter`, `more concrete`,
  `more conversational`, `more authoritative`) are server-side instruction
  templates inside `section_rewriter.py`. The frontend posts a preset name;
  the backend expands it.
- **Service-Layer pattern** — Route handler → Service → Repository → DB.
  No direct DB calls from `content.py` routes. Same shape as the existing
  `section_html_refiner.py`.
- **L-001 / L-002 compliance** — `model_dump(mode="json")` for any JSONB
  storage of Pydantic models, `parse_llm_json` for any LLM JSON parse.

### Task list (verbatim from plan §11.8)

Backend
- [ ] `src/services/content/section_rewriter.py` — Claude-driven section /
  paragraph prose rewrite. Mirrors `section_html_refiner.py`. Inputs:
  `section_id`, `instruction`, `scope` ("paragraph" | "section"),
  `paragraph_index?`, `current_markdown?`, `audience_persona?`. Output:
  `markdown_fragment`, `diff: WordDiff[]`, `model`, `prompt_used`,
  `tokens`, `usd`. Includes the audience-persona register from
  `persona_directions.py` and a banned-pattern list (no new headings,
  no fabricated stats, no quoted citations the user didn't approve).
  Word-level diff reuses the humanization slop-pattern scorer's diff
  infrastructure (see plan §17.2).
- [ ] `src/services/content/section_history.py` — append-only version log.
  One row per rewrite / manual save / restore.
- [ ] DB migration: `section_versions` table —
  `(id, section_id, article_id, markdown, source: "manual" | "ai" |
  "tone_preset", instruction?, model?, tokens?, usd?, created_at,
  created_by)`. New Alembic revision; chain off the most recent
  `b7c9d2e4a5f1`.
- [ ] `src/api/routers/content.py` — five endpoints from plan §5.7.1:
  `POST /api/v1/content/section-rewrite`, `POST /content/section-update`,
  `POST /content/paragraph-tone`, `GET /content/section/{id}/history`,
  `POST /content/section/{id}/restore`. Auth + RBAC (editor or admin).
  Rate limits: 30/min on rewrite, 60/min on section-update.
- [ ] Anchor-preservation validator inside `section_rewriter` —
  `_validate_anchors(original_markdown, new_markdown, image_specs)`.
  Returns a structured violation list when a `spec_id` reference or
  `before_heading` heading is dropped or renamed. Endpoint maps the
  list to HTTP 422 with the diff body.
- [ ] Backend tests: rewriter happy path, anchor rejection path,
  history append on every persist, restore round-trip, tone-preset
  expansion, RBAC enforcement on every endpoint.

Frontend
- [ ] `frontend/src/components/article/SectionContextToolbar.tsx` —
  Pencil Screen 9 (`Eyi7a`). Appears on hover / focus over a section
  in the article column. Three actions: **Edit text** (opens inline
  editor + AI popover), **Edit visual** (jumps to that section's Spec
  Card in Visual Studio — emit a callback the parent page wires up),
  **Refine layout** (opens the existing `SectionHtmlRefinePanel`
  scoped to the hovered section).
- [ ] `frontend/src/components/article/InlineProseEditor.tsx` —
  contenteditable wrapper with markdown round-trip + paragraph-level
  selection model. Anchor for the AI rewrite popover.
- [ ] `frontend/src/components/article/AIRewritePopover.tsx` —
  instruction textarea + tone preset chips (`shorter`, `more concrete`,
  `more conversational`, `more authoritative`) + diff view +
  accept / reject affordance. Wired to `/content/section-rewrite` and
  `/content/paragraph-tone`. The diff view should reuse the same
  word-level diff renderer the backend emits.
- [ ] `frontend/src/components/article/SectionHistoryDrawer.tsx` —
  lists prior versions with a diff vs. current; restore button calls
  `/content/section/{id}/restore`.
- [ ] Vitest + Testing Library tests: toolbar visibility on hover,
  popover open/close, accept/reject diff, anchor-preservation
  rejection path, history restore.
- [ ] Update `frontend/DESIGN.md` with the `SectionContextToolbar`
  pattern (it joins the existing Visual Studio section).

Cross-cutting
- [ ] Word-level diff renderer reused from §17.2 (humanization diff).
  Single source of truth for diff visualisation across image refine,
  HTML refine, and prose rewrite.

Out of scope (do **not** ship in this phase)
- Playwright E2E. The repo doesn't yet have Playwright wired in; the
  plan §11.8 calls for it but the broader scaffold (browsers, CI lane,
  fixtures) is its own deliverable. Cover the flow with Vitest +
  Testing Library tests instead, like Phase 5 did.
- Real-time collaborative editing. Editor focus and rewrite are
  single-user only.
- Auto-saving every keystroke. Manual save via the existing pattern.

### PR target

`feature/VISUAL-011-per-section-content-editing`

---

## Quality gates (run before each commit)

```bash
# Lint + format
uv run ruff check src/services/content/section_rewriter.py \
  src/services/content/section_history.py \
  src/api/routers/content.py \
  tests/unit/services/content/ tests/unit/api/test_content_endpoints.py
uv run ruff format --check <same paths>

# Type check (strict)
uv run mypy src/services/content/section_rewriter.py \
  src/services/content/section_history.py \
  src/api/routers/content.py --strict

# New-code tests
uv run pytest tests/unit/services/content/ tests/unit/api/test_content_endpoints.py -q

# Full unit suite (expect 1 pre-existing failure unrelated to your work)
uv run pytest tests/unit -q

# Frontend
cd frontend && npx vitest run src/components/article
```

---

## Gotchas

### 1. The pre-existing `.env` flake
`tests/unit/test_key_resolver.py::TestApiKeyResolver::test_returns_none_when_no_key`
fails because settings picks up a `newsapi_key` from the parent
`D:\Workbench\github\cognify\.env`. Pre-existing, **don't try to fix as part
of Phase 8**.

### 2. Reuse, don't re-invent
- For the Claude call shape, **literally copy** `section_html_refiner.py` and
  swap the prompt template + return type. Same `parse_llm_json` usage, same
  rate-limit dependency injection, same logger structure.
- For the diff renderer, **don't write a new word-diff library**. Plan §17.2
  pre-allocates the humanization slop-pattern diff for reuse here. Check
  `src/agents/content/slop_patterns.py` and the surrounding humanization
  module first.
- For audience persona, **import `get_persona_register` from
  `src/services/visuals/persona_directions.py`**. Don't fork; the planner
  already uses it.

### 3. `section_id` semantics
Articles don't currently have a stable `section_id` per section — sections
are identified by their integer `section_index` inside the
`ArticleDraft.section_drafts` JSONB array. Two clean options:
- **Option A**: derive a stable `section_id = f"{article_id}:{section_index}"`
  string. Cheap, zero schema migration on the article side.
- **Option B**: add a `uuid` to each `OutlineSection` / `SectionDraft`.
  Pure but invasive — touches the content pipeline and every existing JSONB
  row. Probably not worth it for v1.

Default to Option A unless a strong reason emerges. The
`section_versions.section_id` column is just a string under either option.

### 4. Anchor validator must be cheap
The validator runs on every save / preview. A naive regex sweep over
`heading_text` + `spec_id` references is fine for v1 — don't pull in a
markdown AST parser unless the regex approach starts misfiring.

### 5. Tone presets are server-side
The frontend posts `{ "preset": "shorter" }`; the backend expands that to
the full instruction template. **Never** let the frontend ship the prompt
text — that breaks the "no platform leakage" boundary invariant and lets
the editor accidentally craft instructions that bypass server-side
banned-pattern guards.

### 6. `enable_image_planner=True` is the default
The previous session flipped this in `src/config/settings.py`. Phase 8
doesn't need to touch it. Don't roll it back.

### 7. The 9 Pencil screens stay canonical
Read `pencil_designs/cognify.pen` Screen 9 (`Eyi7a`) before composing the
SectionContextToolbar layout. Pencil tokens (`mcp__pencil__get_variables`)
should match what's already in `frontend/DESIGN.md`. If they don't, raise
it with the user — don't silently drift.

---

## Suggested opening message for the next thread

> Pick up Phase 8 (VISUAL-011) of the Visual Generation Overhaul. Read
> `docs/superpowers/specs/2026-05-07-visual-011-handoff-brief.md` first,
> then proceed per the task list in
> `docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md`
> §11.8. Update `project-management/PROGRESS.md` to mark VISUAL-011
> In Progress as the first thing you do, and flip it to Done at the end.
> Reuse the existing `section_html_refiner.py` shape for the new
> `section_rewriter.py`. PR target name in the commit body is
> `feature/VISUAL-011-per-section-content-editing`. Pencil Screen 9
> (`Eyi7a` in `pencil_designs/cognify.pen`) is canonical for the
> `SectionContextToolbar` UI — read via `mcp__pencil__*` tools only.

---

## Quick links

- Plan: `docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md`
- ADR-003 (CanonicalArticle): `docs/architecture/adrs/ADR-003-canonical-article-boundary.md`
- ADR-004 (Transformer/Adapter): `docs/architecture/adrs/ADR-004-publishing-transformer-adapter-pattern.md`
- ADR-005 (Image Spec Planner): `docs/architecture/adrs/ADR-005-image-spec-planner-and-object-storage.md`
- Pencil design brief (9 screens): `docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md`
- Phase 2 handoff (history): `docs/superpowers/specs/2026-05-07-visual-generation-next-thread-brief.md`
- Storage rollout runbook: `docs/deployment/visual-storage-rollout.md`
- BACKLOG: `project-management/BACKLOG.md` (Epic 10 section)
- PROGRESS: `project-management/PROGRESS.md` (Epic 10 section)
- LEARNINGS: `docs/LEARNINGS.md` (read before changing JSONB / LLM JSON / status fields)
