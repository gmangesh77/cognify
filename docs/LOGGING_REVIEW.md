# Logging Implementation Review: Cognify

**Date**: 2026-03-25
**Reviewer**: Claude Code (Automated)
**Scope**: Full codebase — structlog configuration, correlation IDs, log levels, sensitive data handling, coverage gaps

---

## Executive Summary

Cognify has a **solid structured logging foundation** with JSON output, async-safe correlation ID propagation, correct log level discipline, and zero `print()` statements in production code. The main gap is the **database repository layer is completely silent** — CRUD failures and not-found conditions generate no log events. Vector store (Milvus) operations also have minimal logging. No automated sensitive field filtering is configured (relies on developer discipline, which is currently working).

| Area | Status | Notes |
|------|--------|-------|
| structlog configuration | Good | JSON in prod, console in dev, ISO timestamps |
| Correlation IDs | Good | Middleware-injected, async-safe, in response headers |
| Log levels | Good | Correct INFO/WARNING/ERROR usage |
| Sensitive data | Acceptable | Not logged in practice, but no automated filter |
| Pipeline logging | Good | All stages emit structured events |
| DB layer logging | **Missing** | Repository CRUD operations are silent |
| Vector store logging | **Minimal** | Insert/search not logged |
| Frontend logging | Minimal | `console.warn()` only, no error reporting |
| Metrics (Prometheus) | **Missing** | Documented in architecture, not implemented |

---

## 1. structlog Configuration

**File**: `src/utils/logging.py`

### Processors

| Processor | Purpose |
|-----------|---------|
| `merge_contextvars` | Merges async context variables (includes correlation IDs) |
| `add_log_level` | Adds `level` field to every log entry |
| `TimeStamper(fmt="iso", utc=True)` | ISO 8601 UTC timestamps |
| `StackInfoRenderer()` | Stack traces on errors |
| `UnicodeDecoder()` | Safe unicode handling |

### Output Format

| Mode | Renderer | Log Level |
|------|----------|-----------|
| Production (`debug=False`) | `JSONRenderer()` | INFO |
| Development (`debug=True`) | `ConsoleRenderer()` | DEBUG |

### Initialization

- Called at startup: `src/api/main.py:224` via `setup_logging(debug=settings.debug)`
- Uses `PrintLoggerFactory()` — outputs to stdout/stderr

---

## 2. Correlation ID Implementation

**File**: `src/api/middleware/correlation_id.py`

| Feature | Implementation |
|---------|---------------|
| Header | `x-request-id` (read from request, set on response) |
| Generation | `uuid.uuid4()` if no valid header provided |
| Validation | Regex `^[A-Za-z0-9\-_]{1,128}$` on incoming IDs |
| Storage | `contextvars.ContextVar[str]` — async-safe |
| Propagation | Merged into all log entries via `merge_contextvars` processor |
| Response | Set on outgoing response headers |
| Reset | Context var reset after each request |

### Middleware Registration Order (`src/api/main.py:453-471`)

1. Correlation ID (outermost — runs first)
2. Security Headers
3. CORS
4. SlowAPI (rate limiting)
5. Request Logging (innermost — sees correlation ID)

---

## 3. Logger Usage Across Codebase

### Instantiation Pattern

All files use the same pattern:
```python
import structlog
logger = structlog.get_logger()
```

### Coverage by Layer (47+ files)

| Layer | Files with Logger | Examples |
|-------|-------------------|----------|
| API routers | 12+ | `main.py`, `research.py`, `topics.py`, `settings_domains.py` |
| Middleware | 2 | `correlation_id.py`, `request_logging.py` |
| Services | 15+ | `content.py`, `research.py`, `task_dispatch.py`, `topic_ranking.py` |
| Research agents | 5+ | `orchestrator.py`, `web_search.py`, `evaluator.py`, `planner.py` |
| Content agents | 10+ | `nodes.py`, `chart_generator.py`, `diagram_generator.py`, `seo_node.py` |
| Trend sources | 5 | `arxiv.py`, `google_trends.py`, `hackernews.py`, `newsapi.py`, `reddit.py` |
| DB repositories | **0** | `repositories.py` — no logger |
| Frontend hooks | 2 | `use-settings.ts`, `use-scan-topics.ts` (console.warn only) |

### print() Statements

**None found** in `src/`. All logging goes through structlog.

---

## 4. Log Level Usage

### INFO — Business Events (50+ occurrences)

