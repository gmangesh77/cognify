# Cognify

Self-driving content platform that discovers trends, runs multi-agent AI research, and generates publication-ready articles with visuals.

## Overview

Cognify monitors domains of interest, automatically discovers trending topics from multiple data sources (Google Trends, Reddit, Hacker News, NewsAPI, arXiv), orchestrates multi-agent research pipelines using LangGraph, generates SEO-optimized long-form articles with citations and visuals, and publishes to multiple platforms — all without manual intervention.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.12+ |
| **API** | FastAPI (async REST + WebSocket) |
| **Agent Framework** | LangChain + LangGraph |
| **LLMs** | Claude Opus 4 (primary), Claude Sonnet 4 (drafting) |
| **Visual Assets** | DALL-E 3 (illustrations), Matplotlib (charts), Mermaid (diagrams) |
| **Vector DB** | Milvus (RAG embeddings + similarity search) — see [ADR-002](docs/architecture/adrs/ADR-002-milvus-vector-database.md) |
| **Database** | PostgreSQL 16 + SQLAlchemy 2.0 + Alembic (migrations) |
| **Cache** | Redis |
| **Task Queue** | Celery + Redis |
| **Frontend** | Next.js 15 + React 19 + TypeScript + Tailwind CSS 4 + shadcn/ui + TanStack Query |
| **Testing** | pytest (backend), Vitest + Testing Library (frontend) |
| **Publishing** | Ghost CMS (Admin API), Medium (deprecated API) |
| **CI/CD** | GitHub Actions |
| **Infrastructure** | Docker + Kubernetes on AWS |

### Data Sources

| Source | API | Purpose |
|--------|-----|---------|
| Google Trends | pytrends | Real-time search interest signals |
| Reddit | asyncpraw (OAuth2) | Community-driven trending topics |
| Hacker News | Algolia API | Tech community trends |
| NewsAPI | REST | Mainstream news headlines |
| arXiv | REST/RSS | Academic paper feeds |
| SerpAPI | REST | Web search for research agents |
| Semantic Scholar | REST | Academic paper search for literature review |

## Project Structure

```
cognify/
├── src/
│   ├── agents/
│   │   ├── content/           # Content generation pipeline (LangGraph)
│   │   │   ├── pipeline.py    # StateGraph: outline → draft → validate → humanize → SEO → assemble
│   │   │   ├── outline_generator.py
│   │   │   ├── section_drafter.py
│   │   │   ├── humanizer.py
│   │   │   ├── seo_optimizer.py
│   │   │   ├── citation_manager.py
│   │   │   ├── chart_generator.py
│   │   │   └── article_assembler.py
│   │   └── research/          # Research orchestrator (LangGraph)
│   │       ├── orchestrator.py # StateGraph: plan → dispatch → index → evaluate → finalize
│   │       ├── planner.py      # LLM-based research plan generation
│   │       ├── web_search.py   # SerpAPI web search agent
│   │       ├── literature_review.py # Semantic Scholar literature agent
│   │       ├── evaluator.py    # Completeness evaluation
│   │       └── state.py        # ResearchState TypedDict
│   ├── api/
│   │   ├── main.py            # FastAPI app factory
│   │   ├── middleware/        # CORS, security headers, correlation ID, logging
│   │   ├── routers/           # Route handlers (health, auth, trends, topics, research, articles, metrics)
│   │   └── schemas/           # Pydantic request/response models
│   ├── services/
│   │   ├── content.py         # ContentService (orchestrates content pipeline)
│   │   ├── research.py        # ResearchService (orchestrates research)
│   │   ├── publishing/        # PublishingService + platform adapters
│   │   │   ├── service.py     # Orchestrator (retry, registry, logging)
│   │   │   ├── ghost/         # Ghost CMS transformer + adapter (JWT auth)
│   │   │   └── medium/        # Medium transformer + adapter (deprecated API)
│   │   ├── topic_ranking.py   # Composite scoring + dedup
│   │   ├── topic_persistence.py # Cross-scan dedup + DB storage
│   │   ├── serpapi_client.py  # Web search client
│   │   ├── semantic_scholar.py # Academic paper search client
│   │   ├── milvus_service.py  # Vector DB operations
│   │   ├── embeddings.py      # sentence-transformers embeddings
│   │   └── trends/            # TrendSource protocol + 5 source implementations
│   ├── models/                # Pydantic models + SQLAlchemy ORM
│   ├── db/                    # Database setup, repositories
│   └── config/                # Pydantic settings, structlog config
├── frontend/                  # Next.js 15 dashboard
│   ├── src/app/               # App router pages (dashboard, topics, articles, research, settings)
│   ├── src/components/        # React components (shadcn/ui based)
│   ├── src/hooks/             # TanStack Query hooks (wired to real APIs)
│   └── src/lib/               # API client, utilities
├── tests/
│   ├── unit/                  # ~901 backend tests
│   └── integration/           # Integration tests with real dependencies
├── alembic/                   # Database migrations
├── docs/                      # Architecture, testing, security, observability
├── project-management/        # Backlog, progress tracker, risk register
├── docker-compose.yml         # Local dev services (PostgreSQL)
└── pyproject.toml             # Python dependencies (managed by uv)
```

