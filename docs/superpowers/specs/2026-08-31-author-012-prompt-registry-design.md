# AUTHOR-012 — Prompt registry + global overrides + Settings Prompts tab

**Status:** approved design (2026-08-31) · **Epic 11 Phase C** · program plan §4.6, §5.11 · review §6 #13
**Story points:** 5

## 1. Problem

Every LLM prompt in Cognify is a private module-level string constant
(`_SYSTEM_PROMPT` / `_USER_TEMPLATE` / `_PROMPT_TEMPLATE`, ~20 sites)
formatted with `str.format` placeholders. Editing a prompt means a code
change and a redeploy, and there is no single place that says which prompts
exist or which variables each one may use. ImpactAI's editable prompt
registry is one of the three product ideas the August review flagged as
genuinely new; the plan's acceptance criterion is:

> Editing a prompt override changes the next run's prompt (visible in
> pipeline-debug); reset restores the default; templates with missing
> variables are rejected at save.

## 2. Decisions taken with the user

| Decision | Choice | Why |
|---|---|---|
| Override scope | **Global, admin-edited** (one override per key for the install; editors read-only) | No user table yet — only three seeded dev users. Matches how LLM/SEO settings work. A per-user tier can be layered on later. |
| Prompt scope (v1) | **Pipeline + research + editing prompts** (~16 keys) | The prompts editors touch most (AI rewrite, tone presets, topic analyzer) are included; the image planner / prompt composer are structured catalogues (style tables, cliché lists), not text templates — VISUAL-013 showed how easily an edit there silently degrades output. |
| Runtime resolution | **Contextvar-bound registry** (approach A) | Zero signature churn across ~20 sites, deterministic per run, identical in the Celery worker; same mechanism `TieredChatModel` already uses (`current_step_name`). |

Rejected: explicit `PromptSet` injection through every constructor (B — ~20
signatures + bootstrap + Celery builder for no behavioural gain); a DB read
inside each prompt builder (C — async I/O in pure modules, prompts can change
mid-run).

## 3. Registry — `src/agents/prompts/`

### 3.1 `registry.py`

```python
@dataclass(frozen=True)
class PromptTemplate:
    key: str            # "{step}.{role}", e.g. "content_outline.user"
    step: str           # grouping label for the UI, e.g. "content_outline"
    description: str    # one line, shown in Settings
    template: str       # the code default (moved verbatim from today's constant)
    variables: frozenset[str]  # exact set of allowed {placeholders}

DEFAULT_PROMPTS: Mapping[str, PromptTemplate]   # immutable, keyed by key
current_prompt_overrides: ContextVar[Mapping[str, str]]  # default: {}

def resolve_prompt(key: str) -> str        # override if bound+present else default; KeyError on unknown key
def render_prompt(key: str, **variables) -> str   # resolve_prompt(key).format(**variables)
@contextmanager
def bind_prompt_overrides(overrides: Mapping[str, str]) -> Iterator[None]
```

`resolve_prompt` logs `prompt_override_applied key=…` (info) when an override
is used. Unknown keys raise — a typo in a call site is a programming error,
never a silent default.

### 3.2 Keys (v1)

