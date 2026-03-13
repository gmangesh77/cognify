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
- Test: `pytest --cov=src --cov-report=term-missing`
- Lint: `ruff check src/ && ruff format --check src/ && mypy src/`
- Dev: `uvicorn src.api.main:app --reload --port 8000`
- Single test: `pytest tests/path/to/test_file.py::test_name -v`

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
Conda env: `cognify` — run tests with `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest ...`

## Current Status
See @project-management/PROGRESS.md for full ticket status.

**Last completed:** TREND-003 (Hacker News Integration) — branch `feature/TREND-003-hackernews-integration`
**Epic 7 (API & Auth):** All 3 tickets Done (API-001, API-002, API-003)
**Epic 1 (Trend Discovery):** TREND-006 Done, TREND-003 Done, TREND-001 In Progress (Google Trends via pytrends)
**Epic 0 (Design):** All 9 tickets Done (DESIGN-001 through DESIGN-009) — design system, components, all screens
**Architecture:** Vector DB switched from Weaviate to Milvus (see ADR-002)
**Next up:** TREND-002 (Reddit), TREND-004 (NewsAPI), or DASH-001 (Dashboard frontend)
