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

See L-011 for the supported half-graph entry points (AUTHOR-002).

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

---

## L-008: Azure DevOps Work Item States Vary by Type

**Issue**: Trying to close work items with `--state Closed` fails for Task type items. Different work item types have different valid terminal states.

**Hit multiple times**: When bulk-closing resolved bugs and tasks after PR merges.

**Valid terminal states by type**:

| Work Item Type | Terminal State |
|---------------|---------------|
| User Story | `Closed` |
| Bug | `Closed` |
| Task | `Completed` |
| Epic | `Closed` |

**Rule**: Check work item type before setting state. "Resolved" is an intermediate state (fixed but not verified), not a terminal state. Never leave items in "Resolved" — move to the correct terminal state.

**CLI quirks**:
- `az boards work-item update` does NOT accept `--project` — the project is inferred from the work item
- `az boards query` REQUIRES `--project` for WIQL filtering by `System.TeamProject`
- Connection resets are common — add 3-5s pauses between sequential calls; parallel calls reliably fail
- Use `az boards work-item show --id <id> -o table` to check type before bulk state changes

---

## L-009: Ghost 5 Requires Lexical Format, Not Raw HTML

**Issue**: Ghost 5.130+ silently ignores `html` field (even with `"source": "html"`) in the Admin API POST body. Posts are created with empty content — no error returned, just status 201 with no body.

**Root cause**: Ghost 5 migrated from Mobiledoc to Lexical editor. The `html` and `mobiledoc` fields are no longer writable via the API.

**Rule**: **Wrap HTML content in a Lexical HTML card** when publishing to Ghost 5+:
```python
lexical = json.dumps({
    "root": {
        "children": [{"type": "html", "version": 1, "html": html_content}],
        "direction": None, "format": "", "indent": 0,
        "type": "root", "version": 1,
    }
})
# Send as: {"posts": [{"title": "...", "lexical": lexical, ...}]}
```

**Verification**: Query the Admin API with `?formats=html` — if `html` is empty/null but `lexical` contains the card, the content is stored correctly.

---

## L-010: Encryption Key Must Be Stable Across Restarts

**Issue**: Without `COGNIFY_ENCRYPTION_KEY` in `.env`, the encryption module auto-generates an ephemeral Fernet key. API keys saved to DB via the Settings UI are encrypted with this key. On server restart, a new ephemeral key is generated, making all DB-stored keys permanently unrecoverable. The key resolver then crashes the entire app on startup with `InvalidEncryptionKey`.

**Rule**:
1. **Always set `COGNIFY_ENCRYPTION_KEY`** in `.env` — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
2. **Key resolver must catch decryption failures** and fall back to `.env` values (fixed in `src/utils/key_resolver.py`)
3. After changing the encryption key, all DB-stored API keys must be re-saved through the Settings UI

---

## L-011: Content Graph Re-entry — Outline Gate Semantics

**Issue**: The legacy split-step methods (`ContentService.generate_outline()` / `draft_article()`) both enter the graph at `generate_outline`, so "outline only" used to run the whole pipeline (see L-006). AUTHOR-002 added real half-graph support; use it instead of re-inventing it.

**How the gate works** (`src/services/content/outline_gate.py`, ADR-006):
- **Stop after planning**: `ContentGraphDeps(stop_after_outline=True)` routes `generate_queries → END`. The result has `outline` + `section_queries` and no drafts.
- **Resume from an approved outline**: seed the initial state with `outline=<ArticleOutline>` and `status="outline_complete"` and run the normal full graph — `outline_node` no-ops when an outline is already present, so drafting starts from the stored outline (queries are regenerated, which is what you want after the user edited headings).
- `OutlineContext.instruction` (from `state["outline_instruction"]`) is appended to the outline prompt for "regenerate with instruction".
- Session statuses: research `complete` → (gate on) `awaiting_outline_review` → approve → `generating_article` → `article_complete|article_failed`; `cancelled` is terminal. Both new statuses are L-003 consumers — grep before touching.