| Key | Source constant today | Variables |
|---|---|---|
| `content_outline.system` | `outline_generator._SYSTEM_PROMPT` | — |
| `content_outline.user` | `outline_generator._USER_TEMPLATE` | `title, description, domain, findings_summary, requirements, schema_hint` |
| `content_queries.system` / `.user` | `query_generator._SYSTEM_PROMPT` / `_USER_TEMPLATE` | — / `sections_text` |
| `content_draft.system` | `section_prompt.SYSTEM_PROMPT` (base only; audience/tone/angle/keyword lines stay code-appended) | `target_word_count` |
| `content_humanize.system` | `humanizer._REWRITE_SYSTEM` | — |
| `content_seo.system` / `.user` | `seo_optimizer._SEO_SYSTEM` / `_SEO_USER` | — / `title, body_excerpt` |
| `content_discover.system` / `.user` | `seo_optimizer._DISCOVER_SYSTEM` / `_DISCOVER_USER` | — / `sections_text, citations_text` |
| `content_charts.prompt` | `chart_generator._PROMPT_TEMPLATE` | `sections_text` |
| `content_diagrams.prompt` | `diagram_generator._PROMPT_TEMPLATE` | `sections_text` |
| `plan_research.system` / `.user` | `research/planner._SYSTEM_PROMPT` / `_USER_TEMPLATE` | — / `title, description, domain, context_block` |
| `evaluate_completeness.system` / `.user` | `research/evaluator._SYSTEM_PROMPT` / `_USER_TEMPLATE` | — / `title, domain, findings_summary` |
| `research_claims.system` / `.user` | `web_search._CLAIMS_*` and `literature_review._CLAIMS_*` (one shared pair; the two modules differ only in the variable name — normalised to `snippets`) | — / `title, snippets` |
| `section_rewrite.system` | `section_rewriter._REWRITER_SYSTEM` | — |
| `section_rewrite.tone.shorter` … `.more_authoritative` | `section_rewriter.TONE_PRESETS[…]` | — |
| `topic_analyze.system` / `.full` / `.regenerate` | `topic_analyzer._SYSTEM_PROMPT` / `_FULL_ANALYSIS_TEMPLATE` / `_REGENERATE_TEMPLATE` | — / `title, domains_section, valid_tones` / `field, title, current_json` |

`section_regenerate` reuses the `content_draft.*` keys and `seo_regenerate`
reuses `content_seo.*` — the code already shares those builders. Schema
hints (`_SCHEMA_HINT` and friends) and the banned-pattern block stay code and
are passed in as variables or appended — they are contracts with the JSON
parser, not editorial text.

Migrating a call site means replacing `_CONST.format(...)` with
`render_prompt("key", ...)` and deleting the constant. Behaviour is
byte-identical when no override exists (see tests §7).

### 3.3 `validation.py`

```python
def validate_template(template: str, spec: PromptTemplate) -> list[str]  # [] = valid
```

Rules (each yields a specific message):
- empty / whitespace-only → `"template is empty"`
- length > 20 000 chars → `"template exceeds 20000 characters"`
- placeholders parsed with `string.Formatter().parse` (so `{{`/`}}` escapes
  are respected); positional `{}` / `{0}` → `"positional placeholders are not allowed"`
- placeholder not in `spec.variables` → `"unknown variable {x}"` (would `KeyError` at run time)
- declared variable absent from the template → `"missing required variable {x}"` (a
  template that silently drops `{findings_summary}` is a broken prompt)
- format-spec/conversion suffixes (`{x:>10}`, `{x!r}`) → rejected; templates use plain names

## 4. Storage

`src/db/tables_prompt_overrides.py` (own module — `tables.py` is over the
200-line budget; imported from `tables.py` so `Base.metadata` is complete):

```
prompt_overrides
  id          uuid PK
  key         varchar(100) UNIQUE NOT NULL
  template    text NOT NULL
  updated_by  varchar(100) NOT NULL      # TokenPayload.sub of the admin
  created_at / updated_at                 # TimestampMixin
```

Alembic migration `alembic/versions/<rev>_add_prompt_overrides.py`
(hand-written id, explicit `down_revision` = current head, docstring names
AUTHOR-012). No history table — reset is a delete (YAGNI).

Repository protocol `PromptOverrideRepository` in
`src/db/prompt_override_repository.py`:

```python
async def load_all() -> dict[str, str]                 # key -> template
async def get(key) -> PromptOverride | None            # model: key, template, updated_by, updated_at
async def upsert(key, template, updated_by) -> PromptOverride
async def delete(key) -> bool
```

`PgPromptOverrideRepository` + `InMemoryPromptOverrideRepository` (used by
unit tests and the no-DB lifespan branch, so `/prompts` works without a
database — unlike the pre-existing `settings_repos` gap).

## 5. API — `src/api/routers/prompts.py`

| Route | Role | Body / result |
|---|---|---|
| `GET /api/v1/prompts` | editor+ | `{items: [PromptView]}` — every registered key |
| `GET /api/v1/prompts/{key}` | editor+ | `PromptView`; 404 unknown key |
| `PUT /api/v1/prompts/{key}` | admin | `{template}` → validated → upsert → `PromptView`; 422 `{violations: [...]}`; 404 unknown key |
| `DELETE /api/v1/prompts/{key}` | admin | reset → `PromptView` (now default); 404 if no override or unknown key |

