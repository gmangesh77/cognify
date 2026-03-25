# Logging Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 6 immediate + short-term logging gaps identified in `docs/LOGGING_REVIEW.md` — sensitive field filter, pool_pre_ping, repository logging, settings repo logging, Milvus logging, and request query param logging.

**Architecture:** Inline `structlog.get_logger()` pattern (matching all 47+ existing files). No decorators, mixins, or event listeners. Log calls placed in async methods (not sync executor helpers) to preserve correlation IDs.

**Tech Stack:** structlog, SQLAlchemy async, pytest, `structlog.testing.capture_logs()`

**Spec:** `docs/superpowers/specs/2026-03-25-logging-improvements-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/utils/logging.py` | Modify | Add `SENSITIVE_KEYS` constant, `_filter_sensitive` processor, wire into pipeline |
| `src/db/engine.py` | Modify | Add `pool_pre_ping=True` |
| `src/db/repositories.py` | Modify | Add logger + debug/warning log calls to 5 repository classes |
| `src/db/settings_repositories.py` | Modify | Add logger + debug/warning log calls to 2 classes |
| `src/db/settings_singleton_repositories.py` | Modify | Add logger + debug log calls to 3 classes |
| `src/services/milvus_service.py` | Modify | Add info/debug/warning log calls to async methods |
| `src/api/middleware/request_logging.py` | Modify | Add sanitized query_params field to request log |
| `tests/unit/test_logging.py` | Modify | Add tests for sensitive field filter |
| `tests/unit/services/test_milvus_service.py` | Modify | Add tests for Milvus log events |
| `tests/unit/api/test_middleware.py` | Modify | Add tests for query param logging |

---

### Task 1: Sensitive Field Filter

**Files:**
- Modify: `src/utils/logging.py`
- Modify: `tests/unit/test_logging.py`

- [ ] **Step 1: Write failing tests for the sensitive field filter**

Add to `tests/unit/test_logging.py`:

```python
from src.utils.logging import SENSITIVE_KEYS, _filter_sensitive


class TestSensitiveFieldFilter:
    def test_redacts_password_field(self) -> None:
        event_dict = {"event": "test", "password": "secret123"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["password"] == "***REDACTED***"

    def test_redacts_api_key_field(self) -> None:
        event_dict = {"event": "test", "api_key": "sk-abc123"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["api_key"] == "***REDACTED***"

    def test_redacts_token_field(self) -> None:
        event_dict = {"event": "test", "token": "jwt-xyz"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["token"] == "***REDACTED***"

    def test_redacts_authorization_field(self) -> None:
        event_dict = {"event": "test", "authorization": "Bearer xyz"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["authorization"] == "***REDACTED***"

    def test_redacts_secret_field(self) -> None:
        event_dict = {"event": "test", "secret": "my-secret"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["secret"] == "***REDACTED***"

    def test_passes_non_sensitive_fields(self) -> None:
        event_dict = {"event": "test", "user_id": "abc", "path": "/api"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["user_id"] == "abc"
        assert result["path"] == "/api"

    def test_handles_multiple_sensitive_fields(self) -> None:
        event_dict = {"event": "test", "password": "x", "token": "y", "user": "z"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["password"] == "***REDACTED***"
        assert result["token"] == "***REDACTED***"
        assert result["user"] == "z"

    def test_sensitive_keys_constant_is_frozenset(self) -> None:
        assert isinstance(SENSITIVE_KEYS, frozenset)
        assert "password" in SENSITIVE_KEYS
        assert "token" in SENSITIVE_KEYS
        assert "secret" in SENSITIVE_KEYS
        assert "api_key" in SENSITIVE_KEYS
        assert "authorization" in SENSITIVE_KEYS

    def test_filter_in_pipeline(self) -> None:
        """Verify filter is wired into the structlog pipeline."""
        from src.utils.logging import setup_logging
        setup_logging(debug=False)
        config = structlog.get_config()
        assert _filter_sensitive in config["processors"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: FAIL — `ImportError: cannot import name 'SENSITIVE_KEYS'`

- [ ] **Step 3: Implement the sensitive field filter**

Replace contents of `src/utils/logging.py`:

```python
import logging