**TRAP**: `ContentService._graph_deps()` must ALWAYS return a `ContentGraphDeps` (even with `step_repo=None`) — returning `None` silently drops `stop_after_outline` and the "outline-only" run executes the entire pipeline (caught in review of AUTHOR-002 Task 4; regression test `TestGraphDepsWithoutStepRepo`).

**Rule**: Persisted `ArticleDraft.status == outline_complete` is the durable checkpoint; `OutlineGateService.generate_from_outline()` is the only supported way to resume. Do not call the legacy `draft_article()` for new flows.

---

## L-012: Brief values are copied onto the session, never read back

**Context** (AUTHOR-003, ADR-007): `ResearchService.start_session(topic_id, params)` takes a `SessionParams` built by `resolve_session_params()` (`src/api/routers/research_params.py`) with per-field precedence inline > brief > default. After that point the pipeline reads **only** session columns (`graph_state.py`).

**Rule**: Editing or deleting a brief must never change a past session — so never add a `brief_service` / `brief_repo` call anywhere downstream of `start_session`. `brief_id` on the session and on `Provenance` is a pointer for provenance/UI only.

**Grep check**:
```bash
grep -rn "brief_service\|brief_repo\|BriefRepository" src/ | grep -v "api/routers/briefs.py\|api/routers/research\|services/briefs.py\|db/brief_repository.py\|api/main.py\|api/dependencies"
```
Any hit is a boundary violation.

---

## L-013: Two section-index spaces — outline (0-based H2) is the contract

**Issue** (found in AUTHOR-004): `section_markdown.split_sections` ALWAYS returns the prelude as index 0 (empty string when the body starts with `## `), so the first H2 is markdown index 1. Everything else — `ArticleOutline.sections[].index`, `SectionDraft.section_index`, `ImagePlacement.section_index`, the frontend `sectionIdx` / `makeSectionId` — is 0-based over H2 sections. Until AUTHOR-004 the `/content/*` routes passed `{id}:{sectionIdx}` straight into `split_sections`, so every edit / AI rewrite / history / restore addressed the section *before* the one the user clicked, and `validate_anchors._check_headings` compared a markdown index against spec indices in outline space.

**Rule**: the public `section_id` is `{article_id}:{outline_index}`. `src/services/content/section_history_contracts.md_index_for()` / `outline_index_for()` are the ONLY conversion; only `SectionHistoryService` (and the regenerate text helpers) call them, exactly where the body is read or replaced. `validate_anchors(section_index=…)` always receives the outline index. Never add `+1`/`-1` anywhere else (routers, services, frontend). On the frontend, derive indices only through `lib/articles/split-sections.ts` (`splitBySections` + `hasPreamble`) and `lib/articles/studio-sections.ts` — `page.tsx`'s old `segments.slice(1)` assumed a prelude and shifted Visual Studio's `section_index` by one for every no-prelude article.

**Grep check**:
```bash
grep -rn "md_index_for\|outline_index_for\|section_index + 1\|section_index - 1\|sectionIdx + 1\|segments.slice(1)" src/ frontend/src | grep -v "section_history\|section_regenerate_text\|split-sections\|studio-sections\|test"
```
Any hit outside those modules (other than comments) is a bug.

**Data already in the DB (pre-fix rows, no migration needed):** the frontend always sent outline-space ids, so `section_versions.section_id` / `section_index` are already correct and restore now lands on the intended H2. But rows with `source IN ('ai','tone_preset','humanize')` created before the fix through section-rewrite with `current_markdown=None` were generated from the PREVIOUS section's text, so restoring one writes section k-1's prose under section k's heading; and bodies saved pre-fix had `replace_section(md k)` overwrite section k-1 with section k's edit, so duplicated-H2 bodies may exist. Studio-inserted visuals on no-prelude articles carry `metadata.section_index` one too low (display-only drift). Audit once after deploy:
```sql
SELECT id, section_id, source, created_at FROM section_versions WHERE source <> 'manual' AND created_at < '<deploy-date>';
SELECT id FROM canonical_articles WHERE body_markdown ~ '(## [^\n]+)\n[\s\S]*\1\n';
SELECT id, jsonb_path_query(visuals, '$[*].metadata.section_index') FROM canonical_articles WHERE visuals::text LIKE '%"provider"%';
```

