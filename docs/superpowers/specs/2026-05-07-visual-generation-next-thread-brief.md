# Handoff Brief — Visual Generation Overhaul, Next Thread

> **For:** the next Claude Code session that picks up Phase 2 (VISUAL-005).
> **Why this exists:** Phase 1 shipped autonomously via repeated TodoWrite-driven steps; the user wants Phase 2 to start without re-asking what's done, what's deferred, and what the boundary rules are.

---

## Pre-flight (do this first)

```bash
# Confirm branch + cleanliness.
git status -sb
# Expected: claude/vibrant-chatterjee-1115a8 ... [ahead 2]; clean working tree.

# Read the plan + the ADR + the design brief.
# Plan:        docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md
# ADR-005:     docs/architecture/adrs/ADR-005-image-spec-planner-and-object-storage.md
# Pencil brief: docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md
# Architecture review: docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW.md

# Confirm Phase 1 lands clean.
uv run pytest tests/unit/services/visuals/ tests/unit/api/test_visuals_endpoint.py -q
# Expect: 130 passed.

# Confirm lint + typing on Phase 1 modules.
uv run ruff check src/services/visuals/ src/api/routers/visuals.py
uv run mypy src/services/visuals/ src/api/routers/visuals.py --strict
# Expect: All checks passed; Success: no issues found in 15 source files.
```

---

## Where we are

- **Worktree**: `D:\Workbench\github\cognify\.claude\worktrees\vibrant-chatterjee-1115a8`
- **Branch**: `claude/vibrant-chatterjee-1115a8` (tracks `origin/develop`)
- **Commits ahead of `origin/develop`**: 2
  1. `beaca71` — `docs(visuals): impactai review + visual-generation plan + Pencil design brief`
  2. `ae0c72a` — `feat(visuals): VISUAL-004 Phase 1 — catalogue, providers, MinIO, SSRF guard`
