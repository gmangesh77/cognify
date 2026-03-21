# Cognify — Content Generation and Trend Insight Engine
Self-driving content platform that discovers trends, runs multi-agent research, and generates publication-ready articles with visuals.

## Tech Stack
- **Language**: Python 3.12+ (agents, pipelines, API)
- **Agent Framework**: LangChain + LangGraph (multi-agent orchestration)
- **LLMs**: Claude Opus 4 (primary), Claude Sonnet 4 (drafting), Stable Diffusion XL (images)
- **Vector DB**: Milvus (RAG embeddings + similarity search)
- **API**: FastAPI (async REST endpoints)
- **Database**: PostgreSQL 16 (metadata, users, publishing state)
- **Cache**: Redis (trend signal caching, rate limiting)
- **Task Queue**: Celery + Redis (background agent workflows)
- **Frontend**: Next.js 15 + React 19 + TypeScript (dashboard UI)
- **Testing**: pytest, pytest-asyncio, Playwright (E2E)
- **CI/CD**: GitHub Actions
- **Infrastructure**: Docker + Kubernetes on AWS

## Project Structure
src/
  agents/       # LangGraph agent definitions (orchestrator, researcher, writer)
  pipelines/    # Trend discovery, research, content gen, visual gen, publishing
  services/     # Business logic (topic ranking, SEO, formatting)
  api/          # FastAPI routes and middleware
  models/       # SQLAlchemy/Pydantic models
  utils/        # Shared utilities (logging, correlation IDs)
  config/       # Environment config, settings
docs/           # Architecture, testing, CI/CD, observability docs
.claude/rules/  # Modular AI agent instructions
.claude/commands/ # Custom slash commands
project-management/ # Backlog, sprints, risk register

## Commands
- Build: `docker compose build`
- Test: `uv run pytest --cov=src --cov-report=term-missing`
- Lint: `uv run ruff check src/ && uv run ruff format --check src/ && uv run mypy src/`
- Dev: `uv run uvicorn src.api.main:app --reload --port 8000`
- Single test: `uv run pytest tests/path/to/test_file.py::test_name -v`

## Architecture Decisions
- See @docs/architecture/HIGH_LEVEL_ARCHITECTURE.md for system design
- See @docs/architecture/adrs/ for decision records
- All new architectural decisions MUST be recorded as ADRs

## Coding Standards
- Write tests BEFORE implementation (TDD — Red/Green/Refactor)
- All functions < 20 lines, all files < 200 lines, max 3 params
- Named exports only — no default exports
- Use Pydantic for all data validation and serialization
- Input validation on all external inputs (Pydantic models + FastAPI deps)
- Structured logging with correlation IDs via structlog
- No secrets in code — use environment variables via pydantic-settings

## Patterns to AVOID
- No `Any` types — use strict typing with mypy strict mode
- No inline styles in frontend — use Tailwind CSS
- No direct database calls from route handlers — use service layer
- No print() in production code — use structlog
- No hardcoded configuration — externalize via pydantic-settings

## Git Workflow
- Branch: feature/{TICKET}-description or fix/{TICKET}-description
- Commits: conventional commits (feat:, fix:, chore:, docs:, test:)
- Always run full test suite before committing
- PR requires: tests passing + security scan clean + human review

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

## Environment
Package manager: **uv** — all commands use `uv run` prefix (no activation needed).
- Install deps: `uv sync --dev`
- Conda fallback: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ...`

## Current Status
See @project-management/PROGRESS.md for full ticket status.

**Last completed:** VISUAL-001 (Data Chart Generation) — PR #30
**Epic 4 (Visual Assets):** VISUAL-001 Done — LLM-driven chart generation (bar/line/pie via Matplotlib), integrated into content pipeline. VISUAL-002, VISUAL-003 remaining.
**Epic 6 (Dashboard):** ALL 5 TICKETS DONE — **Epic complete.** Next.js 15 frontend with Tailwind v4, 220 frontend tests. Dashboard + Topic Discovery + Article View + Research Sessions + Settings.
**Epic 3 (Content Gen):** ALL 6 TICKETS DONE — **Epic complete.** Full pipeline: outline → section drafting with RAG → validation → citation management → humanization → SEO + AI discoverability → chart generation → CanonicalArticle assembly.
**Epic 8 (Architecture):** ARCH-001, ARCH-002 Done — CanonicalArticle contracts, TrendSource protocol & registry. Epic complete.
**Epic 2 (Research):** RESEARCH-001 through RESEARCH-004 Done — orchestrator + web search + RAG pipeline + literature review. RESEARCH-005 in progress.
**Epic 7 (API & Auth):** All 3 tickets Done (API-001, API-002, API-003)
**Epic 1 (Trend Discovery):** All 6 tickets Done (TREND-001 through TREND-006) — Epic complete
**Epic 0 (Design):** All 9 tickets Done (DESIGN-001 through DESIGN-009) — design system, components, all screens
**Test suite:** ~790 backend tests + 220 frontend tests, ~98% coverage
**Next action:** Epic 4 (VISUAL-002/003) or Epic 5 (Publishing) or Epic 2 (RESEARCH-005).
