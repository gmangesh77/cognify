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
| **Image Generation** | Stable Diffusion XL |
| **Vector DB** | Weaviate (RAG embeddings + similarity search) |
| **Database** | PostgreSQL 16 |
| **Cache** | Redis |
| **Task Queue** | Celery + Redis |
| **Frontend** | Next.js 15 + React 19 + TypeScript |
| **Testing** | pytest, pytest-asyncio, Playwright |
| **CI/CD** | GitHub Actions |
| **Infrastructure** | Docker + Kubernetes on AWS |

## Project Structure

```
src/
  agents/           # LangGraph agent definitions (orchestrator, researcher, writer)
  pipelines/        # Trend discovery, research, content gen, visual gen, publishing
  services/         # Business logic (topic ranking, SEO, formatting)
  api/              # FastAPI routes and middleware
    middleware/      # Correlation ID, security headers, request logging
    routers/        # Route handlers organized by domain
  models/           # SQLAlchemy/Pydantic models
  utils/            # Shared utilities (logging, correlation IDs)
  config/           # Environment config, settings
tests/
  unit/             # Unit tests (~70% of test pyramid)
  integration/      # Integration tests with real dependencies (~20%)
docs/
  architecture/     # System design, ADRs
  testing/          # Test strategy
  ci-cd/            # Pipeline docs
  security/         # Security checklist
  observability/    # SLIs, SLOs, alerting
project-management/ # Backlog, risk register
```

## Getting Started

### Prerequisites

- Python 3.12+
- [Conda](https://docs.conda.io/) (recommended) or pip

### Installation

```bash
# Clone the repository
git clone git@github.com:gmangesh77/cognify.git
cd cognify

# Create and activate conda environment
conda create -n cognify python=3.12 -y
conda activate cognify

# Install dependencies
pip install -e ".[dev]"
```

### Configuration

Copy the example environment file and adjust values:

```bash
cp .env.example .env
```

Available environment variables (all prefixed with `COGNIFY_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `COGNIFY_DEBUG` | `false` | Enable debug mode |
| `COGNIFY_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `COGNIFY_CORS_ALLOWED_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins (JSON array) |
| `COGNIFY_RATE_LIMIT_DEFAULT` | `100/minute` | Default API rate limit |

### Running the Dev Server

```bash
uvicorn src.api.main:create_app --factory --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Liveness check (public, no auth) |
| GET | `/api/v1/health/ready` | Readiness check (for k8s probes) |

## Development

### Running Tests

```bash
# Full test suite with coverage
pytest --cov=src --cov-report=term-missing

# Single test file
pytest tests/unit/api/test_health.py -v

# Specific test
pytest tests/unit/api/test_app.py::TestCreateApp::test_returns_fastapi_instance -v
```

### Linting and Type Checking

```bash
# Lint
ruff check src/ tests/

# Format check
ruff format --check src/ tests/

# Type check (strict mode)
mypy src/

# All at once
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/
```

### Code Quality Standards

- **TDD** — write tests before implementation (Red/Green/Refactor)
- **Strict typing** — mypy strict mode, no `Any` types
- **Small functions** — all functions < 20 lines, max 3 parameters
- **Structured logging** — structlog with correlation IDs, no `print()`
- **Pydantic everywhere** — all data validation via Pydantic models
- **No hardcoded config** — environment variables via pydantic-settings

## Architecture

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

## Git Workflow

- **Branch naming**: `feature/{TICKET}-description` or `fix/{TICKET}-description`
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`, `test:`)
- **PR requirements**: tests passing + security scan clean + human review

## License

This project is proprietary. All rights reserved.