- **Pencil designs**: 9 screens in `pencil_designs/cognify.pen` at x=3200, y=0..11600 (don't touch the existing 6 screens at x=0).

---

## What's done (Phase 1 / VISUAL-004)

Foundation. Everything later phases depend on. Touched files:

**Settings + ADR**
- `docs/architecture/adrs/ADR-005-image-spec-planner-and-object-storage.md` — full boundary contract, mirrors ADR-003/ADR-004 patterns.
- `src/config/settings.py` — visual gen, MinIO, fetch-image-safety fields. `enable_image_planner` defaults to `False` until end of Phase 5.

**Service module — `src/services/visuals/`**
- `visual_styles.py` — 12-style catalogue, `ROLE_STYLE_DEFAULTS`, `compose_style_override()`, `planner_catalogue_block()`. **Single source of truth** — exposed via API; no mirrored TS catalogue.
- `persona_directions.py` — 8 personas with `get_persona_register()` (default `general_business`).
- `banned_cliches.py` — 10-rule block + per-category register reinforcement.
- `providers/base.py` — `ImageProvider` Protocol + `ImageRenderResult` Pydantic schema + 4 error subclasses (`ImageProviderError`, `…Quota…`, `…Timeout…`, `…InvalidRequest…`).
- `providers/{dalle_3,gemini_flash,gemini_3_pro,imagen_4}.py` — 4 concrete providers. DALL-E wraps the existing `src/agents/content/illustration_generator.OpenAIDalleGenerator`. Google providers lazy-import `google.generativeai` with a clear `ImageProviderError` if missing.
- `providers/_google_base.py` — shared `IMAGEN_ASPECT_MAP`, `aspect_instruction()`, `import_google_genai()`, `make_render_result()`.
- `registry.py` — `ImageProviderRegistry` (mirrors `src/services/trends/registry.py`).
- `object_storage.py` — `ObjectStorage` Protocol, `LocalDiskObjectStorage` (default), `MinioObjectStorage` (lazy-import), `select_object_storage(settings)`, `make_object_key()`.
- `safe_http.py` — `SafeHttpFetcher` with full SSRF defence (scheme allowlist, userinfo rejection, comprehensive CIDR blocking IPv4+IPv6, HEAD-then-streamed-GET with magic-byte MIME sniff, redirect re-validation per hop).
- `__init__.py::init_registry(settings)` — credential + flag-aware provider registration; logs `visual_provider_skipped` when something's missing instead of crashing boot.

**API**
- `src/api/routers/visuals.py` — `GET /api/v1/visuals/styles` returning catalogue + personas + cliché block + planner block.
- `src/api/main.py` — router mounted under `api_v1_prefix`, tagged `"visuals"`.

**Local-dev infra**
- `docker-compose.minio.yml` — MinIO + bucket-init container. `cognify-visuals` bucket auto-created, public-read policy. Use as: `docker compose -f docker-compose.yml -f docker-compose.minio.yml up -d minio`.

**Tests** — 130 new, all passing:
- catalogue (16), persona (7), banned-cliches (8), SSRF (18), object-storage (13), provider Protocol/errors (6), DALL-E provider (6), Google providers (13), registry (7), init_registry (6), styles endpoint (7), provider package init (3).

**Project management**
- `project-management/BACKLOG.md` — Epic 10 added: VISUAL-004 (Done in spirit; not formally closed yet) through VISUAL-011, 89 SP total.
- `project-management/PROGRESS.md` — VISUAL-004 marked In Progress in the Epic 10 table. **Update to Done** at top of next thread once VISUAL-005 begins.

---

## What's next (Phase 2 / VISUAL-005)

The plan is in `docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md` §11.2. Phase 2 ports the **persona-aware planner**, the **prompt composer**, the **per-section + per-article planning logic**, and the two new **LangGraph pipeline nodes**.

**Boundary invariants (do not violate — see ADR-005 §"Boundary invariants enforced by this phase" and the same callout in the plan's Phase 8 section):**

- No imports from `src/services/publishing/` in any new visuals code.
- The planner is one Claude call per article — not per section bundle. Cache when re-running.
- `image_specs`, `page_art_direction`, `audience_persona` are added to `CanonicalArticle` as **optional, default-empty fields**. Existing articles keep working without re-renders. ADR-003 amendment is in ADR-005, not a new ADR.
- Each rendered visual carries `spec_id` linking to its plan — content-layer concept, not publishing.
- Tone preset templates (`shorter`, `more concrete`, …) live server-side. Frontend posts a preset name; backend expands it.
- Use `parse_llm_json()` from `src/utils/llm_json.py` for any LLM JSON parsing (L-002).
- Use `model_dump(mode="json")` when persisting Pydantic to JSONB columns (L-001).

### Phase 2 task list (verbatim from plan §11.2)

- [ ] `src/services/visuals/prompt_composer.py` — port `_build_banner_prompt` from impactai's `apps/api/routers/generate.py:2988`. Branches: prompt_override × has_style × style_text × no_text_clause + the "Composition reference IGNORED" trick. Cap style_text at 800 chars (already supported via `compose_style_override`). 800-char `no_text_clause` block. Inject `aspect_instruction()` for Gemini Flash. 10–15 unit tests covering all 4 decision-tree branches × multiple styles × overrides.
- [ ] `src/services/visuals/default_prompts.py` — Python port of impactai's `defaultSectionVisualPrompts.ts`. One default prompt seed per `ImageRoleStyle` literal.
- [ ] `src/services/visuals/image_planner.py` — `plan_section_images(section, article_topic, page_art_direction, brand_context, audience_persona, target_audience, max_images, llm)` and `plan_article_cover(article, page_art_direction, audience_persona, llm)`. Planner prompt MUST include `planner_catalogue_block()`, persona register fragment from `get_persona_register()`, banned-cliché block from `cliche_block_for_style()`. Fallback path `_fallback_specs()` synthesises a single spec from `(role, ROLE_STYLE_DEFAULTS, default_aspect)` when LLM returns garbage or empty.
- [ ] `src/agents/content/image_planner_node.py` — LangGraph node: when `_images_enabled(state)`, plan article cover then per-section.
- [ ] `src/agents/content/image_render_node.py` — LangGraph node: fan out `render_spec(spec, page_dir, registry)` calls with `asyncio.Semaphore(settings.image_render_concurrency)` (default 3). `render_spec` calls `prompt_composer.build_prompt`, routes to provider, persists via `select_object_storage(settings)`, builds an `ImageAsset` with the full metadata extension (§4.2 of plan).
- [ ] **CanonicalArticle additions** in `src/models/canonical.py` (or wherever it lives — grep first):
  - `image_specs: list[ImageSpec] = []`
  - `page_art_direction: str | None = None`
  - `audience_persona: str | None = None`
  - Plus the new `ImageSpec`, `ImagePlacement`, `ImageRoleStyle`, `ImageAspectRatio`, `PlacementAnchor` types from plan §4.1 — likely in `src/models/visual.py`.
- [ ] **`ImageAsset.metadata` JSONB extension** — append `{spec_id, role_style, visual_style, aspect_ratio, placement_anchor, provider, model, prompt_used, cost_usd, generation_ms}`. No DB migration (already JSONB).
- [ ] Wire nodes into `src/agents/content/pipeline.py` between `seo_optimize` and `generate_charts`. Gate everything on `settings.enable_image_planner`. Default flag stays `False` — flip to `True` only at the end of Phase 5.
- [ ] Thread `audience_persona` from existing per-article params (already in CONTENT-006 humanization flow — grep for `audience_persona` in `src/agents/content/`) into the planner.
- [ ] FakeLLM fixtures in `tests/fixtures/visual_planner/` — realistic JSON for ~5–6 archetypal sections (intro, deep-dive, comparison, quote, conclusion) × 3 personas (general_business, cto, marketer).
- [ ] Stub provider in `tests/stubs/stub_image_provider.py` returning a 1×1 PNG so the full pipeline runs without hitting Google AI in CI.
- [ ] Integration test: full pipeline with planner + render + LocalDisk object_storage stub. Assert CanonicalArticle has `image_specs` aligned with `visuals` and every visual carries `spec_id` linking to a spec.
- **PR target**: `feature/VISUAL-005-persona-aware-planner-pipeline`.

### Phase 2 decomposition for parallel work (when subagents are available)

If the next thread has working subagents (this thread didn't — see Gotchas), the following slices are independent and can run in parallel after the foundation pieces land:

| # | Slice | Depends on | Output |
|---|-------|-----------|--------|
| F1 | CanonicalArticle additions + `ImageSpec` Pydantic models | (foundation) | `src/models/visual.py` extensions, `src/models/canonical.py` extensions |
| F2 | `prompt_composer.py` + tests | F1 | full prompt-composition module |
| F3 | `default_prompts.py` + tests | F1 | per-role default prompt seeds |
| P1 | `image_planner.py` + FakeLLM fixtures | F1, F2, F3 | the actual planner |
| P2 | `image_planner_node` + `image_render_node` + stub provider | F1, F2, P1 | LangGraph nodes |
| P3 | Pipeline wiring + integration test | P1, P2 | green pipeline run with `enable_image_planner=True` |

Sequence: F1 → (F2, F3 in parallel) → P1 → P2 → P3.

---

## Design source of truth (when you get to UI work)

**Phase 2 is pure backend** — planner, prompt composer, LangGraph nodes, CanonicalArticle additions. No UI work in this phase, no Pencil traffic.

For every later phase that touches frontend (Phase 4 API consumed by frontend, Phase 5 the Visual Studio panel, Phase 7 saved-asset gallery + Settings UI, Phase 8 per-section context toolbar):

- **The Pencil file is canonical.** All UI structure, spacing, component anatomy, and state variants come from `pencil_designs/cognify.pen`. Don't compose layouts from scratch or improvise component anatomy — read the relevant screen first.
- **The 9 Visual Studio screens** ship the full anatomy:
  - Screen 1 (`lZhq7`) — Article Detail with Visual Studio panel (the anchor; all chip rails, bento controls, spec-card states are derived here)
  - Screen 2 (`pb0Hz`) — Spec Card 6 lifecycle states (idle, planning, generating, done, error, refining)
  - Screen 3 (`e47sQG`) — Plan-Visuals Modal (planning state + variant picker)
  - Screen 4 (`a7sfx`) — Edit Drawer (role / style / aspect / placement / alt / prompt / provider override + footer)
  - Screen 5 (`SL2pb`) — Saved Asset Gallery Modal (filter chips, sidebar facets, masonry grid, hover overlay)
  - Screen 6 (`g6P48`) — Section HTML Refine Panel (split-view diff + Apply-with-AI textarea)
  - Screen 7 (`P4R0EO`) — Image Import Modal (Upload tab + Fetch-from-URL with SSRF check feedback)
  - Screen 8 (`TVcmU`) — UsageBadge (compact, expanded with provider breakdown + sparkline, limit-warning)
  - Screen 9 (`Eyi7a`) — Per-Section Context Toolbar (toolbar visible / inline edit + AI rewrite popover / diff + history drawer)
- **All 9 live at `x=3200, y=0..11600`** in the canvas. The Pencil design brief at `docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md` describes each screen; the file itself is the authoritative reference for pixel-level details.
- **Read the Pencil file via MCP only** — `mcp__pencil__get_editor_state`, `mcp__pencil__snapshot_layout(parentId=<id>, maxDepth=2-3)`, `mcp__pencil__get_screenshot(nodeId=<id>)`. **Never** use `Read`/`Grep`/`Edit` on `.pen` files (encrypted; only Pencil's MCP tools can read them — see the design brief's "Crucial constraint" note).
- **Design tokens**: pull from the Pencil document via `mcp__pencil__get_variables()`. Tokens are also documented in `frontend/DESIGN.md` — keep them in sync. Primary `#DC2626`, warm slate neutrals, Space Grotesk + Inter, 4px grid, 12px modal radius. Don't introduce new colours or fonts without updating both `frontend/DESIGN.md` and the `.pen` variables.
- **Don't redesign**. If a flow looks wrong on the canvas, raise it with the user — don't silently change it in code. The user reviewed and approved all 9 screens (commit `ae0c72a`'s lineage covers the design phase).

## Gotchas

### 1. Subagents may be unreachable
This thread tried `Agent({subagent_type: 'python-pro', ...})` and `Agent({subagent_type: 'backend-security-coder', ...})`. Both completed in seconds with the message **"Your organization does not have access to Claude. Please login again or contact your administrator."** No work was done by the subagents. The next thread should test subagent dispatch with a tiny task first; if it fails, fall back to sequential per-module work like Phase 1 did.

### 2. Two pre-existing test failures
Running `uv run pytest tests/unit -q` will show 2 failures:
- `tests/unit/test_key_resolver.py::TestApiKeyResolver::test_returns_none_when_no_key` — settings picks up a `newsapi_key='ded097...'` from an environment variable; test expects None. **Cause**: a `.env` exists in the **main repo root** (`D:\Workbench\github\cognify\.env`) and pydantic-settings inherits it. Not caused by Phase 1.
- `tests/unit/api/test_topic_endpoints.py::TestTopicEndpoint503::test_embedding_failure_returns_503` — passes when run in isolation; flake from test ordering. Not caused by Phase 1.

Both files were untouched by Phase 1. Don't try to fix them as part of Phase 2.

### 3. Lazy imports for Google AI + MinIO
`google-generativeai` and `minio` are NOT in `pyproject.toml` deps. The provider/storage modules import them lazily and raise a clear `ImageProviderError`/`ObjectStorageError` if missing. **For Phase 2 to actually exercise Imagen/Gemini end-to-end** in integration tests, you'll need a stub provider (already on the task list) — do NOT add the real packages until Phase 6 calls for it. Tests must mock via `sys.modules` injection (see `tests/unit/services/visuals/providers/test_google_providers.py::_install_fake_genai`).

### 4. Existing DALL-E generator
The legacy hero generator lives at `src/agents/content/illustration_generator.OpenAIDalleGenerator` and is wrapped by our new `DalleThreeProvider`. **Don't delete or rewrite the legacy generator** — it's still wired into `src/agents/content/pipeline.py:203` and runs when `enable_image_planner=False`. Phase 5 flips the flag and the legacy path becomes dormant; Phase 7 or later cleanup can decide whether to delete.

### 5. Pencil designs are at x=3200
The 9 Visual Studio screens (`lZhq7` Screen 1 through `Eyi7a` Screen 9) live at `x=3200, y=0..11600` in `pencil_designs/cognify.pen`. Don't move them. Don't touch the existing 6 screens at `x=0`. The 30 reusable components live in the `x=1540..2660` band — leave them alone too. If you need to verify a screen's structure, use `mcp__pencil__snapshot_layout(parentId=<id>, maxDepth=2)`.

### 6. `pyproject.toml` constraints
- ruff line-length: 88 chars. Use multi-line string concatenation rather than chasing edge-case rule disables.
- mypy strict: `disallow_any_generics`, `warn_return_any`. When wrapping stdlib calls that return `Any`, annotate the local variable explicitly (e.g. `cleaned: str = parsed._replace(...).geturl()`).
- pytest-asyncio mode is `auto` — `@pytest.mark.asyncio` is implicit but I add it explicitly for clarity.
- `pytest-httpx` and `respx` are NOT installed. Use `httpx.MockTransport` for HTTP-client tests (see `tests/unit/services/visuals/test_safe_http.py` for the pattern).

### 7. CRLF warnings on `git add`
Windows worktree → many `LF will be replaced by CRLF` warnings on staging. Harmless. Don't try to "fix" them by changing `core.autocrlf`.

### 8. `.claude/rules/security.md` and `.claude/rules/testing.md`
Pulled in via system reminders during a session. Note: the `security.md` mentions OWASP A01-A03/A07/A09 — Phase 2's planner prompt composition is a place where prompt-injection (A03) defence matters. Use `parse_llm_json` and structured prompt templates (no user-controlled prompt structure) per the rule.

---

## Quality gates (run before any commit)

```bash
# Lint + format
uv run ruff check src/services/visuals/ src/agents/content/ src/api/routers/visuals.py tests/unit/services/visuals/ tests/unit/api/test_visuals_endpoint.py
uv run ruff format --check src/services/visuals/ src/agents/content/ src/api/routers/visuals.py tests/unit/services/visuals/ tests/unit/api/test_visuals_endpoint.py

# Type check (strict)
uv run mypy src/services/visuals/ src/agents/content/image_planner_node.py src/agents/content/image_render_node.py src/api/routers/visuals.py --strict

# New-code tests
uv run pytest tests/unit/services/visuals/ tests/unit/api/test_visuals_endpoint.py tests/integration/visuals/ -q

# Full unit suite (expect 2 pre-existing failures unrelated to your work)
uv run pytest tests/unit -q
```

---

## Commit conventions

Per `CLAUDE.md` §"Git Workflow":

- Branch naming: `feature/VISUAL-005-persona-aware-planner-pipeline` for Phase 2 work. **But this thread is on `claude/vibrant-chatterjee-1115a8` (a worktree-managed branch)** — don't switch off it without coordinating with the user. Commits accumulate on the chatterjee branch and merge later.
- Conventional commits: `feat(visuals):`, `fix(visuals):`, `test(visuals):`, `docs(adr):`, etc.
- Include `AB#<id>` in commit footer when the user provides Azure Boards work-item IDs (none provided yet for Epic 10).
- Co-author trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  ```
- Phase 1's commit: `ae0c72a` is the example to follow for Phase 2's commit message style — boundary-invariant callouts, deliverables list, test count.

---

## TodoWrite cadence (what worked in Phase 1)

The user's environment surfaces TodoWrite reminders frequently. Pattern that worked:

1. Set up the full task list at the start of the phase (one item per major file/module).
2. Mark exactly one item `in_progress` at a time.
3. Update **before** running the next batch of tool calls — the harness dings the reminder if the list goes stale.
4. Add new sub-items as soon as a deviation is discovered (e.g. "fix mypy errors" if mypy surfaces a problem).
5. Don't bundle small completions — flip status as each module lands so the user sees real-time progress.

---

## Quick links

- ADR-003 (CanonicalArticle): `docs/architecture/adrs/ADR-003-canonical-article-boundary.md`
- ADR-004 (Transformer/Adapter): `docs/architecture/adrs/ADR-004-publishing-transformer-adapter-pattern.md`
- ADR-005 (this epic): `docs/architecture/adrs/ADR-005-image-spec-planner-and-object-storage.md`
- Implementation plan: `docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md`
- Pencil design brief (9 screens): `docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md`
- Architecture review against impactai: `docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW.md`
- Engineering learnings (read before changing JSONB / LLM JSON / status fields): `docs/LEARNINGS.md`
- BACKLOG: `project-management/BACKLOG.md` (Epic 10 section)
- PROGRESS: `project-management/PROGRESS.md` (Epic 10 section — **update VISUAL-004 to Done at start of next thread**)

---

## Suggested opening message for the next thread

> Pick up Phase 2 (VISUAL-005) of the Visual Generation Overhaul. Read
> `docs/superpowers/specs/2026-05-07-visual-generation-next-thread-brief.md`
> first, then proceed per the task list in
> `docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md` §11.2.
> Update `project-management/PROGRESS.md` to mark VISUAL-004 Done and VISUAL-005
> In Progress as the first thing you do.