`PromptView = {key, step, description, variables: [str], default_template,
template (effective), is_overridden, updated_by?, updated_at?}`. Rate limit
30/min; the route decorator is outermost (the AUTHOR-006 slowapi gotcha).
Repo exposed as `app.state.prompt_override_repo`, wired in both lifespan
branches and in `bootstrap.py` for the worker.

## 6. Runtime binding

- **Pipeline runs** (`src/services/pipeline_runner.py`): before invoking the
  research and content graphs — the full run, the outline-only run and the
  approve-and-resume run, in-process and Celery — `overrides = await
  repo.load_all()` then `with bind_prompt_overrides(overrides): …`. One
  snapshot per run: an edit mid-run does not change a running article; it
  applies to the next run.
- **Request-path LLM calls** — section rewrite / regenerate, SEO regenerate,
  humanize preview + stream, topic analyze — use one FastAPI dependency
  `bind_request_prompt_overrides` that loads and binds for the request scope.
- Failure mode: if the repo is unavailable the binder logs
  `prompt_overrides_unavailable` and binds `{}` (defaults) — an override
  store outage must never block generation.
- Observability: the rendered prompt already lands in
  `llm_calls.prompt_messages` (pipeline-debug); the `prompt_override_applied`
  log line links the two.

## 7. Frontend — Settings → Prompts

- `settings-nav.tsx` gains `{ key: "prompts", label: "Prompts", icon: FileText }`; `SettingsTab` union gains `"prompts"`.
- `lib/api/prompts.ts` (`listPrompts`, `updatePrompt`, `resetPrompt`), `hooks/use-prompts.ts` (React Query: list + two mutations invalidating `["prompts"]`, 422 violations surfaced as `Error.violations`).
- `components/settings/prompts-tab.tsx`: list grouped by `step`, each row = key, description, variable chips, **Overridden** badge (`bg-warning-light text-warning`), click selects.
- `components/settings/prompt-editor.tsx`: monospace textarea, variable chips, **Save** (admin; disabled until changed) / **Reset to default** (admin; only when overridden) / read-only notice for editors; 422 violations rendered as a red-bordered list (the `InlineProseEditor` anchor-violation pattern). Toasts via the shared `useToast`.
- Every new file ≤ 200 lines (`file-size-budget.test.ts` enforces it).

## 8. Testing

- `tests/unit/agents/prompts/test_registry.py`: every key in `DEFAULT_PROMPTS` renders with exactly its declared variables; `resolve_prompt` precedence (unbound → default, bound-missing → default, bound-present → override); `render_prompt` unknown key raises; nested `bind_prompt_overrides` restores.
- `test_validation.py`: each rule above, plus `{{ }}` escapes accepted, and a table-driven check that **every default template passes its own validation** (catches a mis-declared variable set).
- Migration tests per call site (`tests/unit/agents/content/…`, `tests/unit/agents/research/…`, `tests/unit/services/…`): the rendered prompt equals the pre-migration string for a fixed input (golden snapshot captured before the constant is removed), and a bound override changes it.
- Repo: `InMemory` unit tests + `tests/integration/db/test_pg_prompt_overrides.py` round-trip (upsert twice → one row, delete → gone).
- Router: list shape, 404 unknown key, 422 violations, 403 for editor PUT, 429 pinned, reset semantics.
- Frontend: `prompts-tab.test.tsx`, `prompt-editor.test.tsx`, `use-prompts.test.ts`, nav test updated.
- Live smoke (after rebuild): override `content_outline.user` with a marker sentence → generate → marker visible in `/pipeline-debug` for the `content_outline` call → reset → next run shows the default.

## 9. Non-goals

Per-user override tier · version history / audit of prompt edits · image
planner and image-prompt composer catalogues · persona prompts (AUTHOR-011
registers its own keys) · editing schema hints or the banned-pattern block ·
a prompt "playground" (run a prompt ad hoc).