**Related, NOT fixed here:** `CanonicalArticle.provenance.research_session_id` is the TOPIC id (`graph_state.build_initial_state` sets `state["session_id"] = topic.id`; `seo_node` copies it into provenance). Never key a lookup on it — AUTHOR-004 resolves context through `ArticleDraftRepository.find_by_article_id` + `draft.session_id`. AUTHOR-001's `articles.find_by_session` (`src/api/routers/session_events.py`) depends on the current value, so the source fix is a separate ticket. Regression tests: `tests/unit/services/content/test_section_history.py`, `tests/unit/api/test_content_regenerate_endpoint.py` (round-trip with specs on k and k+1; 422 on both calls).

---

## L-014: Prompts are registry keys

**Issue** (AUTHOR-012): before the prompt registry, every LLM call site defined its own module-level constant (`_SYSTEM_PROMPT`, `_USER_TEMPLATE`, `_PROMPT_TEMPLATE`, …) and formatted it inline. That made an admin-editable prompt catalogue impossible without touching ~20 call sites, and gave every constant its own ad hoc variable contract.

**Rule**: never add a new module-level prompt constant. Register a `PromptTemplate` in the matching `src/agents/prompts/defaults_*.py` (`defaults_content.py` / `defaults_content_post.py` / `defaults_research.py` / `defaults_editing.py`) and call `render_prompt(key, **variables)` at the call site instead of `_CONST.format(...)`. Declare `variables` exactly — a parametrized test enforces that every registered template's placeholders match its declared variable set, so a mismatch fails CI, not production. Zero-variable templates (`variables=frozenset()`) are returned verbatim by `resolve_prompt()` — literal `{`/`}` in their text is fine; templates with variables go through `.format(**variables)`, so a literal brace in one of those must be escaped (`{{`/`}}`).

Overrides are **one snapshot per pipeline run / per request**, bound via `bind_prompt_overrides()` (a contextvar, same mechanism `TieredChatModel` uses for `current_step_name`). An admin edit through `PUT /api/v1/prompts/{key}` therefore applies to the *next* run — never retroactively, never mid-flight — so there is no need to guard against a prompt changing under a running pipeline.

**Grep check**:
```bash
grep -rn "_SYSTEM_PROMPT\|_USER_TEMPLATE\|_PROMPT_TEMPLATE" src/agents src/services | grep -v prompts/defaults
```
Expected hits: a small number of intentionally-kept aliases (e.g. `section_prompt.SYSTEM_PROMPT` referenced by existing tests) and the image-planner/prompt-composer catalogues, which are structured data (style tables, cliché lists), not text templates, and are deliberately out of the registry's scope. Any other hit is a bug — migrate it into a `defaults_*.py` module.

---

## L-015: Model fields are not columns

**Issue** (AUTHOR-011): `CanonicalArticle.audience_persona` was added to the Pydantic model but the article repository's `create()` / `_to_model()` never mapped a matching column. The field silently round-tripped to `None` on every read — three tickets (AUTHOR-002/003 era through AUTHOR-011) shipped code that set it on the model without anyone noticing it never reached the database, because nothing errored: Pydantic happily accepts and returns `None` for an unset optional field.

**Rule**: a new field on a Pydantic model that is meant to persist is not done until it has (1) a column on the table (`src/db/tables*.py`), (2) an explicit assignment in the repository's `create()` (and `update()` if the field is mutable), (3) an explicit read in `_to_model()`, and (4) a PG integration test that round-trips a **non-null** value through create → read and asserts it survives. A model field with no matching repository code is not "not yet wired" — it is a silent data-loss bug, because the ORM layer never raises on an unmapped Pydantic field.

**Grep check** (compare model field names against `_to_model` kwargs when adding a field):
```bash
python -c "import re,sys; m=open('src/models/content.py').read(); print(re.findall(r'^\s*(\w+):\s', m, re.M))"
grep -n "_to_model\|def create" src/db/repositories.py
```
Any model field not named in both the `create()` insert and the `_to_model()` return is unmapped — fix before merging, never "in a follow-up".
