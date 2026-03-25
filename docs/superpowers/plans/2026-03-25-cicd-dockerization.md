# CI/CD and Dockerization Plan

## Branch & Documentation

- **Branch**: `feature/cicd-dockerization` (created from `main`)
- **Plan doc**: `docs/superpowers/plans/2026-03-25-cicd-dockerization.md` (per project convention)
- All work is done on the feature branch; nothing touches `main` until PR review

## Context

Cognify has a complete backend (FastAPI + Python 3.12) and frontend (Next.js 15 + React 19) but no containerization or CI/CD automation. The `docs/ci-cd/PIPELINE.md` spec defines a 12-stage pipeline, but nothing is implemented. The only Docker file is `docker-compose.yml` with PostgreSQL + Milvus for local dev. This plan implements Dockerfiles, a full-stack compose, GitHub Actions CI/CD, and a Makefile — everything needed to go from "run manually" to "containerized with automated pipelines".

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `.dockerignore` | Create | Exclude bloat from Docker context |
| `Dockerfile.api` | Create | Multi-stage FastAPI backend image |
| `Dockerfile.worker` | Create | Celery worker image (same deps, different entrypoint) |
| `Dockerfile.frontend` | Create | Multi-stage Next.js frontend image |
| `docker-entrypoint.sh` | Create | API startup: migrations + uvicorn |
| `docker-compose.yml` | Modify | Add Redis, API, worker, frontend services |
| `docker-compose.test.yml` | Create | Self-contained E2E test environment |
| `frontend/next.config.ts` | Modify | Add `output: "standalone"` for Docker builds |
| `.github/workflows/ci.yml` | Create | PR validation (lint, test, security) |
| `.github/workflows/cd.yml` | Create | Main branch build + deploy pipeline |
| `Makefile` | Create | Developer convenience commands |

---

## Step 1: `.dockerignore`

Create at project root. Keeps Docker build context small (~50MB vs ~1GB+).

```
.git
.github
.venv
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
.coverage
htmlcov
node_modules
.next
frontend/node_modules
frontend/.next
*.egg-info
dist
build
docs
pencil_designs
project-management
tests
.env
.env.*
*.pem
generated_assets
milvus_data.db
.claude
.superpowers
```

---

## Step 2: `frontend/next.config.ts` — Add standalone output

Required for Docker-optimized Next.js builds. Without it, the prod image needs full `node_modules` (~500MB vs ~20MB).

```ts
const nextConfig: NextConfig = {
  output: "standalone",
};
```

**File**: `/home/ubuntu/workbench/cognify/frontend/next.config.ts` (line 3, add `output: "standalone"`)

---

## Step 3: `docker-entrypoint.sh`

API container startup script. Runs Alembic migrations before starting uvicorn.

- Check `COGNIFY_DATABASE_URL` is set before running migrations
- Use `exec` to replace shell with uvicorn (proper signal handling)
- Pass `"$@"` to allow overriding uvicorn args

**Existing**: `alembic/env.py` already reads `COGNIFY_DATABASE_URL` (line 17), so migrations will target the correct database.

---

## Step 4: `Dockerfile.api` — Multi-stage Python image

**Stage 1 (builder)**:
- Base: `python:3.12-slim`
- Install `uv` via pip
- Copy `pyproject.toml` + `uv.lock`
- `uv sync --no-dev --frozen` (production deps only, reproducible)
- Copy `src/`, `alembic/`, `alembic.ini`

**Stage 2 (runtime)**:
- Base: `python:3.12-slim`
- Install runtime system deps only (`libpq5` for asyncpg, `curl` for healthcheck)
- Create non-root user `cognify` (uid 1000)
- Copy venv + source from builder
- Create `generated_assets/{charts,illustrations,diagrams}` dirs
- Copy `docker-entrypoint.sh`, make executable
- `EXPOSE 8000`, `USER cognify`
- `ENTRYPOINT ["./docker-entrypoint.sh"]`

**Note**: Image will be ~2-3GB due to `sentence-transformers` pulling PyTorch. Accepted for now; extracting embeddings to a separate service is future work.

---

## Step 5: `Dockerfile.worker`

Same as `Dockerfile.api` but different entrypoint. Celery isn't wired yet (codebase uses `AsyncIODispatcher`), so this is a placeholder that shares the same deps.

- Entrypoint: placeholder `echo "Worker ready"` until Celery is wired
- Same non-root user, same deps

---

## Step 6: `Dockerfile.frontend` — Multi-stage Node image

**Stage 1 (deps)**: `node:20-alpine`, copy `package.json` + `package-lock.json`, `npm ci`
**Stage 2 (builder)**: Copy source, set `ARG NEXT_PUBLIC_API_BASE_URL`, `npm run build`
**Stage 3 (runner)**: `node:20-alpine`, non-root user `nextjs`, copy `.next/standalone` + `.next/static`, `EXPOSE 3000`, `CMD ["node", "server.js"]`

The `NEXT_PUBLIC_API_BASE_URL` is a build-time arg baked into the JS bundle. Browser makes requests, not the container.
- Local dev: `http://localhost:8000/api/v1`
- Production: `/api/v1` (relative, behind reverse proxy)