import structlog

SENSITIVE_KEYS = frozenset({"password", "token", "secret", "api_key", "authorization"})


def _filter_sensitive(
    logger: object,
    method_name: str,
    event_dict: dict[str, object],
) -> dict[str, object]:
    """Redact sensitive fields from log entries."""
    for key in SENSITIVE_KEYS:
        if key in event_dict:
            event_dict[key] = "***REDACTED***"
    return event_dict


def setup_logging(debug: bool = False) -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _filter_sensitive,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/logging.py tests/unit/test_logging.py
git commit -m "feat: add sensitive field auto-redaction to structlog pipeline"
```

---

### Task 2: Database Engine pool_pre_ping

**Files:**
- Modify: `src/db/engine.py`

- [ ] **Step 1: Add pool_pre_ping=True**

In `src/db/engine.py`, add `pool_pre_ping=True` to the `_create_engine()` call:

```python
def create_async_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    return _create_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `uv run pytest tests/unit/ -x -q`
Expected: All pass (no behavioral change, just a connection pool setting)

- [ ] **Step 3: Commit**

```bash
git add src/db/engine.py
git commit -m "fix: add pool_pre_ping to prevent stale DB connections"
```

---

### Task 3: Repository Logging — `src/db/repositories.py`

**Files:**
- Modify: `src/db/repositories.py`

This is the largest change. Add `import structlog` and `logger = structlog.get_logger()` at module level, then add log calls to all 5 repository classes.

**Testing note:** No dedicated logging tests for repository classes. These are all `debug`/`warning` level additive log calls — behavioral correctness is verified by the existing integration tests in `tests/integration/db/test_pg_repositories.py`. The high-value logging tests (sensitive filter, Milvus events, middleware query params) are covered in Tasks 1, 5, and 6.

- [ ] **Step 1: Add logger import and module-level logger**

At the top of `src/db/repositories.py`, after the existing imports, add:

```python
import structlog

logger = structlog.get_logger()
```

- [ ] **Step 2: Add logging to PgResearchSessionRepository**

In `create()` — after `await db.refresh(row)`, before `return`:
```python
logger.debug("research_session_created", session_id=str(session.id), status=session.status)
```

In `get()` — no change (returns None, callers handle missing).

In `update()` — after the `if row is None` check, add warning:
```python
if row is None:
    logger.warning("research_session_not_found", session_id=str(session.id))
    raise ValueError(...)
```
After `await db.refresh(row)`, before `return`:
```python
logger.debug("research_session_updated", session_id=str(session.id), status=session.status)
```

In `list()` — after getting `total` and `rows`, before `return`:
```python
logger.debug("research_sessions_listed", status=status, page=page, size=size, total=total)
```

- [ ] **Step 3: Add logging to PgAgentStepRepository**

In `create()` — after `await db.refresh(row)`:
```python
logger.debug("agent_step_created", step_id=str(step.id), session_id=str(step.session_id))
```

In `update()` — after the `if row is None` check:
```python
if row is None:
    logger.warning("agent_step_not_found", step_id=str(step.id))
    raise ValueError(...)
```
After `await db.refresh(row)`:
```python
logger.debug("agent_step_updated", step_id=str(step.id), status=step.status)
```

In `list_by_session()` — after `rows`:
```python
logger.debug("agent_steps_listed", session_id=str(session_id), count=len(rows))
```

- [ ] **Step 4: Add logging to PgTopicRepository**

In `create_from_ranked()` — after `await session.commit()`:
```python
logger.debug("topic_created", topic_id=str(topic_id), domain=domain, source=topic.source)
```

In `update_from_scan()` — after `await session.commit()`:
```python
logger.debug("topic_updated", topic_id=str(topic_id), trend_score=topic.trend_score)
```

In `list_by_domain()` — after getting `total` and `rows`:
```python
logger.debug("topics_listed", domain=domain, page=page, size=size, total=total)
```

- [ ] **Step 5: Add logging to PgArticleDraftRepository**

