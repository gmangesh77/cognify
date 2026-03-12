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

### Completed (Tasks 1–6)
- `pyproject.toml` — deps, pytest config (asyncio_mode=auto)
- `src/config/settings.py` — Settings via pydantic-settings
- `src/utils/logging.py` — structlog setup (`setup_logging(debug)`)
- `src/api/errors.py` — CognifyError hierarchy + `build_error_response`
- `src/api/routers/health.py` — `/api/v1/health` + `/api/v1/health/ready`
- `src/api/middleware/__init__.py` + `src/api/middleware/correlation_id.py` — CorrelationIdMiddleware, correlation_id_ctx ContextVar
- `tests/unit/api/test_middleware.py` — 5 correlation ID tests (all passing)

### In Progress (Task 7 — next to resume)
- Tests already appended to `tests/unit/api/test_middleware.py` (TestSecurityHeadersMiddleware — 3 tests)
- Need to create: `src/api/middleware/security_headers.py`
  - Class `SecurityHeadersMiddleware(BaseHTTPMiddleware)`
  - Sets: `x-content-type-options: nosniff`, `x-frame-options: DENY`, `content-security-policy: default-src 'self'`
- Run: 8 tests total (5 corr + 3 security)
- Commit: `feat: add security headers middleware (CSP, X-Frame, X-Content-Type)`

### Pending (Task 8)
- Append tests to `tests/unit/api/test_middleware.py` (TestRequestLoggingMiddleware — 2 tests)
- Create: `src/api/middleware/request_logging.py`
  - Class `RequestLoggingMiddleware(BaseHTTPMiddleware)`
  - Skip paths: `/docs`, `/openapi.json`, `/redoc`
  - Log fields: method, path, status_code, duration_ms, correlation_id
  - Stacks with CorrelationIdMiddleware (add RequestLogging first, then CorrelationId)
- Run: 10 tests total (5 corr + 3 security + 2 logging)
- Commit: `feat: add request logging middleware with structlog and correlation IDs`

### Remaining Tasks (9–12)
- Task 9: App factory, rate limiter, dependency stubs
- Task 10: Rate limiting tests (429 verification)
- Task 11: Full suite validation, lint, type check
- Task 12: Dev server smoke test and final commit
