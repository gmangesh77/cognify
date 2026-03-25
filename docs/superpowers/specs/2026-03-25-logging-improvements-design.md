# Logging Improvements — Design Spec

**Date**: 2026-03-25
**Ticket**: Implements recommendations 1-6 from `docs/LOGGING_REVIEW.md`
**Scope**: Immediate (1-3) + Short-Term (4-6) logging gaps

---

## Summary

Add structured logging to the database repository layer, settings repositories, and Milvus vector service. Add a sensitive field auto-redaction processor to structlog. Add `pool_pre_ping` to the DB engine. Add sanitized query parameters to request logging middleware.

## Approach

**Option A (chosen)**: Inline `structlog.get_logger()` — matches the existing codebase pattern used in all 47+ files that have logging today.

---

## 1. Sensitive Field Filter

**File**: `src/utils/logging.py`

Add a `_filter_sensitive` processor to the structlog pipeline, inserted before the renderer. Auto-redacts log fields with exact key matches.

```python
SENSITIVE_KEYS = frozenset({"password", "token", "secret", "api_key", "authorization"})

def _filter_sensitive(
    logger: object,
    method_name: str,
    event_dict: dict[str, object],
) -> dict[str, object]:
    for key in SENSITIVE_KEYS:
        if key in event_dict:
            event_dict[key] = "***REDACTED***"
    return event_dict
```

Insert into the `shared_processors` list after `merge_contextvars` and before `add_log_level`.

## 2. Database Engine — `pool_pre_ping`

**File**: `src/db/engine.py`

Add `pool_pre_ping=True` to `create_async_engine()`. Tests connections before reuse from the pool, preventing stale connection errors.

## 3. Repository Logging — `src/db/repositories.py`

Add `logger = structlog.get_logger()` at module level. Covers 5 classes:

| Class | `debug` events | `warning` events |
|-------|---------------|-----------------|
| `PgResearchSessionRepository` | `research_session_created`, `research_session_updated`, `research_sessions_listed` | `research_session_not_found` |
| `PgAgentStepRepository` | `agent_step_created`, `agent_step_updated`, `agent_steps_listed` | `agent_step_not_found` |
| `PgTopicRepository` | `topic_created`, `topic_updated`, `topics_listed` | (returns None, no ValueError) |
| `PgArticleDraftRepository` | `article_draft_created`, `article_draft_updated` | `article_draft_not_found` |
| `PgArticleRepository` | `article_created`, `articles_listed` | (returns None, no ValueError) |

### Log fields

- All events include the entity ID (`session_id=`, `topic_id=`, `draft_id=`, `article_id=`, `step_id=`)
- `*_created` / `*_updated` events include `status` where applicable
- `*_listed` events include pagination fields where the method has them (`page`, `size`, `total`), or `count` for non-paginated lists (e.g., `agent_steps_listed` includes `session_id` and `count`)
- No try/except wrappers — exceptions propagate to the service layer which already logs them

## 4. Settings Repository Logging

**Files**: `src/db/settings_repositories.py`, `src/db/settings_singleton_repositories.py`

Add `logger = structlog.get_logger()` to both files. Same pattern as main repositories.

### `settings_repositories.py`

| Class | `debug` events | `warning` events |
|-------|---------------|-----------------|
| `PgDomainConfigRepository` | `domain_config_created`, `domain_config_updated`, `domain_config_deleted` (only when row exists), `domain_configs_listed` | `domain_config_not_found` (on update ValueError) |
| `PgApiKeyRepository` | `api_key_created`, `api_key_rotated`, `api_key_deleted` (only when row exists), `api_keys_listed` | `api_key_not_found` (on rotate ValueError) |

Note: `rotate()` and `delete()` on `PgApiKeyRepository` are audit-relevant security operations and must be logged.

### `settings_singleton_repositories.py`

| Class | `debug` events |
|-------|---------------|
| `PgLlmConfigRepository` | `llm_config_loaded` (with `created_default=True/False`), `llm_config_updated` |
| `PgSeoDefaultsRepository` | `seo_defaults_loaded` (with `created_default=True/False`), `seo_defaults_updated` |
| `PgGeneralConfigRepository` | `general_config_loaded` (with `created_default=True/False`), `general_config_updated` |

## 5. Milvus Service Logging

**File**: `src/services/milvus_service.py` (already has `logger = structlog.get_logger()`)

| Level | Event | Fields | Method |
|-------|-------|--------|--------|
| `info` | `milvus_collection_created` | `collection_name` | `ensure_collection()` |
| `debug` | `milvus_chunks_inserted` | `count`, `topic_id`, `session_id` | `insert_chunks()` |
| `debug` | `milvus_search_executed` | `topic_id`, `top_k`, `results_count` | `search()` |
| `debug` | `milvus_stats_fetched` | `total_chunks`, `collection_name` | `get_stats()` |
| `warning` | `milvus_search_empty` | `topic_id`, `top_k` | `search()` |

**Placement**: All log calls go in the async wrapper methods (`insert_chunks()`, `search()`, `get_stats()`), NOT in the `_sync_*` methods. This ensures correlation IDs from `contextvars` are captured — `run_in_executor` threads may not inherit the context.

No try/except — errors propagate to callers.

## 6. Request Middleware Query Parameters

**File**: `src/api/middleware/request_logging.py`

Add sanitized query parameters to the existing `request_completed` log event. Import `SENSITIVE_KEYS` from `src/utils/logging.py`.

- Extract `request.query_params` as a dict
- Redact values for any keys in `SENSITIVE_KEYS`
- Include as `query_params=` field only when non-empty
- No new log events — extends the existing one

## Testing Strategy

- **Unit test**: `_filter_sensitive` processor redacts matching keys, passes others through
- **Unit test**: Milvus logging — mock `MilvusClient`, verify log events emitted with correct fields
- **Unit test**: Repository logging — use existing test patterns with async session fixtures, verify `debug`/`warning` events via `structlog.testing.capture_logs()` (works with async code since structlog uses `contextvars`)
- **Unit test**: Request middleware query param logging — verify params appear in log event when present, omitted when empty, sensitive keys redacted
- **No unit test for `pool_pre_ping`** — validated by integration tests and manual verification
- **No integration test changes needed** — logging is additive, doesn't change behavior

## Files Changed

| File | Change |
|------|--------|
| `src/utils/logging.py` | Add `SENSITIVE_KEYS`, `_filter_sensitive` processor, wire into pipeline |
| `src/db/engine.py` | Add `pool_pre_ping=True` |
| `src/db/repositories.py` | Add logger + debug/warning log calls to all 5 classes |
| `src/db/settings_repositories.py` | Add logger + debug/warning log calls |
| `src/db/settings_singleton_repositories.py` | Add logger + debug log calls |
| `src/services/milvus_service.py` | Add info/debug/warning log calls |
| `src/api/middleware/request_logging.py` | Add sanitized query_params to request log |
| `tests/unit/test_logging.py` | Modify — add sensitive field filter tests |
| `tests/unit/services/test_milvus_service.py` | Modify — add Milvus log event tests |
| `tests/unit/api/test_middleware.py` | Modify — add query param logging tests |