In `create()` — after `await db.refresh(row)`:
```python
logger.debug("article_draft_created", draft_id=str(draft.id), status=draft.status.value)
```

In `update()` — after the `if row is None` check:
```python
if row is None:
    logger.warning("article_draft_not_found", draft_id=str(draft.id))
    raise ValueError(...)
```
After `await db.refresh(row)`:
```python
logger.debug("article_draft_updated", draft_id=str(draft.id), status=draft.status.value)
```

- [ ] **Step 6: Add logging to PgArticleRepository**

In `create()` — after `await db.refresh(row)`:
```python
logger.debug("article_created", article_id=str(article.id), title=article.title[:80])
```

In `list()` — after getting `total` and `rows`:
```python
logger.debug("articles_listed", page=page, size=size, total=total)
```

- [ ] **Step 7: Run full test suite to verify no regression**

Run: `uv run pytest tests/unit/ -x -q`
Expected: All pass. Logging is additive — no behavioral changes.

- [ ] **Step 8: Commit**

```bash
git add src/db/repositories.py
git commit -m "feat: add structured logging to all database repositories"
```

---

### Task 4: Settings Repository Logging

**Files:**
- Modify: `src/db/settings_repositories.py`
- Modify: `src/db/settings_singleton_repositories.py`

- [ ] **Step 1: Add logging to settings_repositories.py**

Add at top after existing imports:
```python
import structlog

logger = structlog.get_logger()
```

In `PgDomainConfigRepository`:
- `create()` after commit: `logger.debug("domain_config_created", domain_id=str(domain.id), name=domain.name)`
- `update()` not-found path: `logger.warning("domain_config_not_found", domain_id=str(domain.id))`
- `update()` after commit: `logger.debug("domain_config_updated", domain_id=str(domain.id))`
- `delete()` when row exists, after commit: `logger.debug("domain_config_deleted", domain_id=str(domain_id))`
- `list_all()` after result: `logger.debug("domain_configs_listed", count=len(result))`
  Note: `result` here refers to the final list — capture the return value before returning.

In `PgApiKeyRepository`:
- `create()` after commit: `logger.debug("api_key_created", key_id=str(key.id), service=key.service)`
- `rotate()` not-found path: `logger.warning("api_key_not_found", key_id=str(key_id))`
- `rotate()` after commit: `logger.debug("api_key_rotated", key_id=str(key_id))`
- `delete()` when row exists, after commit: `logger.debug("api_key_deleted", key_id=str(key_id))`
- `list_all()` after result: `logger.debug("api_keys_listed", count=len(result))`

**Important**: Never log `encrypted_key` or `masked_key` values — only `key_id` and `service`.

- [ ] **Step 2: Add logging to settings_singleton_repositories.py**

Add at top after existing imports:
```python
import structlog

logger = structlog.get_logger()
```

In `PgLlmConfigRepository`:
- `get_or_create()` when creating new: `logger.debug("llm_config_loaded", created_default=True)`
- `get_or_create()` when existing found: `logger.debug("llm_config_loaded", created_default=False)`
- `update()` after commit: `logger.debug("llm_config_updated")`

In `PgSeoDefaultsRepository`:
- `get_or_create()` when creating new: `logger.debug("seo_defaults_loaded", created_default=True)`
- `get_or_create()` when existing found: `logger.debug("seo_defaults_loaded", created_default=False)`
- `update()` after commit: `logger.debug("seo_defaults_updated")`

In `PgGeneralConfigRepository`:
- `get_or_create()` when creating new: `logger.debug("general_config_loaded", created_default=True)`
- `get_or_create()` when existing found: `logger.debug("general_config_loaded", created_default=False)`
- `update()` after commit: `logger.debug("general_config_updated")`

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/unit/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/db/settings_repositories.py src/db/settings_singleton_repositories.py
git commit -m "feat: add structured logging to settings repositories"
```

---

### Task 5: Milvus Service Logging

**Files:**
- Modify: `src/services/milvus_service.py`
- Modify: `tests/unit/services/test_milvus_service.py`

- [ ] **Step 1: Write failing tests for Milvus log events**

Add to `tests/unit/services/test_milvus_service.py`:

```python
import structlog
import src.services.milvus_service as milvus_mod


