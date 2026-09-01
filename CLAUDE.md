# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Cognify is a self-driving content platform that discovers trends, runs multi-agent research, and generates publication-ready articles with visuals.

## Tech Stack
- **Backend**: Python 3.12+, FastAPI, LangChain + LangGraph, SQLAlchemy (async), structlog
- **LLMs**: Claude Sonnet 4 (primary + drafting), Stable Diffusion XL (images)
- **Data**: PostgreSQL 16, Milvus (vector DB), Redis (cache + task broker)
- **Frontend**: Next.js 15 + React 19 + TypeScript, Tailwind CSS
- **Testing**: pytest + pytest-asyncio (backend), Vitest + Testing Library (frontend)
- **CI/CD**: GitHub Actions, Docker
- **Package Manager**: uv (backend), npm (frontend)

## Commands
- Build: `docker compose build` or `make build`
- Test all: `make test` (runs backend + frontend)
- Test backend: `uv run pytest tests/unit/ -q`
- Test frontend: `cd frontend && npx vitest run`
- Single test: `uv run pytest tests/path/to/test_file.py::test_name -v`
- Lint: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/ --ignore-missing-imports`
- Lint fix: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/`
- Dev backend: `uv run uvicorn src.api.main:app --reload --port 8000`
- Dev frontend: `cd frontend && npm run dev`
- Full stack (Docker): `make dev` or `docker compose up --build -d`
- Infra only: `make up` (starts postgres, milvus, redis)
- Install deps: `uv sync --dev` (backend), `cd frontend && npm ci` (frontend)
- Migrations: `uv run alembic upgrade head`
- New migration: `uv run alembic revision --autogenerate -m "description"`

## Project Structure
```
src/
  agents/       # LangGraph agent definitions (orchestrator, researcher, writer, content pipeline)
  pipelines/    # Trend discovery, research, content gen, visual gen
  services/     # Business logic (topic ranking, SEO, content, research, milvus)
  api/          # FastAPI routes, middleware, auth (JWT + RBAC)
  models/       # Pydantic models (content, research, settings) + SQLAlchemy tables
  db/           # Database engine, repositories, Alembic migrations
  utils/        # Shared utilities (logging with sensitive field redaction, LLM JSON parsing)
  config/       # pydantic-settings (all env vars prefixed COGNIFY_)
frontend/       # Next.js 15 app (app router, hooks, components, types)
alembic/        # Database migration versions
```

## Architecture
- **Content Pipeline**: Orchestrator → Research Agents (parallel) → Writer Agent → Visual Agent → CanonicalArticle
- **CanonicalArticle** is the central boundary contract between content generation and publishing (see ADR-003). Publishing consumes it via Transformer/Adapter pairs per platform (see ADR-004).
- **Service Layer Pattern**: Route handlers → Service → Repository → Database. No direct DB calls from routes.
- **TrendSource Protocol + Registry**: All 5 trend sources (HN, Google Trends, Reddit, NewsAPI, arXiv) implement a common protocol. Single registry-driven router.
- **Settings**: `src/config/settings.py` uses pydantic-settings with `COGNIFY_` env prefix. All configuration externalized.
- **Auth**: JWT (RS256) with RBAC (admin/editor/viewer). Token expiry: 1440 min (24h access), 7d refresh.
- **Frontend API layer**: Hooks in `frontend/src/hooks/` call API functions in `frontend/src/lib/api/`, which use axios via `apiClient`.

## Architecture Decisions
- See @docs/architecture/HIGH_LEVEL_ARCHITECTURE.md for system design
- See @docs/architecture/adrs/ for decision records
- All new architectural decisions MUST be recorded as ADRs

## Frontend Design System
- See @frontend/DESIGN.md for colors, typography, spacing, and component patterns
- Primary color is `#DC2626` (red) — DO NOT change without updating DESIGN.md and Pencil designs
- Fonts: Space Grotesk (headings), Inter (body)
- All UI changes must follow the design guidelines