---

## Step 7: Update `docker-compose.yml`

**File**: `/home/ubuntu/workbench/cognify/docker-compose.yml`

Add 4 new services to existing postgres + milvus:

- **redis**: `redis:7-alpine`, port 6379, healthcheck via `redis-cli ping`
- **api**: Build from `Dockerfile.api`, port 8000, env overrides for Docker service hostnames (`postgres`, `milvus`), `env_file: .env` for API keys, depends_on postgres/milvus/redis with health conditions
- **worker**: Build from `Dockerfile.worker`, same env, depends_on postgres/redis
- **frontend**: Build from `Dockerfile.frontend`, port 3000, build arg `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1`, depends_on api

Key env overrides in compose (override `.env` defaults for Docker networking):
- `COGNIFY_DATABASE_URL=postgresql+asyncpg://cognify:cognify@postgres:5432/cognify`
- `COGNIFY_MILVUS_URI=http://milvus:19530`
- `COGNIFY_CORS_ALLOWED_ORIGINS=["http://localhost:3000"]`

Add `generated_assets` named volume.

---

## Step 8: `docker-compose.test.yml`

Self-contained E2E test environment. Separate DB credentials (`cognify_test`), no port mappings (internal network), no volumes (ephemeral). Same services but isolated.

Referenced by CI pipeline and `make test-e2e`.

---

## Step 9: `.github/workflows/ci.yml` — PR Checks

Triggered on: `pull_request` to `main`

**Job 1: `lint`** (~30s)
- Setup uv via `astral-sh/setup-uv@v4`
- `uv sync --dev --frozen`
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/ --ignore-missing-imports`
- Setup Node 20, `npm ci`, `npm run lint` in frontend

**Job 2: `test-backend`** (~90s, needs lint)
- `uv run pytest tests/unit/ -v --tb=short`
- Upload coverage artifact

**Job 3: `test-frontend`** (~60s, needs lint)
- `npm ci && npx vitest run`

**Job 4: `test-integration`** (~5min, needs lint)
- GitHub Actions service containers: postgres:16, redis:7
- Run Alembic migrations
- `uv run pytest tests/integration/ -v --tb=short`

**Job 5: `security`** (~2min, parallel with tests)
- `uv run pip-audit`
- `npm audit --audit-level=high`

---

## Step 10: `.github/workflows/cd.yml` — Deploy Pipeline

Triggered on: `push` to `main`

**Job 1: `build-images`** (~5min)
- Build all 3 Docker images tagged with `${{ github.sha }}`
- Use `docker/build-push-action@v5` with GitHub Actions cache
- Push to ECR (requires `AWS_ACCOUNT_ID`, `AWS_REGION` secrets)
- Placeholder for now until ECR is provisioned

**Job 2: `deploy-staging`** (depends on build, placeholder)
- Future: Helm deploy to staging namespace

**Job 3: `deploy-production`** (depends on staging, requires approval)
- Uses GitHub Environments with required reviewers
- Future: Helm deploy to production namespace

---

## Step 11: `Makefile`

Common targets:
- `make dev` — `docker compose up --build -d`
- `make up` — `docker compose up -d postgres milvus redis` (infra only)
- `make down` — `docker compose down`
- `make build` — `docker compose build`
- `make test` — `uv run pytest tests/unit/ -q`
- `make test-frontend` — `cd frontend && npx vitest run`
- `make lint` — Run ruff + mypy + eslint
- `make lint-fix` — `uv run ruff check --fix && uv run ruff format`
- `make migrate` — `uv run alembic upgrade head`
- `make migrate-create` — `uv run alembic revision --autogenerate -m "$(msg)"`
- `make clean` — Remove caches, build artifacts

---

## Implementation Sequence

```
1. .dockerignore                    (no deps)
2. frontend/next.config.ts          (add output: "standalone")
3. docker-entrypoint.sh             (needed by Dockerfile.api)
4. Dockerfile.api                   (depends on 1, 3)
5. Dockerfile.worker                (depends on 1)
6. Dockerfile.frontend              (depends on 1, 2)
7. docker-compose.yml update        (depends on 4, 5, 6)
8. docker-compose.test.yml          (depends on 4, 6)
9. Makefile                         (depends on 7)
10. .github/workflows/ci.yml        (independent)
11. .github/workflows/cd.yml        (depends on 10)
```

Steps 4-6 can be parallelized. Steps 10-11 can be parallelized with 7-9.

---

## Verification

1. **Docker build**: `docker compose build` — all 3 images build successfully
2. **Full stack**: `docker compose up -d` — all services start, health checks pass
3. **API health**: `curl http://localhost:8000/api/v1/health` returns `{"status": "healthy"}`
4. **Frontend**: `curl http://localhost:3000` returns HTML
5. **Migrations**: Check API logs show `Running database migrations... done`
6. **Backend tests**: `make test` — 844 tests pass
7. **Frontend tests**: `make test-frontend` — 239 tests pass
8. **Lint**: `make lint` runs without errors on changed files
9. **CI dry-run**: `act pull_request` (if `act` installed) or push to a feature branch and observe GitHub Actions