class TestMilvusServiceLogging:
    async def test_insert_chunks_logs_debug(
        self, milvus_db: MilvusService,
    ) -> None:
        milvus_mod.logger = structlog.get_logger()
        chunks = _make_chunks(3)
        embeddings = _make_embeddings(3)
        with structlog.testing.capture_logs() as logs:
            await milvus_db.insert_chunks(chunks, embeddings)
        inserted = [e for e in logs if e["event"] == "milvus_chunks_inserted"]
        assert len(inserted) == 1
        assert inserted[0]["count"] == 3
        assert inserted[0]["log_level"] == "debug"

    async def test_search_logs_debug(
        self, milvus_db: MilvusService, mock_client: MagicMock,
    ) -> None:
        milvus_mod.logger = structlog.get_logger()
        mock_client.search.return_value = [[
            {"entity": {"text": "t", "source_url": "u", "source_title": "s",
                        "chunk_index": 0, "published_at": "", "author": ""},
             "distance": 0.9},
        ]]
        emb = _make_embeddings(1)[0]
        with structlog.testing.capture_logs() as logs:
            await milvus_db.search(emb, "topic-1", top_k=5)
        searched = [e for e in logs if e["event"] == "milvus_search_executed"]
        assert len(searched) == 1
        assert searched[0]["results_count"] == 1
        assert searched[0]["log_level"] == "debug"

    async def test_search_empty_logs_warning(
        self, milvus_db: MilvusService, mock_client: MagicMock,
    ) -> None:
        milvus_mod.logger = structlog.get_logger()
        mock_client.search.return_value = [[]]
        emb = _make_embeddings(1)[0]
        with structlog.testing.capture_logs() as logs:
            await milvus_db.search(emb, "topic-1", top_k=5)
        empty = [e for e in logs if e["event"] == "milvus_search_empty"]
        assert len(empty) == 1
        assert empty[0]["log_level"] == "warning"

    async def test_ensure_collection_logs_info_on_create(
        self, mock_client: MagicMock,
    ) -> None:
        milvus_mod.logger = structlog.get_logger()
        mock_client.has_collection.return_value = False
        with (
            patch("src.services.milvus_service.MilvusClient", return_value=mock_client),
            structlog.testing.capture_logs() as logs,
        ):
            svc = MilvusService(uri="mock://test", collection_name="test_chunks")
            svc.ensure_collection()
        created = [e for e in logs if e["event"] == "milvus_collection_created"]
        assert len(created) == 1
        assert created[0]["log_level"] == "info"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/services/test_milvus_service.py::TestMilvusServiceLogging -v`
Expected: FAIL — no log events captured (logging not yet added)

- [ ] **Step 3: Add logging to milvus_service.py**

In `ensure_collection()` — after `self._client.create_collection(...)`:
```python
logger.info("milvus_collection_created", collection_name=self._collection_name)
```

In `insert_chunks()` — replace the `return await loop.run_in_executor(...)` with a variable assignment, log call, and separate return statement:
```python
async def insert_chunks(self, chunks, embeddings):
    ...
    if not chunks:
        return 0
    data = self._prepare_insert_data(chunks, embeddings)
    loop = asyncio.get_running_loop()
    count = await loop.run_in_executor(None, self._sync_insert, data)
    logger.debug(
        "milvus_chunks_inserted",
        count=count,
        topic_id=chunks[0].topic_id if chunks else "",
        session_id=chunks[0].session_id if chunks else "",
    )
    return count
```

In `search()` — replace `return await loop.run_in_executor(...)` with variable assignment, log, return:
```python
async def search(self, query_embedding, topic_id, top_k):
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(
        None, self._sync_search, query_embedding, topic_id, top_k,
    )
    if not results:
        logger.warning("milvus_search_empty", topic_id=topic_id, top_k=top_k)
    else:
        logger.debug(
            "milvus_search_executed",
            topic_id=topic_id,
            top_k=top_k,
            results_count=len(results),
        )
    return results