| Event | File | Description |
|-------|------|-------------|
| `full_article_pipeline_started` | `services/content.py:98` | Pipeline kickoff with session_id |
| `outline_generated` | `services/content.py:142` | Section count logged |
| `chart_rendered` | `agents/content/chart_generator.py:115` | Chart type and path |
| `mermaid_rendered` | `agents/content/diagram_generator.py:79` | Diagram path |
| `findings_indexed` | `agents/research/orchestrator.py:363` | Chunk count indexed in Milvus |
| `domain_created` | `api/routers/settings_domains.py:94` | Domain config created |
| `api_key_added` | `api/routers/settings_domains.py:158` | Key ID and service (not key value) |
| `section_queries_node_complete` | `agents/content/nodes.py:78` | Query count |
| `draft_sections_complete` | `agents/content/nodes.py:105` | Section count |
| `validate_article_complete` | `agents/content/nodes.py:127` | Word count |

### WARNING — Recoverable Issues (30+ occurrences)

| Event | File | Description |
|-------|------|-------------|
| `milvus_unavailable` | `api/main.py:104-108` | RAG degraded, pipeline continues |
| `content_pipeline_partial_failure` | `services/content.py:132-135` | Some steps failed, article still produced |
| `drafting_without_retriever` | `services/content.py:230` | No RAG context available |
| `skipping_content_pipeline` | `api/routers/research.py:112-116` | Research incomplete |
| `facet_dispatch_failed` | `services/task_dispatch.py:47-50` | One research facet timed out |
| `serpapi_query_failed` | `agents/research/web_search.py:90` | Search API error |
| `citation_url_unreachable` | `agents/content/citation_manager.py:130` | Dead link detected |
| `authorization_denied` | `api/dependencies.py:51-56` | Insufficient role |
| `seo_fallback_used` | `services/content.py:177` | SEO generation failed, defaults used |
| `step_record_failed` | `agents/research/orchestrator.py:127-129` | Step tracking DB write failed |

### ERROR — Unrecoverable Failures (15+ occurrences)

| Event | File | Description |
|-------|------|-------------|
| `content_deps_init_failed` | `api/main.py:142` | Startup dependency failure |
| `orchestrator_rebuild_failed` | `api/main.py:166-168` | LLM orchestrator init crashed |
| `content_pipeline_failed` | `api/routers/research.py:130-135` | Full pipeline crash (with `exc_info=True`) |
| `orchestrator_failed` | `services/research.py:178-183` | Agent workflow crash (with `exc_info=True`) |
| `persist_success_failed` | `services/research.py:189-193` | DB persistence after successful run |
| `unhandled_exception` | `api/main.py:438-442` | Global handler — full traceback |
| `embedding_model_failed` | `api/routers/topics.py:54-58` | Embedding model unavailable |
| `index_findings_failed` | `agents/research/orchestrator.py:316` | Milvus indexing crash |
| `seo_node_failed` | `agents/content/seo_node.py:118` | SEO optimization crash |
| `outline_generation_failed` | `agents/content/nodes.py:65` | LLM outline generation crash |

### DEBUG — Diagnostics (~10 occurrences)

| Event | File | Description |
|-------|------|-------------|
| Embedding details | `services/topic_ranking.py:113` | Embedding computation |
| Ranking details | `services/topic_ranking.py:174` | Score calculations |
| Feed processing | `services/trends/arxiv.py:115` | arXiv feed parsing |
| API parsing | `services/trends/newsapi.py:149` | NewsAPI response details |
| HN API details | `services/trends/hackernews.py:50` | Hacker News fetch details |
| Google Trends | `services/trends/google_trends.py:55` | Trend signal details |
| Reddit parsing | `services/trends/reddit.py:160,167` | Subreddit post details |

---

## 5. Sensitive Data Handling

### What's Properly Protected

| Data Type | Protection | Location |
|-----------|-----------|----------|
| API keys | Masked in responses (`_mask_key()` — first 8 + last 4 chars) | `api/routers/settings_domains.py:34-38` |
| API keys in logs | Only key ID and service name logged, never raw value | `api/routers/settings_domains.py` |
| DB credentials | Hostname-only logging: `db_url.split("@")[-1]` | `api/main.py:202` |
| Anthropic API key | Never logged (passed to settings only) | `api/main.py:129-142` |
| SerpAPI key | Never logged (set in headers only) | `services/serpapi_client.py:39-52` |
| JWT tokens | Never logged (used in auth middleware only) | `api/dependencies.py` |
| Passwords | Never logged (bcrypt hashing only) | `api/auth/password.py` |

### Gap: No Automated Filtering

**File**: `src/utils/logging.py`

The structlog configuration does **not** include a processor to automatically strip sensitive fields (e.g., `password`, `token`, `secret`, `api_key`) from log entries. Current safety relies on developers never passing these fields to logger calls.

**Risk**: Low (working in practice), but a single `logger.info("debug", api_key=key)` would leak a secret.

