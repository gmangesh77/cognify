# Engineering Learnings & Gotchas

> **Purpose**: Document hard-won lessons from debugging production issues. Read this before making changes to avoid repeating past mistakes. Referenced from CLAUDE.md.

---

## L-001: Pydantic datetime + SQLAlchemy JSONB = Silent Failure

**Issue**: `model_dump()` returns Python `datetime` objects. When these are stored in a PostgreSQL JSONB column via SQLAlchemy, `json.dumps()` fails with `TypeError: Object of type datetime is not JSON serializable`.

**Hit 3 times**:
1. `findings_data` in `research_sessions` table (commit `51a57ab`)
2. `global_citations` in `article_drafts` table (commit `17b66bb`)
3. `section_drafts`, `citations`, `visuals` in `article_drafts` table (same commit)

**Rule**: **ALWAYS use `model_dump(mode="json")` when serializing Pydantic models for JSONB storage.** Never use bare `model_dump()` for data going into a JSONB column.

**Grep check before storing to JSONB**:
```bash
grep -rn "model_dump()" src/ | grep -v "mode=" | grep -v "test"
```
Any hit near a JSONB write path is a bug.

**Affected tables** (JSONB columns):
- `research_sessions.findings_data`
- `article_drafts.section_drafts`
- `article_drafts.citations`
- `article_drafts.seo_result`
- `article_drafts.global_citations`
- `article_drafts.visuals`
- `article_drafts.outline`

**TRAP**: Even when you fix the storage layer (`_jsonable()` in content.py), upstream code may ALREADY convert Pydantic models to dicts with bare `model_dump()`. Example: `citation_manager.py` was calling `c.model_dump()` which produces dicts with datetime values. Then `_jsonable()` sees dicts (no `model_dump` method) and passes them through unchanged. **Fix BOTH the source (where model_dump is called) AND the sink (where data is written to DB).**

**Full grep for L-001 compliance**:
```bash
grep -rn "model_dump()" src/ | grep -v "mode=" | grep -v test | grep -v __pycache__
```

**TRAP 2**: Repository methods that call `.model_dump(mode="json")` on items will crash if upstream code already converted them to dicts (via `_jsonable()` or bare `model_dump()`). The repository's `_to_jsonb()` helper handles BOTH cases: `hasattr(item, "model_dump")` → call it, else pass through. **Always use `_to_jsonb()` in repository create/update for ALL JSONB fields.**

---

## L-002: LLM Responses Wrapped in Markdown Fences

**Issue**: Claude wraps JSON output in ` ```json ... ``` ` markdown fences, causing `json.loads()` to fail with `JSONDecodeError`.

**Rule**: **ALWAYS use `parse_llm_json()` from `src/utils/llm_json.py` when parsing JSON from LLM responses.** Never use bare `json.loads()` on LLM output.

**Grep check**:
```bash
grep -rn "json.loads.*response\|json.loads.*content" src/agents/ | grep -v "parse_llm_json"
```

**Affected modules**: All 9 files in `src/agents/` that call LLMs and parse JSON responses.

---

## L-003: Status Field Changes Break Multiple Consumers

**Issue**: Changing a session `status` value (e.g., adding `generating_article`, `article_complete`) breaks:
- Frontend filter tabs (hardcoded status lists)
- Frontend polling logic (which statuses are "active")
- Backend query filters (exact string match)
- Frontend status badges (color/label mapping)
- Frontend progress bars (percentage mapping)
- `_load_session()` validation (whitelist check)

**Rule**: Before changing any status value:
1. Grep ALL consumers: `grep -rn "status.*complete\|complete.*status" src/ frontend/src/`
2. Check frontend types: `frontend/src/types/research.ts`
3. Check filter tabs: `frontend/src/components/research/session-filters.tsx`
4. Check polling: `frontend/src/hooks/use-research-sessions.ts`
5. Check badge: `frontend/src/components/research/session-status-badge.tsx`
6. Check progress: `frontend/src/components/research/session-card.tsx`
7. Check backend filters: `src/db/repositories.py` (list method)
8. Check validators: `src/services/content.py` (`_load_session`)

---

## L-004: Milvus Collection Must Be Created Before Use

**Issue**: Connecting to a fresh Milvus instance (or switching from file-based to Docker) fails with `collection not found` because `ensure_collection()` was never called.

**Rule**: **ALWAYS call `milvus_svc.ensure_collection()` immediately after creating a `MilvusService` instance** in initialization paths.

**Grep check**:
```bash
grep -rn "MilvusService(" src/ | grep -v test | grep -v "ensure_collection"
```
Every `MilvusService(` instantiation must be followed by `.ensure_collection()`.

---

## L-005: Integration Tests Leak Data to Real Database

**Issue**: Tests in `tests/integration/db/test_pg_repositories.py` write directly to the production PostgreSQL database (same `docker-compose.yml` instance). Test topics, sessions, and articles appear in the UI.

**Pattern**: Test topics have title `"Test Topic {hex}"` and source `"seed"`.

**Cleanup query**:
```sql
DELETE FROM topics WHERE title LIKE 'Test Topic%' AND source = 'seed';
DELETE FROM research_sessions WHERE topic_title LIKE 'Test%';
```

**Rule**: After running `pytest tests/integration/`, check for leaked test data. Ideally, integration tests should use a separate database or transaction rollback.

---

## L-006: Content Pipeline Runs Full Graph, Not Separate Steps

**Issue**: `ContentService.generate_outline()` calls `_run_pipeline()` which runs the ENTIRE content graph (outline → queries → draft → validate → citations → humanize → SEO → charts → diagrams). It does NOT stop at the outline. This means:
- Calling `generate_outline()` then `draft_article()` runs the pipeline TWICE
- Test fixtures need enough FakeLLM responses for the full pipeline, not just the outline

**Rule**: Use `generate_full_article()` for the complete flow. The separate `generate_outline()` / `draft_article()` / `finalize_article()` methods exist for the REST API but each invokes the full graph from different starting points.

---

## L-007: FakeLLM Response Count Must Match Full Pipeline

**Issue**: Tests using `FakeListChatModel` need enough responses for every LLM call in the full pipeline. When the pipeline changed from outline-only to full-pipeline, many tests broke with "no more responses" errors.

**Minimum responses for full pipeline** (1 section):
1. Outline JSON
2. Queries JSON (array of SectionQueries)
3. Section draft text (per section)
4. SEO metadata JSON
5. AI discoverability JSON
6. Chart proposals JSON
7. Diagram proposals JSON
8. Extra padding responses (for validation/retry nodes)

**Rule**: Use a `_full_pipeline_responses()` helper that provides ~10+ responses and multiply by number of pipeline invocations in the test.