## Coding Standards
- Write tests BEFORE implementation (TDD — Red/Green/Refactor)
- All functions < 20 lines, all files < 200 lines, max 3 params
- Named exports only — no default exports
- Use Pydantic for all data validation and serialization
- Input validation on all external inputs (Pydantic models + FastAPI deps)
- Structured logging with correlation IDs via structlog
- No `Any` types — use strict typing with mypy strict mode
- No inline styles in frontend — use Tailwind CSS
- No direct database calls from route handlers — use service layer
- No print() in production code — use structlog
- No hardcoded configuration — externalize via pydantic-settings

## Azure Boards
- **Organization**: https://dev.azure.com/signity
- **Project**: Cognify
- **Work item prefix**: `AB#<id>` in commit messages and PR descriptions to link to Azure Boards
- **CLI (Windows)**: `powershell.exe -Command "& 'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd' boards <command>"` (az.cmd requires PowerShell on Windows due to path spaces)
- **CLI (Linux)**: `az boards <command>`
- When completing a ticket: update Azure Boards work item state to Closed
- When starting a ticket: update Azure Boards work item state to Active

## Environment
- **Package manager**: uv (backend), npm (frontend) — all Python commands use `uv run` prefix
- **Install deps**: `uv sync --dev` (backend), `cd frontend && npm ci` (frontend)
- **Windows Conda fallback**: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ...`
- **Linux**: Standard uv/npm, Docker available for full stack

## Git Workflow
- Branch: feature/{TICKET}-description or fix/{TICKET}-description
- Commits: conventional commits (feat:, fix:, chore:, docs:, test:)
- Always run full test suite before committing
- PR requires: tests passing + security scan clean + human review
- Include `AB#<work-item-id>` in PR descriptions to link to Azure Boards
- **NEVER create files with colons (`:`) in their names** — Windows/NTFS cannot handle them and they block `git pull` on Windows machines. This applies to ALL platforms including Linux.

## Definition of Done
Before marking ANY task complete, verify:
1. All acceptance criteria met
2. Unit tests written and passing (≥80% coverage on new code)
3. Integration tests for API/service boundaries
4. SAST scan passes (zero Critical/High findings)
5. No hardcoded secrets (secret scan passes)
6. Code reviewed (human review mandatory for AI-authored code)
7. Documentation updated (API docs, README, changelog)
8. Monitoring: health endpoints + structured logging + metrics

## Context Files
- @docs/architecture/HIGH_LEVEL_ARCHITECTURE.md — System design
- @docs/testing/TEST_STRATEGY.md — Test pyramid and approach
- @docs/ci-cd/PIPELINE.md — CI/CD stages and checklist
- @docs/security/SECURITY_CHECKLIST.md — Sprint security gates
- @docs/observability/OBSERVABILITY_PLAN.md — SLIs, SLOs, alerts
- @project-management/BACKLOG.md — Product backlog (full acceptance criteria)
- @project-management/PROGRESS.md — **START HERE** — ticket status, branches, links to plans/specs
- @project-management/RISK_REGISTER.md — Active risks

## Workflow: Plans and Specs
Implementation artifacts live in `docs/superpowers/`:
- **Specs** (`docs/superpowers/specs/`): Design documents created before implementation
- **Plans** (`docs/superpowers/plans/`): Step-by-step task breakdowns with checkboxes

Naming convention: `{date}-{ticket-id}-{description}.md` (e.g., `2026-03-12-api-001-fastapi-setup.md`)

**New session checklist**: Read `project-management/PROGRESS.md` to see what's done/in-progress, then check the relevant plan file for detailed task state.

## Change Protocol
Before modifying any interface, field constraint, or status value: grep all callers/consumers, check test assertions, and verify the full dependency chain. Never change a contract without understanding its blast radius.