## Getting Started

There are two ways to run Cognify locally: **Docker (full stack)** or **manual (for active development)**.

### Option A: Docker — Full Stack (Recommended for first run)

Runs everything in containers. No Python/Node installation needed — only Docker.

```bash
# Clone and configure
git clone git@github.com:gmangesh77/cognify.git
cd cognify
cp .env.example .env
# Edit .env — add JWT keys and any API keys you have

# Start the full stack (builds + runs all services)
docker compose up -d --build

# Run database migrations
docker compose exec api uv run alembic upgrade head
```

This starts 6 services:

| Service | URL | Description |
|---------|-----|-------------|
| **frontend** | http://localhost:3000 | Next.js dashboard |
| **api** | http://localhost:8000 | FastAPI backend (docs at `/docs`) |
| **worker** | — | Celery background worker |
| **postgres** | localhost:5432 | PostgreSQL 16 database |
| **milvus** | localhost:19530 | Vector database for RAG |
| **redis** | localhost:6379 | Cache and task broker |

```bash
# View logs
docker compose logs -f api

# Stop everything (data preserved)
docker compose down

# Stop and delete all data
docker compose down -v
```

### Option B: Manual — For Active Development

Run backend and frontend natively with hot-reload. Best for writing code.

**Prerequisites:**
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — Python package manager
- Node.js 20+ and npm
- Docker — for infrastructure services (Postgres, Milvus, Redis)

```bash
# Clone and install
git clone git@github.com:gmangesh77/cognify.git
cd cognify
uv sync --dev
cd frontend && npm install && cd ..

# Configure environment
cp .env.example .env
# Edit .env — at minimum, set JWT keys.
# Default database URL matches docker-compose.yml:
#   COGNIFY_DATABASE_URL=postgresql+asyncpg://cognify:cognify@localhost:5432/cognify

# Start infrastructure only (Postgres, Milvus, Redis — not api/worker/frontend)
docker compose up postgres milvus redis -d

# Run database migrations
uv run alembic upgrade head

# Start backend API with hot-reload (port 8000)
uv run uvicorn src.api.main:create_app --factory --reload --port 8000

# Start frontend with hot-reload (port 3000) — separate terminal
cd frontend && npm run dev
```

The API will be at `http://localhost:8000` (docs at `/docs`). The dashboard will be at `http://localhost:3000`.

### Local Ghost CMS (Optional — for publishing tests)

Ghost is included in docker-compose under the `publishing` profile. It doesn't start by default.

```bash
# Start Ghost alongside other services
docker compose --profile publishing up -d

# Or start Ghost standalone
docker compose up ghost -d
```

Then:
1. Visit `http://localhost:2368/ghost/` and complete the setup wizard
2. Go to **Settings > Integrations > Add custom integration**
3. Copy the **Admin API Key** (format: `id:secret`)
4. Add to your `.env`:
   ```
   COGNIFY_GHOST_API_URL=http://localhost:2368
   COGNIFY_GHOST_ADMIN_API_KEY=<your-id>:<your-secret>
   ```
5. Restart the API and publish an article:
   ```bash
   curl -X POST http://localhost:8000/api/v1/articles/{article_id}/publish \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"platform": "ghost"}'
   ```

**Dev credentials** (seeded automatically when `COGNIFY_DEBUG=true`):

