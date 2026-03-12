# Cognify — Content Generation and Trend Insight Engine
Self-driving content platform that discovers trends, runs multi-agent research, and generates publication-ready articles with visuals.

## Tech Stack
- **Language**: Python 3.12+ (agents, pipelines, API)
- **Agent Framework**: LangChain + LangGraph (multi-agent orchestration)
- **LLMs**: Claude Opus 4 (primary), Claude Sonnet 4 (drafting), Stable Diffusion XL (images)
- **Vector DB**: Weaviate (RAG embeddings + similarity search)
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
- @project-management/BACKLOG.md — Product backlog
- @project-management/RISK_REGISTER.md — Active risks

## Active Development Session State
Branch: `feature/API-001-fastapi-setup`
Conda env: `cognify` — run tests with `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify pytest ...`

### All Tasks Complete (1–12) — API-001 FastAPI Setup Done

**Test results:** 37 tests passing, 96% coverage
**Lint/type check:** ruff + mypy clean

**Created files:**
- `pyproject.toml` — deps, pytest config (asyncio_mode=auto)
- `src/config/settings.py` — Settings via pydantic-settings (`COGNIFY_` prefix)
- `src/utils/logging.py` — structlog setup (`setup_logging(debug)`)
- `src/api/errors.py` — CognifyError hierarchy + `build_error_response`
- `src/api/rate_limiter.py` — Module-level slowapi `Limiter` singleton
- `src/api/dependencies.py` — Placeholder stubs for JWT auth + DB session
- `src/api/routers/health.py` — `/api/v1/health` + `/api/v1/health/ready` (rate-limit exempt)
- `src/api/middleware/correlation_id.py` — CorrelationIdMiddleware + `correlation_id_ctx` ContextVar
- `src/api/middleware/security_headers.py` — X-Content-Type-Options, X-Frame-Options, CSP
- `src/api/middleware/request_logging.py` — structlog request logging with correlation IDs
- `src/api/main.py` — `create_app()` factory with middleware stack + exception handlers
- `tests/conftest.py` — Shared fixtures (app, client, settings)
- `tests/unit/api/test_health.py` — 11 health/readiness tests
- `tests/unit/api/test_middleware.py` — 13 middleware tests (correlation, security, logging, rate limiting)
- `tests/unit/api/test_app.py` — 6 app factory tests
- `tests/unit/api/test_errors.py` — 7 error handling tests

**Commits:**
- `2fbb94f` — chore: add pyproject.toml with runtime and dev dependencies
- `0940ed4` — feat: add pydantic-settings config with COGNIFY_ env prefix
- `3863606` — feat: add structlog configuration with JSON/console rendering
- `6e11112` — feat: add CognifyError hierarchy and standard error response builder
- `11d2c2f` — feat: add health and readiness endpoints with dependency checks
- `42a8b5d` — feat: add correlation ID middleware with X-Request-ID header
- `3dc3d22` — feat: add security headers middleware (CSP, X-Frame, X-Content-Type)
- `f65abcb` — feat: add request logging middleware with structlog and correlation IDs
- `f49c700` — feat(api-001): add create_app() factory, rate limiter, and full test suite

**Next ticket:** API-002 (JWT Authentication)