## Engineering Learnings
See @docs/LEARNINGS.md for hard-won debugging lessons. **Read before making changes.** Key rules:
- **L-001**: Use `model_dump(mode="json")` for JSONB storage, never bare `model_dump()`
- **L-002**: Use `parse_llm_json()` for LLM responses, never bare `json.loads()`
- **L-003**: Status field changes have 8+ consumer sites — grep all before changing
- **L-004**: Call `ensure_collection()` after every `MilvusService()` instantiation
- **L-005**: Integration tests leak data to real DB — clean after running
- **L-006**: `generate_outline()` runs the FULL pipeline, not just outline
- **L-007**: FakeLLM tests need 10+ responses per pipeline invocation
- **L-008**: Azure DevOps work item terminal states: User Story/Bug/Epic → `Closed`, Task → `Completed`
- **L-009**: Ghost 5+ requires Lexical format — raw `html` field is silently ignored
- **L-010**: `COGNIFY_ENCRYPTION_KEY` must be stable in `.env` — ephemeral keys make DB-stored API keys unrecoverable
- **L-011**: Outline gate: `ContentGraphDeps(stop_after_outline=True)` to stop after planning; seed `outline` + `status=outline_complete` to resume; `_graph_deps()` must never return `None`
- **L-012**: Brief values are copied onto the session at `start_session` (inline > brief > default); nothing downstream may read the brief row — `brief_id` is provenance only
- **L-013**: Section ids are `{article_id}:{outline_index}` (0-based H2); `md_index_for()` in `section_history_contracts.py` is the only conversion to `split_sections` space — never add ±1 elsewhere; `provenance.research_session_id` is the topic id, resolve drafts via `find_by_article_id`
- **L-014**: Prompts are registry keys — never add a module-level prompt constant; register a `PromptTemplate` in `src/agents/prompts/defaults_*.py` and call `render_prompt(key, **vars)` at call time; overrides are one snapshot per run/request
- **L-015**: Model fields are not columns — new model fields need column + `create()` + `_to_model()` + PG round-trip test

## Current Status

See @project-management/PROGRESS.md for full ticket status.

