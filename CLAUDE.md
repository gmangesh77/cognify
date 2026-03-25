# Cognify — Content Generation and Trend Insight Engine
Self-driving content platform that discovers trends, runs multi-agent research, and generates publication-ready articles with visuals.

## Tech Stack
- **Language**: Python 3.12+ (agents, pipelines, API)
- **Agent Framework**: LangChain + LangGraph (multi-agent orchestration)
- **LLMs**: Claude Sonnet 4 (primary), Claude Sonnet 4 (drafting), Stable Diffusion XL (images)
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
- No secrets in code — use environment variables via pydantic-settings

## Patterns to AVOID
- No `Any` types — use strict typing with mypy strict mode
- No inline styles in frontend — use Tailwind CSS
- No direct database calls from route handlers — use service layer
- No print() in production code — use structlog
- No hardcoded configuration — externalize via pydantic-settings

## Azure Boards
- **Organization**: https://dev.azure.com/signity
- **Project**: Cognify
- **Work item prefix**: `AB#<id>` in commit messages and PR descriptions to link to Azure Boards
- **CLI**: `powershell.exe -Command "& 'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd' boards <command>"` (az.cmd requires PowerShell on this machine due to path spaces)
- When completing a ticket: update Azure Boards work item state to Closed
- When starting a ticket: update Azure Boards work item state to Active

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

## Environment
Package manager: **uv** — all commands use `uv run` prefix (no activation needed).
- Install deps: `uv sync --dev`
- Conda fallback: `"C:\Users\mange\anaconda3\Library\bin\conda.bat" run -n cognify ...`

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

**Last completed:** VISUAL-003 (Diagram Generation) — PR #36
**Epic 9 (Infrastructure):** ALL 3 TICKETS DONE — **Epic complete.** PostgreSQL persistence (SQLAlchemy, Alembic, Docker Compose), topic persistence with cross-scan dedup, all frontend hooks wired to real APIs. INFRA-003/004/005 remain in backlog.
**Epic 4 (Visual Assets):** **Epic complete.** VISUAL-001 (charts), VISUAL-002 (AI illustrations), VISUAL-003 (diagrams) all Done.
**Epic 6 (Dashboard):** **Epic complete.** All pages show real data (except Settings — mock, needs backend CRUD endpoints).
**Epic 3 (Content Gen):** **Epic complete.** Full pipeline with chart generation → CanonicalArticle assembly.
**Epic 8 (Architecture):** Epic complete.
**Epic 2 (Research):** **Epic complete.**
**Epic 7 (API & Auth):** Epic complete.
**Epic 1 (Trend Discovery):** Epic complete.
**Epic 0 (Design):** Epic complete.
**Test suite:** ~764 backend tests + 237 frontend tests, ~98% coverage
**Next action:** Epic 5 (Publishing), INFRA-003 (Wire Real LLM Orchestrator), INFRA-004 (Settings Backend CRUD), or INFRA-005 (Frontend Status Alignment).