**Recommended fix**: Add a filtering processor:
```python
def _filter_sensitive(logger, method_name, event_dict):
    sensitive_keys = {"password", "token", "secret", "api_key", "authorization"}
    for key in sensitive_keys:
        if key in event_dict:
            event_dict[key] = "***REDACTED***"
    return event_dict
```

---

## 6. Request Logging Middleware

**File**: `src/api/middleware/request_logging.py`

### What's Logged Per Request

| Field | Example |
|-------|---------|
| `correlation_id` | `a1b2c3d4-...` |
| `method` | `GET` |
| `path` | `/api/v1/topics` |
| `status_code` | `200` |
| `duration_ms` | `45.2` |

### Excluded Paths

- `/docs`, `/openapi.json`, `/redoc` — skipped (correct)

### Not Logged (by design)

- Request body (privacy-conscious)
- Response body (privacy-conscious)
- Query parameters (not included)

---

## 7. Gaps and Missing Logging

### GAP 1: Database Repository Layer (HIGH)

**File**: `src/db/repositories.py` (541 lines, zero logger calls)

No logging in any CRUD operation. Failures are raised as exceptions but not logged at the repository level.

**Missing events**:
- Record not found (raises `ValueError` at lines 85, 176, 399 — no log)
- Insert/update failures
- Query execution time
- Connection errors

**Impact**: If a database query fails or a record is unexpectedly missing, there's no log trail at the data layer. Errors only appear if the calling service catches and logs them.

### GAP 2: Settings Repositories (MEDIUM)

**Files**: `src/db/settings_repositories.py`, `src/db/settings_singleton_repositories.py`

Same issue — no logging in settings CRUD operations.

### GAP 3: Milvus Vector Operations (MEDIUM)

**File**: `src/services/milvus_service.py` (268 lines, minimal logging)

- `insert_chunks()` — not logged
- `search()` — not logged
- `upsert()` — not logged
- Silent datetime parsing failure at line 40-41

**Missing events**:
- Embedding insertion count and duration
- Search query and result count
- Collection management operations

### GAP 4: Prometheus Metrics (MEDIUM)

Architecture docs (`OBSERVABILITY_PLAN.md`) specify metrics like:
- `cognify_http_requests_total`
- `cognify_articles_generated_total`
- `cognify_llm_calls_total`

**None are implemented.** No Prometheus client is configured.

### GAP 5: Frontend Error Reporting (LOW)

**Files**: `frontend/src/hooks/use-settings.ts`, `frontend/src/hooks/use-scan-topics.ts`

Frontend uses only `console.warn()` in catch blocks (9 instances). No error reporting service (e.g., Sentry) is configured. Acceptable for current stage but not production-ready for user-facing error tracking.

---

## 8. Summary Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Structured format (JSON) | 10/10 | JSONRenderer in production |
| Correlation IDs | 10/10 | Async-safe, in headers, in all logs |
| No print() in prod | 10/10 | Zero instances found |
| Log level discipline | 9/10 | Correct usage, minor edge cases |
| Business event coverage | 9/10 | All pipeline stages logged |
| Sensitive data protection | 8/10 | Works in practice, no automated filter |
| API request logging | 8/10 | Duration, status, path — no query params |
| Agent/pipeline logging | 8/10 | Step-by-step tracking with durations |
| Error context | 8/10 | `exc_info=True` on critical errors |
| Database layer logging | 2/10 | Repository layer completely silent |
| Vector store logging | 3/10 | Minimal — insert/search not logged |
| Metrics (Prometheus) | 0/10 | Not implemented |
| Frontend error reporting | 3/10 | console.warn only |
| **Overall** | **7.5/10** | Solid foundation, DB and metrics gaps |

---

## 9. Recommendations

### Immediate (Low Effort, High Impact)

1. **Add logger to `src/db/repositories.py`** — Log `warning` on not-found, `error` on write failures, `debug` on query execution
2. **Add sensitive field filter** to `src/utils/logging.py` — Automated redaction of `password`, `token`, `secret`, `api_key` fields
3. **Add `pool_pre_ping=True`** to `src/db/engine.py` — Prevents stale connection errors (related: connection failures are silent without DB logging)

### Short-Term (Next Sprint)

4. **Add logging to `src/services/milvus_service.py`** — Log insert count, search query, result count, operation duration
5. **Add logging to settings repositories** — Log config reads/writes for audit trail
6. **Log query parameters in request middleware** (sanitized) — Helps debug API issues

### Medium-Term

7. **Implement Prometheus metrics** — Per `OBSERVABILITY_PLAN.md` specifications
8. **Add frontend error reporting** — Sentry or similar for production error tracking
9. **Add request/response body logging** — Optional, admin-only, for debugging specific routes