**Epics 0-4, 6-9:** All complete (Design, Trend Discovery, Research, Content Gen, Visual Assets, Dashboard, API & Auth, Architecture, Infrastructure).
**Epic 5 (Publishing):** Ghost, Medium (PR #43), LinkedIn (PR #48), Publication Tracking done. WordPress (PUBLISH-002) in backlog.
**Epic 10 (Visual Generation Overhaul):** All 8 phases shipped (VISUAL-004..VISUAL-011, 89 SP) — merged to `develop` via PR #54. The new pipeline (`enable_image_planner=True`) is the default. Per-section prose editing (toolbar / inline editor / AI rewrite popover / history drawer) is live on the article-detail page. See `docs/deployment/visual-storage-rollout.md` for the production MinIO + cost-dashboard runbook.
**Post-Epic 10 housekeeping (PR #55):** `.env` flake fix + INFRA-006 (SSRF guard reuse for trend sources) + CONTENT-007 (structure-aware humanization) + DASH-007 (humanization diff panel) + Playwright E2E scaffolding (smoke test + opt-in CI lane).
**INFRA-005 (Frontend Status Alignment):** Done (PR #46).
**CI/CD & Docker:** Implemented — Dockerfiles (api, worker, frontend), GitHub Actions (ci.yml, cd.yml, e2e.yml), Makefile, docker-compose with full stack.
**Test suite:** 2043 backend unit tests (0 failures) + 670 frontend Vitest tests (incl. the 200-line file-size budget guard) + 2 Playwright specs (smoke + AUTHOR-014 create-article flow against a mocked backend; `cd frontend && PLAYWRIGHT_PORT=3100 npm run e2e` — PowerShell: `$env:PLAYWRIGHT_PORT=3100; npm run e2e` — beside the Docker stack).
**Epic 11 (Supervised Authoring, started 2026-08-19):** program plan `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md`; ADR-006/007 accepted. **Done:** AUTHOR-001 live SSE session progress + `/research/[id]` page (`06439e9`); AUTHOR-002 opt-in outline approval gate + cancel (PR #73, `30f1a36`, migration `a9d4e2f7c1b8`, gate off by default via `COGNIFY_REQUIRE_OUTLINE_APPROVAL`); AUTHOR-003 Brief as authoring input (ADR-007; `briefs` table + `/briefs` CRUD, `brief_id`/`save_as_brief` on session create, `suggested_brief` from topic analysis, Generate-modal brief picker; migration `b3c7e1f9a2d4`). AUTHOR-004 per-section regenerate-with-feedback (PR #76, `7ef590c`; `POST /content/section-regenerate`: one tracked LLM call `step_name=section_regenerate`, candidate version row `source=regenerate`, accept via section-update; fixed the section-id off-by-one at the root — L-013). AUTHOR-005 usage/cost badge (PR #77, 2026-08-24: `GET /research/sessions/{id}/usage` + `GET /articles/{id}/usage`, `COGNIFY_LLM_PRICING_JSON` over `DEFAULT_LLM_PRICING` in `src/services/usage.py`, `UsageBadge` in session header + article sidebar; image cost from recorded asset metadata, never settings). INFRA-007 Celery worker dispatch (2026-08-24, `feature/INFRA-007-celery`: `COGNIFY_TASK_DISPATCH=celery` moves the whole pipeline to the worker container — `PipelineDispatcher` seam, `src/tasks/`, bootstrap factory, cooperative cancellation with "cancelled" terminal-by-intent; default `inprocess` unchanged). **Phase A complete.** AUTHOR-006 metadata editor + autosave (2026-08-24, `feature/AUTHOR-006-metadata`: `PATCH /articles/{id}` with SEO length warnings + `POST /articles/{id}/seo/regenerate`, header/SEO editor with counters + per-field ↻, section-draft localStorage autosave, stale-view fixes). AUTHOR-007 article status + filters + Resume (2026-08-25, `feature/AUTHOR-007-status`: `ArticleStatus` draft/in_review/approved/published, migration `d5e8f2a1c3b9`, `GET /articles?status=` filter, publish marks `published`, status pill + transitions in the header, filter pills + resumable-sessions strip on `/articles`). AUTHOR-008 length target + content type through the outliner (2026-08-25, PR #82 → `608f4fc`: `src/agents/content/length_budgets.py` — short/medium/long/pillar word budgets, `COGNIFY_LENGTH_BUDGETS_JSON` overrides, content-type guidance in the outline prompt; guardrails outline-derived — expansion floor 0.6×outline total; outline save recomputes `total_target_words`; budget chip + live total in outline review). Fix: dead View-article button (PR #81 → `bbea9e9`: session→article resolves via `article_drafts.find_latest_by_session`, not the topic-id-bearing provenance — L-013; `session_events.py` limiter decorator order fixed). INFRA-008 platform bundle (PR #83 → develop `372e635`, 2026-08-28): `EmbeddingService.warm_up_in_background()` at API boot (`COGNIFY_EMBEDDING_WARMUP`) with `try_embed()` → retriever skips RAG while cold, `/health.checks.embedding`; `UserData.is_active` + 30 s `UserStatusCache` (`COGNIFY_AUTH_RECHECK_TTL_SECONDS`) in `get_current_user` + admin `PATCH /auth/users/{id}/active` (role drift is logged, not enforced — no user table yet); shared `ToastProvider`/`useToast`; six components split under 200 lines with `frontend/src/file-size-budget.test.ts` enforcing it. AUTHOR-009 humanize streaming (PR #84 → develop `1efcd11`, 2026-08-28): `POST /content/humanize-preview/stream` (POST-SSE; `pass` per mechanical/LLM pass with scores, up to `COGNIFY_HUMANIZE_PREVIEW_MAX_PASSES`=2 LLM passes stopping at score ≥70 or no change; `done` carries gap-free sentence `segments` from `src/services/content/sentence_segments.py`), `useHumanizeStream` + `HumanizePassTiles`/`HumanizeChangeList` in the panel — every changed sentence starts accepted, the resolved markdown still saves through `section-update`'s anchor validator; the JSON `/humanize-preview` and the pipeline's single-pass node are unchanged. AUTHOR-010 model tiering (PR #85 → develop `103db4e`, 2026-08-28; **Phase B complete**): `COGNIFY_LLM_MODEL_BY_STEP` JSON map of tracked step name (`content_outline`, `content_queries`, `content_draft`, …, `plan_research`, `section_regenerate`, `seo_regenerate`) → Anthropic model id; `src/utils/tiered_llm.py::TieredChatModel` routes on the tracker's `current_step_name` and sits inside `TrackedChatModel` so `llm_calls.model_name`/usage pricing reflect the real model; `_wrap_node` now binds the step name even without a step repo; `GET /settings/llm` returns read-only `default_model` + `model_by_step`, shown in the LLM tab's Model tiering card. Default `{}` = single model. AUTHOR-014 Playwright create-article flow (2026-08-29, PR #86): `frontend/tests/e2e/create-article.spec.ts` + `support/` (route-table mock backend with a phase machine, finite SSE bodies that ride `useSessionEvents`' 1 s reconnect, contract-typed fixtures); config gains `PLAYWRIGHT_PORT`, same-origin `NEXT_PUBLIC_API_BASE_URL=/api/v1`, and a clean-`.next` spawn (a killed `next dev` leaves Turbopack state that wedges the next route compile). AUTHOR-012 prompt registry (2026-09-01, `feature/AUTHOR-012-prompt-registry`, migration `e2a7c4d9b1f3`): `src/agents/prompts/` registry of 28 keyed `PromptTemplate`s (content/research/editing), `GET/PUT/DELETE /api/v1/prompts[/{key}]` for global admin-edited overrides, a Settings → Prompts tab, and a per-run/per-request contextvar snapshot binding so an edit applies to the next run — see L-014. AUTHOR-011 persona voice engine v1 (2026-09-02, `feature/AUTHOR-011-persona-voice`, PR pending, migration `f3b8d1c6a2e4`): flagged off by default via `COGNIFY_ENABLE_VOICE_ENGINE`; `src/services/persona/` (pure, stdlib+numpy) builds a 13-dim stylometric fingerprint from ≥5 pasted samples, confidence-gated z-score section scoring (`match ≥80 / close ≥60 / off_voice`), an in-process cosine few-shot picker, and a voice prompt block (5 `voice.*` registry keys per L-014); two graph nodes (`score_voice` pure, `fix_voice_deviations` LLM, one pass per section below `COGNIFY_VOICE_FIX_THRESHOLD`=70) wired after `humanize`; `voice_persona_id` threads brief → session → `ContentState` → persisted article; `personas`/`persona_samples` tables + `/personas` CRUD; Settings → Personas tab + Voice select in the Generate modal + Voice-match chip on the article sidebar. See L-011 before touching the content graph, L-012 before touching brief resolution, L-013 before touching section ids, L-015 before adding a new model field.
**Next action:** AUTHOR-011 done (persona voice engine, PR pending on `feature/AUTHOR-011-persona-voice`; live smoke passed — see PROGRESS.md RESUME block; incidental fix `95009f7` for a pre-existing `GET /articles` 500 on null visual metadata still needs the api image rebuilt). Next is the user's pick: AUTHOR-013 (LinkedIn repurpose, 5 SP — worktree `author-013-linkedin` already prepared) or PUBLISH-002 (WordPress, 5 SP).
