# Observability Plan: Cognify

## 1. Observability Strategy

Cognify uses the three pillars of observability — **logs**, **metrics**, and **traces** — unified through OpenTelemetry. This is critical for a multi-agent system where failures can occur at any step in a long-running pipeline.

## 2. Service Level Indicators (SLIs)

| SLI | Description | Measurement Method |
|-----|-------------|--------------------|
| API Availability | Percentage of successful API responses (non-5xx) | Prometheus counter: `http_requests_total` by status |
| API Latency | P95 response time for API endpoints | Prometheus histogram: `http_request_duration_seconds` |
| Trend Scan Success | Percentage of trend scans completing without error | Custom metric: `trend_scan_status` |
| Article Generation Success | Percentage of article workflows completing successfully | Custom metric: `article_generation_status` |
| Publishing Success | Percentage of publish operations succeeding on first attempt | Custom metric: `publishing_status` |
| Agent Workflow Duration | P95 time for end-to-end agent pipeline | Custom metric: `agent_workflow_duration_seconds` |

## 3. Service Level Objectives (SLOs)

| SLO | Target | Window | Error Budget |
|-----|--------|--------|-------------|
| API Availability | 99.5% | 30 days | 3.6 hours/month |
| API Latency (P95) | < 200ms | 30 days | 5% of requests may exceed |
| Trend Scan Success | 95% | 7 days | 5% scans may fail |
| Article Generation Success | 90% | 7 days | 10% may fail (LLM variance) |
| Publishing Success | 98% | 30 days | 2% may fail |
| Agent Workflow Duration (P95) | < 10 minutes | 30 days | 5% may exceed |

## 4. Logging

### Structured Logging (structlog)
All services use structlog with JSON output for machine-parseable logs.

```python
import structlog
logger = structlog.get_logger()

logger.info("article_generated",
    article_id=article.id,
    topic_id=topic.id,
    word_count=article.word_count,
    duration_seconds=duration,
    correlation_id=request.correlation_id,
)
```

### Log Levels
| Level | Usage |
|-------|-------|
| ERROR | Unrecoverable failures (agent crash, DB connection lost) |
| WARNING | Recoverable issues (LLM rate limit hit, external API timeout, retry triggered) |
| INFO | Business events (topic discovered, article generated, article published) |
| DEBUG | Development diagnostics (agent state transitions, RAG retrieval details) |

### Log Fields (required on all entries)
- `correlation_id`: Request-scoped unique ID for tracing across services
- `service`: Service name (api, orchestrator, worker, frontend)
- `timestamp`: ISO 8601 UTC
- `level`: Log level
- `event`: Structured event name (snake_case)

### Sensitive Data Exclusions
Never log: API keys, JWT tokens, user passwords, raw LLM prompts containing user data, external API credentials.

## 5. Metrics (Prometheus)

### Application Metrics
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cognify_http_requests_total` | Counter | method, path, status | Total API requests |
| `cognify_http_request_duration_seconds` | Histogram | method, path | Request latency |
| `cognify_trend_scans_total` | Counter | domain, status | Trend scans completed |
| `cognify_topics_discovered_total` | Counter | domain, source | Topics discovered |
| `cognify_research_sessions_total` | Counter | status | Research sessions |
| `cognify_research_duration_seconds` | Histogram | - | Research session duration |
| `cognify_articles_generated_total` | Counter | status | Articles generated |
| `cognify_article_generation_seconds` | Histogram | - | Article generation time |
| `cognify_publications_total` | Counter | platform, status | Publications completed |
| `cognify_llm_calls_total` | Counter | model, agent_role | LLM API calls |
| `cognify_llm_call_duration_seconds` | Histogram | model | LLM call latency |
| `cognify_llm_tokens_total` | Counter | model, type (input/output) | Token usage |
| `cognify_vector_operations_total` | Counter | operation (embed/query) | Milvus operations |

### Infrastructure Metrics (standard)
- CPU, memory, disk usage per pod
- PostgreSQL connection pool utilization
- Redis memory usage and hit/miss ratio
- Celery queue depth and worker utilization
- Milvus query latency and index size

## 6. Distributed Tracing (OpenTelemetry)

### Trace Context
Every request creates a trace that follows the full pipeline:

```
API Request → Celery Task → Orchestrator Agent → Research Agents (parallel) → Writer Agent → Visual Agent → Publishing Service
```

### Key Spans
- `api.request` — FastAPI endpoint handling
- `celery.task` — Background task execution
- `agent.orchestrate` — Full orchestration workflow
- `agent.research` — Individual research agent execution
- `agent.write` — Writer agent execution
- `agent.visual` — Visual asset generation
- `llm.call` — Individual LLM API call (model, tokens, duration)
- `vectordb.query` — Milvus similarity search
- `publishing.push` — Platform API call

### Instrumentation
```python
from opentelemetry import trace
tracer = trace.get_tracer("cognify.agents")

async def research_topic(topic: Topic):
    with tracer.start_as_current_span("agent.research", attributes={
        "topic.id": str(topic.id),
        "topic.title": topic.title,
    }) as span:
        # ... research logic
        span.set_attribute("sources.count", len(sources))
        span.set_attribute("embeddings.count", embeddings_created)
```

## 7. Alerting

### Critical Alerts (PagerDuty / Slack #alerts-critical)
| Alert | Condition | Action |
|-------|-----------|--------|
| API Down | Availability < 99% over 5 min | Investigate immediately |
| Database Unreachable | PostgreSQL connection failures > 3 in 1 min | Check RDS status, failover |
| Agent Workflow Stuck | Any workflow running > 30 min | Kill and retry; check LLM API |

### Warning Alerts (Slack #alerts-warning)
| Alert | Condition | Action |
|-------|-----------|--------|
| High LLM Cost | Token usage > daily budget (configurable) | Review usage, consider model downgrade |
| Trend Scan Failures | > 3 consecutive scan failures | Check external API status |
| Publishing Failures | > 5 failed publications in 1 hour | Check platform API credentials |
| Error Rate Elevated | 5xx rate > 2% over 15 min | Review error logs |
| Queue Backlog | Celery queue depth > 50 tasks | Scale workers |

## 8. Dashboards (Grafana)

### Dashboard: Operations Overview
- API request rate and latency (P50, P95, P99)
- Active research sessions and completion rate
- Articles generated per day
- Publications per platform
- Error rate by service

### Dashboard: Agent Performance
- Agent workflow duration distribution
- LLM call latency by model
- Token usage over time (cost tracking)
- Research agent parallelism (concurrent agents)
- RAG retrieval quality (relevance scores)

### Dashboard: Infrastructure
- Pod CPU/memory usage
- PostgreSQL query latency and connection pool
- Redis hit rate and memory
- Celery worker utilization and queue depth
- Milvus query latency and index size

## 9. Health Endpoints

### `/api/v1/health` (public, no auth)
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-12T10:00:00Z",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "milvus": "ok",
    "celery": "ok"
  }
}
```

### `/api/v1/health/ready` (internal, for Kubernetes readiness probe)
Returns 200 only when all dependencies are connected and service is ready to accept traffic.
