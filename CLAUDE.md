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

## Current Status

See @project-management/PROGRESS.md for full ticket status.

**Epics 0-4, 6-9:** All complete (Design, Trend Discovery, Research, Content Gen, Visual Assets, Dashboard, API & Auth, Architecture, Infrastructure).
**Epic 5 (Publishing):** Ghost & Medium done (PR #43). WordPress, LinkedIn, Publication Tracking in backlog.
**INFRA-005 (Frontend Status Alignment):** Backlog.
**CI/CD & Docker:** Implemented — Dockerfiles (api, worker, frontend), GitHub Actions (ci.yml, cd.yml), Makefile, docker-compose with full stack.
**Test suite:** 901 backend tests + 239 frontend tests.
**Next action:** Epic 5 (Publishing) or INFRA-005 (Frontend Status Alignment).