| Email | Password | Role |
|-------|----------|------|
| `admin@cognify.dev` | `admin123` | admin |
| `editor@cognify.dev` | `editor123` | editor |
| `viewer@cognify.dev` | `viewer123` | viewer |

### Configuration

All environment variables are prefixed with `COGNIFY_` and read from `.env`:

```bash
cp .env.example .env
```

**Core Settings**

| Variable | Default | Description |
|----------|---------|-------------|
| `COGNIFY_DEBUG` | `false` | Enable debug mode (seeds dev users, verbose logging) |
| `COGNIFY_LOG_LEVEL` | `INFO` | Log level |
| `COGNIFY_DATABASE_URL` | `""` | PostgreSQL connection string (`postgresql+asyncpg://user:pass@host:port/db`). **Required for persistent storage** — empty falls back to in-memory repos |
| `COGNIFY_CORS_ALLOWED_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |

**Authentication (JWT RS256)**

| Variable | Default | Description |
|----------|---------|-------------|
| `COGNIFY_JWT_PRIVATE_KEY` | — | RSA private key for signing tokens |
| `COGNIFY_JWT_PUBLIC_KEY` | — | RSA public key for verification |
| `COGNIFY_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `COGNIFY_JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |

**LLM & AI**

| Variable | Default | Description |
|----------|---------|-------------|
| `COGNIFY_ANTHROPIC_API_KEY` | — | Anthropic API key (required for real article generation) |
| `COGNIFY_OPENAI_API_KEY` | — | OpenAI key (DALL-E illustrations) |
| `COGNIFY_PRIMARY_MODEL_NAME` | `claude-sonnet-4` | Primary LLM model for generation |
| `COGNIFY_DRAFTING_MODEL_NAME` | `claude-sonnet-4` | Drafting LLM model |

**External API Keys**

| Variable | Default | Description |
|----------|---------|-------------|
| `COGNIFY_SERPAPI_API_KEY` | — | SerpAPI key (web search research agent) |
| `COGNIFY_SEMANTIC_SCHOLAR_API_KEY` | — | Optional — higher rate limits for academic search |
| `COGNIFY_NEWSAPI_API_KEY` | — | NewsAPI key (trend source) |
| `COGNIFY_REDDIT_CLIENT_ID` | — | Reddit OAuth2 client ID |
| `COGNIFY_REDDIT_CLIENT_SECRET` | — | Reddit OAuth2 client secret |

**Publishing**

| Variable | Default | Description |
|----------|---------|-------------|
| `COGNIFY_GHOST_API_URL` | — | Ghost Admin API URL (e.g., `http://localhost:2368`) |
| `COGNIFY_GHOST_ADMIN_API_KEY` | — | Ghost Admin API key (`id:secret` format, from Ghost Admin > Integrations) |
| `COGNIFY_MEDIUM_API_TOKEN` | — | Medium Integration Token (API deprecated, mock-only) |
| `COGNIFY_MEDIUM_USER_ID` | — | Medium user ID |
| `COGNIFY_ENCRYPTION_KEY` | — | Fernet key for encrypting API keys at rest. **Required in production.** Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

**Vector Database & RAG**

| Variable | Default | Description |
|----------|---------|-------------|
| `COGNIFY_MILVUS_URI` | `./milvus_data.db` | Milvus Lite for dev; configure for production |
| `COGNIFY_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `COGNIFY_CHUNK_SIZE_TOKENS` | `512` | RAG chunk size |
| `COGNIFY_TOP_K_RETRIEVAL` | `5` | Top-k chunks for RAG retrieval |

See `src/config/settings.py` for the full list of 50+ configurable settings.

**Frontend** (in `frontend/.env.local`):

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | Backend API base URL |
| `NEXT_PUBLIC_APP_NAME` | `Cognify` | Application name |

## API Endpoints

All endpoints prefixed with `/api/v1`. Auth endpoints are public; all others require JWT.

**Health**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check (public) |
| GET | `/health/ready` | Readiness check (k8s probes) |

**Authentication**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Login → access + refresh tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Revoke refresh token |

**Trend Discovery**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/trends/fetch` | Fetch trends from all sources |
| POST | `/topics/rank` | Rank and deduplicate topics |
| POST | `/topics/persist` | Persist ranked topics to DB |
| GET | `/topics` | List persisted topics (paginated) |