```

In `get_stats()` — replace `return await loop.run_in_executor(...)` with variable assignment, log, return:
```python
async def get_stats(self, topic_id=None):
    loop = asyncio.get_running_loop()
    stats = await loop.run_in_executor(None, self._sync_get_stats, topic_id)
    logger.debug(
        "milvus_stats_fetched",
        total_chunks=stats.total_chunks,
        collection_name=stats.collection_name,
    )
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/services/test_milvus_service.py -v`
Expected: All pass (new + existing)

- [ ] **Step 5: Commit**

```bash
git add src/services/milvus_service.py tests/unit/services/test_milvus_service.py
git commit -m "feat: add structured logging to Milvus vector service"
```

---

### Task 6: Request Middleware Query Parameter Logging

**Files:**
- Modify: `src/api/middleware/request_logging.py`
- Modify: `tests/unit/api/test_middleware.py`

- [ ] **Step 1: Write failing tests for query param logging**

Add to `tests/unit/api/test_middleware.py`. First, add a new fixture with a route that accepts query params (reuse existing `app_with_logging` fixture which already has `/test`):

```python
class TestRequestLoggingQueryParams:
    async def test_logs_query_params(
        self,
        log_client: httpx.AsyncClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(debug=False)
        await log_client.get("/test?page=1&size=20")
        captured = capsys.readouterr().out
        log_line = json.loads(captured.strip().split("\n")[-1])
        assert log_line["query_params"] == {"page": "1", "size": "20"}

    async def test_omits_query_params_when_empty(
        self,
        log_client: httpx.AsyncClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(debug=False)
        await log_client.get("/test")
        captured = capsys.readouterr().out
        log_line = json.loads(captured.strip().split("\n")[-1])
        assert "query_params" not in log_line

    async def test_redacts_sensitive_query_params(
        self,
        log_client: httpx.AsyncClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(debug=False)
        await log_client.get("/test?token=secret123&page=1")
        captured = capsys.readouterr().out
        log_line = json.loads(captured.strip().split("\n")[-1])
        assert log_line["query_params"]["token"] == "***REDACTED***"
        assert log_line["query_params"]["page"] == "1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/test_middleware.py::TestRequestLoggingQueryParams -v`
Expected: FAIL — `query_params` key not in log output

- [ ] **Step 3: Implement query param logging in middleware**

Update `src/api/middleware/request_logging.py`:

```python
import time

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

from src.api.middleware.correlation_id import correlation_id_ctx
from src.utils.logging import SENSITIVE_KEYS

logger = structlog.get_logger()

_SKIP_PATHS = {"/docs", "/openapi.json", "/redoc"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        log_kwargs: dict[str, object] = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id_ctx.get(""),
        }

        params = dict(request.query_params)
        if params:
            log_kwargs["query_params"] = {
                k: "***REDACTED***" if k in SENSITIVE_KEYS else v
                for k, v in params.items()
            }

        logger.info("request_completed", **log_kwargs)
        return response
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/test_middleware.py -v`
Expected: All pass (new + existing)

- [ ] **Step 5: Commit**

```bash
git add src/api/middleware/request_logging.py tests/unit/api/test_middleware.py
git commit -m "feat: add sanitized query params to request logging middleware"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/unit/ --cov=src --cov-report=term-missing -q`
Expected: All pass, no coverage regression

- [ ] **Step 2: Run linter**

Run: `uv run ruff check src/utils/logging.py src/db/engine.py src/db/repositories.py src/db/settings_repositories.py src/db/settings_singleton_repositories.py src/services/milvus_service.py src/api/middleware/request_logging.py`
Expected: No errors

- [ ] **Step 3: Run type checker**

Run: `uv run mypy src/utils/logging.py src/db/engine.py src/db/repositories.py src/db/settings_repositories.py src/db/settings_singleton_repositories.py src/services/milvus_service.py src/api/middleware/request_logging.py`
Expected: No errors