**Research**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/research/sessions` | Start research session for a topic |
| GET | `/research/sessions` | List sessions (paginated, filterable) |
| GET | `/research/sessions/{id}` | Session details with agent steps |

**Articles**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/articles/generate` | Generate article outline from research |
| POST | `/articles/drafts/{id}/sections` | Draft all sections with RAG |
| GET | `/articles/drafts/{id}` | Get draft with outline, sections, SEO |
| POST | `/articles/drafts/{id}/finalize` | Finalize → CanonicalArticle |
| GET | `/articles` | List finalized articles (paginated) |
| GET | `/articles/{id}` | Get finalized CanonicalArticle |

**Publishing**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/articles/{id}/publish` | Publish article to a platform (ghost, medium) |

**Dashboard**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/metrics` | Dashboard overview (topics, articles, research time) |

## Development

### Running Tests

```bash
# Backend — full suite with coverage
uv run pytest --cov=src --cov-report=term-missing

# Backend — single test
uv run pytest tests/unit/api/test_health.py::TestHealthEndpoint -v

# Frontend — all tests
cd frontend && npm test

# Frontend — watch mode
cd frontend && npm run test:watch
```

**Test suite:** ~901 backend tests + 239 frontend tests

### Linting and Type Checking

```bash
# Backend
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/

# Frontend
cd frontend && npm run lint
```

### Code Quality Standards

- **TDD** — write tests before implementation (Red/Green/Refactor)
- **Strict typing** — mypy strict mode, no `Any` types
- **Small functions** — all functions < 20 lines, max 3 parameters
- **Small files** — all files < 200 lines
- **Structured logging** — structlog with correlation IDs, no `print()`
- **Pydantic everywhere** — all data validation via Pydantic models
- **No hardcoded config** — environment variables via pydantic-settings

## Architecture

### Content Pipeline

```
Trend Discovery → Research Orchestrator → Content Generation → Publishing Service
     │                    │                       │                    │
     ├─ Google Trends     ├─ Web Search Agent     ├─ Outline          ├─ Ghost CMS
     ├─ Reddit            ├─ Literature Review    ├─ Section Drafting │   (Admin API + JWT)
     ├─ Hacker News       │   Agent               ├─ Validation       ├─ Medium
     ├─ NewsAPI           └─ (parallel per facet)  ├─ Humanization     │   (deprecated API)
     └─ arXiv                                      ├─ SEO + AI Disc.  └─ (WordPress, LinkedIn
                                                   ├─ Citations            planned)
                                                   ├─ Charts
                                                   └─ CanonicalArticle
```

The research orchestrator tags each facet with a `source_type` (web, academic, or both) and routes to the appropriate agent. All findings are indexed in Milvus for RAG retrieval during content generation.

Content generation produces a platform-neutral **CanonicalArticle** — the single output contract consumed by all publishing adapters. See [ADR-003](docs/architecture/adrs/ADR-003-canonical-article-boundary.md) and [ADR-004](docs/architecture/adrs/ADR-004-publishing-transformer-adapter-pattern.md).

### Middleware Stack

Requests flow through middleware in this order:

1. **Correlation ID** — generates/validates `X-Request-ID` header
2. **Security Headers** — adds `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`
3. **CORS** — handles cross-origin requests
4. **Rate Limiting** — slowapi-based per-endpoint limits
5. **Request Logging** — structlog JSON logging with timing and correlation IDs

### Error Handling

All errors return a consistent envelope:

```json
{
  "error": {
    "code": "error_code",
    "message": "Human-readable message",
    "details": []
  }
}
```

### Key Documentation

- [High-Level Architecture](docs/architecture/HIGH_LEVEL_ARCHITECTURE.md)
- [Test Strategy](docs/testing/TEST_STRATEGY.md)
- [CI/CD Pipeline](docs/ci-cd/PIPELINE.md)
- [Security Checklist](docs/security/SECURITY_CHECKLIST.md)
- [Observability Plan](docs/observability/OBSERVABILITY_PLAN.md)
- [Product Backlog](project-management/BACKLOG.md)
- [Progress Tracker](project-management/PROGRESS.md)

## Git Workflow

- **Branch naming**: `feature/{TICKET}-description` or `fix/{TICKET}-description`
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`, `test:`)
- **PR requirements**: tests passing + security scan clean + human review

## License

This project is proprietary. All rights reserved.
