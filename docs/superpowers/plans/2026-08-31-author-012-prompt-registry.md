# AUTHOR-012 Prompt Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every pipeline/research/editing LLM prompt into a keyed registry with global, admin-edited DB overrides, validated at save and applied to the next run.

**Architecture:** `src/agents/prompts/registry.py` holds `PromptTemplate` defaults (moved verbatim from today's module constants) and a contextvar of overrides; call sites render via `render_prompt(key, **vars)`. Overrides live in one `prompt_overrides` table, are loaded once per pipeline run (`pipeline_runner`) or per request (a FastAPI dependency) and bound with `bind_prompt_overrides`. A `/prompts` router and a Settings → Prompts tab expose view / edit / reset.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async + Alembic, pydantic v2, pytest-asyncio; Next.js 15 / React 19 / TanStack Query / Vitest.

**Spec:** `docs/superpowers/specs/2026-08-31-author-012-prompt-registry-design.md` (amended by Task 12: two research-claims pairs, 18 keys).

## Global Constraints

- All functions < 20 lines, all files < 200 lines, max 3 params (use dataclasses / keyword-only bundles); named exports only; no `Any`.
- TDD: write the failing test, run it, implement, run again, commit. Backend tests run as `COGNIFY_ANTHROPIC_API_KEY= uv run pytest …` (a set key makes `create_app()` hang on Milvus at import).
- Every migrated prompt must render **byte-identical** output with no override bound — each migration task pins that with a golden test.
- Route decorator OUTERMOST, `@limiter.limit` innermost (slowapi never evaluates the limit otherwise).
- Frontend: Tailwind only, files ≤ 200 lines (`frontend/src/file-size-budget.test.ts` enforces), `useToast` from `components/ui/toaster`.
- Conventional commits; branch `feature/AUTHOR-012-prompt-registry` in worktree `.claude/worktrees/author-012-prompts`.
- Registry keys (18): `content_outline.system/.user`, `content_queries.system/.user`, `content_draft.system`, `content_humanize.system`, `content_seo.system/.user`, `content_discover.system/.user`, `content_charts.prompt`, `content_diagrams.prompt`, `plan_research.system/.user`, `evaluate_completeness.system/.user`, `research_web_claims.system/.user`, `research_literature_claims.system/.user`, `section_rewrite.system`, `section_rewrite.tone.shorter`, `section_rewrite.tone.more_concrete`, `section_rewrite.tone.more_conversational`, `section_rewrite.tone.more_authoritative`, `topic_analyze.system/.full/.regenerate`. (Counting each key: 27 individual keys across 18 step/role groups — the number that matters is "every constant in §3.2 of the spec".)

---

## File structure

| File | Responsibility |
|---|---|
| `src/agents/prompts/__init__.py` | re-exports |
| `src/agents/prompts/registry.py` | `PromptTemplate`, `DEFAULT_PROMPTS`, contextvar, `resolve_prompt`, `render_prompt`, `bind_prompt_overrides` |
| `src/agents/prompts/defaults_content.py` | content-pipeline default templates |
| `src/agents/prompts/defaults_research.py` | research default templates |
| `src/agents/prompts/defaults_editing.py` | rewrite / tone / topic-analyze default templates |
| `src/agents/prompts/validation.py` | `validate_template` |
| `src/models/prompt_override.py` | `PromptOverride` pydantic model |
| `src/db/tables_prompt_overrides.py` | `PromptOverrideRow` |
| `src/db/prompt_override_repository.py` | protocol + `PgPromptOverrideRepository` + `InMemoryPromptOverrideRepository` |
| `alembic/versions/e2a7c4d9b1f3_add_prompt_overrides.py` | migration |
| `src/api/schemas/prompts.py` | `PromptView`, `PromptListResponse`, `UpdatePromptRequest` |
| `src/api/routers/prompts.py` | `/prompts` endpoints |
| `src/api/prompt_scope.py` | `load_prompt_overrides` request dependency |
| `src/services/pipeline_runner.py` | per-run binding |
| `frontend/src/types/prompts.ts`, `lib/api/prompts.ts`, `hooks/use-prompts.ts`, `lib/auth/role.ts` | API + state |
| `frontend/src/components/settings/prompts-settings.tsx`, `prompts-tab.tsx`, `prompt-editor.tsx` | UI |

---

### Task 1: Registry core

**Files:**
- Create: `src/agents/prompts/__init__.py`, `src/agents/prompts/registry.py`
- Test: `tests/unit/agents/prompts/__init__.py` (empty), `tests/unit/agents/prompts/test_registry.py`

**Interfaces:**
- Produces: `PromptTemplate(key, step, description, template, variables: frozenset[str])`; `DEFAULT_PROMPTS: Mapping[str, PromptTemplate]` (filled by Tasks 3–5; Task 1 seeds it with one probe key that Task 3 replaces); `current_prompt_overrides: ContextVar[Mapping[str, str]]`; `resolve_prompt(key) -> str`; `render_prompt(key, **variables: object) -> str`; `bind_prompt_overrides(overrides) -> ContextManager[None]`; `register(*templates)` (module-internal helper used by the defaults modules).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/agents/prompts/test_registry.py
"""AUTHOR-012 — registry resolution + contextvar binding."""

from __future__ import annotations

import pytest

from src.agents.prompts.registry import (
    DEFAULT_PROMPTS,
    PromptTemplate,
    bind_prompt_overrides,
    current_prompt_overrides,
    render_prompt,
    resolve_prompt,
)


def _probe() -> PromptTemplate:
    return DEFAULT_PROMPTS["content_queries.user"]


class TestDefaults:
    def test_every_default_renders_with_its_declared_variables(self) -> None:
        for key, spec in DEFAULT_PROMPTS.items():
            rendered = render_prompt(key, **{v: f"<{v}>" for v in spec.variables})
            assert rendered, key
            for v in spec.variables:
                assert f"<{v}>" in rendered, (key, v)

    def test_key_matches_dict_key_and_step_prefix(self) -> None:
        for key, spec in DEFAULT_PROMPTS.items():
            assert spec.key == key
            assert key.startswith(spec.step + "."), key


class TestResolve:
    def test_unbound_returns_default(self) -> None:
        assert resolve_prompt(_probe().key) == _probe().template

    def test_bound_missing_key_returns_default(self) -> None:
        with bind_prompt_overrides({"other.key": "x"}):
            assert resolve_prompt(_probe().key) == _probe().template

    def test_bound_present_key_returns_override(self) -> None:
        with bind_prompt_overrides({_probe().key: "OVERRIDE {sections_text}"}):
            assert resolve_prompt(_probe().key) == "OVERRIDE {sections_text}"

    def test_unknown_key_raises(self) -> None:
        with pytest.raises(KeyError):
            resolve_prompt("nope.system")


class TestRender:
    def test_render_formats_variables(self) -> None:
        out = render_prompt("content_queries.user", sections_text="S1")
        assert "S1" in out
        assert "{sections_text}" not in out

    def test_zero_variable_template_returned_verbatim(self) -> None:
        # No .format() pass: literal braces (JSON examples) must survive.
        spec = DEFAULT_PROMPTS["content_queries.system"]
        assert spec.variables == frozenset()
        assert render_prompt(spec.key) == spec.template

    def test_override_is_rendered_too(self) -> None:
        with bind_prompt_overrides({"content_queries.user": "X {sections_text} Y"}):
            assert render_prompt("content_queries.user", sections_text="1") == "X 1 Y"


class TestBind:
    def test_nested_bind_restores_outer(self) -> None:
        with bind_prompt_overrides({"a": "1"}):
            with bind_prompt_overrides({"a": "2"}):
                assert current_prompt_overrides.get()["a"] == "2"
            assert current_prompt_overrides.get()["a"] == "1"
        assert current_prompt_overrides.get() == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/prompts/test_registry.py -q`
Expected: FAIL — `ModuleNotFoundError: src.agents.prompts`

- [ ] **Step 3: Implement**

```python
# src/agents/prompts/__init__.py
"""Prompt registry (AUTHOR-012). Import the defaults modules for their
side effect of registering templates."""

from src.agents.prompts import (  # noqa: F401 — registration side effects
    defaults_content,
    defaults_editing,
    defaults_research,
)
from src.agents.prompts.registry import (
    DEFAULT_PROMPTS,
    PromptTemplate,
    bind_prompt_overrides,
    current_prompt_overrides,
    render_prompt,
    resolve_prompt,
)

__all__ = [
    "DEFAULT_PROMPTS",
    "PromptTemplate",
    "bind_prompt_overrides",
    "current_prompt_overrides",
    "render_prompt",
    "resolve_prompt",
]
```

For Task 1 create the three defaults modules as stubs that register nothing except one probe in `defaults_content.py` (Task 3 replaces it):

```python
# src/agents/prompts/defaults_content.py  (Task 1 stub — Task 3 fills it)
"""Content-pipeline default prompts (AUTHOR-012)."""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="content_queries.system",
        step="content_queries",
        description="Retrieval-query generator: system role.",
        template="You are a research retrieval specialist. Respond with valid JSON only.",
        variables=frozenset(),
    ),
    PromptTemplate(
        key="content_queries.user",
        step="content_queries",
        description="Retrieval-query generator: sections to query for.",
        template="Generate retrieval queries for each section:\n\n{sections_text}",
        variables=frozenset({"sections_text"}),
    ),
)
```

```python
# src/agents/prompts/defaults_research.py  (Task 1 stub — Task 4 fills it)
"""Research default prompts (AUTHOR-012)."""
```

```python
# src/agents/prompts/defaults_editing.py  (Task 1 stub — Task 5 fills it)
"""Editing / topic-analysis default prompts (AUTHOR-012)."""
```

```python
# src/agents/prompts/registry.py
"""Prompt registry + override resolution (AUTHOR-012, program plan §4.6).

Defaults live in code (`defaults_*.py`, registered at import). Overrides
are a `{key: template}` mapping bound to a contextvar for the duration of
one pipeline run (`pipeline_runner`) or one request (`api/prompt_scope`).
Resolution is `override if bound and present, else default`; an unknown
key is a programming error and raises.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class PromptTemplate:
    """One registered prompt: its code default and the variables it may use."""

    key: str
    step: str
    description: str
    template: str
    variables: frozenset[str]


_REGISTRY: dict[str, PromptTemplate] = {}
DEFAULT_PROMPTS: Mapping[str, PromptTemplate] = MappingProxyType(_REGISTRY)

current_prompt_overrides: contextvars.ContextVar[Mapping[str, str]] = (
    contextvars.ContextVar("prompt_overrides", default=MappingProxyType({}))
)


def register(*templates: PromptTemplate) -> None:
    """Register defaults; called at import time by the defaults modules."""
    for spec in templates:
        if not spec.key.startswith(spec.step + "."):
            msg = f"prompt key {spec.key!r} must start with {spec.step!r}."
            raise ValueError(msg)
        _REGISTRY[spec.key] = spec


def resolve_prompt(key: str) -> str:
    """Effective template for `key`: bound override, else the code default."""
    spec = DEFAULT_PROMPTS[key]  # KeyError on unknown key — deliberate
    override = current_prompt_overrides.get().get(key)
    if override is None:
        return spec.template
    logger.info("prompt_override_applied", key=key)
    return override


def render_prompt(key: str, **variables: object) -> str:
    """Resolve and `.format()` `key`. Zero-variable templates are returned
    verbatim so literal braces (JSON examples) survive."""
    template = resolve_prompt(key)
    if not DEFAULT_PROMPTS[key].variables:
        return template
    return template.format(**variables)


@contextmanager
def bind_prompt_overrides(overrides: Mapping[str, str]) -> Iterator[None]:
    """Bind `overrides` for the enclosed block (nested binds restore)."""
    token = current_prompt_overrides.set(MappingProxyType(dict(overrides)))
    try:
        yield
    finally:
        current_prompt_overrides.reset(token)
```

- [ ] **Step 4: Run to verify it passes**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/prompts/test_registry.py -q`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/agents/prompts tests/unit/agents/prompts
git commit -m "feat(prompts): registry core — PromptTemplate, contextvar overrides, resolve/render/bind (AUTHOR-012)"
```

---

### Task 2: Template validation

**Files:**
- Create: `src/agents/prompts/validation.py`
- Test: `tests/unit/agents/prompts/test_validation.py`

**Interfaces:**
- Consumes: `PromptTemplate`, `DEFAULT_PROMPTS` (Task 1)
- Produces: `validate_template(template: str, spec: PromptTemplate) -> list[str]` (empty list = valid); `MAX_TEMPLATE_CHARS = 20_000`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/agents/prompts/test_validation.py
"""AUTHOR-012 — save-time template validation."""

from __future__ import annotations

import pytest

from src.agents.prompts.registry import DEFAULT_PROMPTS, PromptTemplate
from src.agents.prompts.validation import MAX_TEMPLATE_CHARS, validate_template


def _spec(variables: set[str]) -> PromptTemplate:
    return PromptTemplate(
        key="content_outline.user",
        step="content_outline",
        description="d",
        template="ignored",
        variables=frozenset(variables),
    )


class TestRules:
    def test_valid_template_returns_no_violations(self) -> None:
        assert validate_template("Title: {title}\nDomain: {domain}", _spec({"title", "domain"})) == []

    def test_empty_rejected(self) -> None:
        assert validate_template("   \n", _spec(set())) == ["template is empty"]

    def test_too_long_rejected(self) -> None:
        out = validate_template("x" * (MAX_TEMPLATE_CHARS + 1), _spec(set()))
        assert out == [f"template exceeds {MAX_TEMPLATE_CHARS} characters"]

    def test_unknown_variable_rejected(self) -> None:
        assert validate_template("{title} {bogus}", _spec({"title"})) == [
            "unknown variable {bogus}"
        ]

    def test_missing_required_variable_rejected(self) -> None:
        assert validate_template("only {title}", _spec({"title", "domain"})) == [
            "missing required variable {domain}"
        ]

    def test_positional_placeholder_rejected(self) -> None:
        assert "positional placeholders are not allowed" in validate_template(
            "{} and {0} {title}", _spec({"title"})
        )

    def test_format_spec_rejected(self) -> None:
        assert validate_template("{title:>10}", _spec({"title"})) == [
            "format specs and conversions are not allowed ({title:>10})"
        ]

    def test_escaped_braces_accepted(self) -> None:
        assert validate_template('Return {{"a": 1}} for {title}', _spec({"title"})) == []

    def test_zero_variable_template_allows_literal_braces(self) -> None:
        # Zero-variable templates are never .format()ed (registry contract).
        assert validate_template('Respond {"title": "x"}', _spec(set())) == []

    def test_unbalanced_brace_in_variable_template_rejected(self) -> None:
        out = validate_template("{title", _spec({"title"}))
        assert out and out[0].startswith("invalid template syntax")


class TestDefaultsSelfValidate:
    @pytest.mark.parametrize("key", sorted(DEFAULT_PROMPTS))
    def test_every_default_passes_its_own_validation(self, key: str) -> None:
        spec = DEFAULT_PROMPTS[key]
        assert validate_template(spec.template, spec) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/prompts/test_validation.py -q`
Expected: FAIL — `ModuleNotFoundError: src.agents.prompts.validation`

- [ ] **Step 3: Implement**

```python
# src/agents/prompts/validation.py
"""Save-time validation for prompt overrides (AUTHOR-012, spec §3.3)."""

from __future__ import annotations

from string import Formatter

from src.agents.prompts.registry import PromptTemplate

MAX_TEMPLATE_CHARS = 20_000


def validate_template(template: str, spec: PromptTemplate) -> list[str]:
    """Return every rule the template breaks (empty list = valid)."""
    if not template.strip():
        return ["template is empty"]
    if len(template) > MAX_TEMPLATE_CHARS:
        return [f"template exceeds {MAX_TEMPLATE_CHARS} characters"]
    if not spec.variables:
        # Zero-variable templates are returned verbatim by the registry —
        # literal braces are fine and there is nothing to check.
        return []
    try:
        fields = list(Formatter().parse(template))
    except ValueError as exc:
        return [f"invalid template syntax: {exc}"]
    return _placeholder_violations(fields, spec)


def _placeholder_violations(
    fields: list[tuple[str, str | None, str | None, str | None]],
    spec: PromptTemplate,
) -> list[str]:
    violations: list[str] = []
    seen: set[str] = set()
    for _literal, name, fmt, conversion in fields:
        if name is None:
            continue
        if name == "" or name.isdigit():
            violations.append("positional placeholders are not allowed")
            continue
        if fmt or conversion:
            rendered = "{" + name + (f"!{conversion}" if conversion else "") + (f":{fmt}" if fmt else "") + "}"
            violations.append(f"format specs and conversions are not allowed ({rendered})")
            continue
        seen.add(name)
        if name not in spec.variables:
            violations.append(f"unknown variable {{{name}}}")
    for missing in sorted(spec.variables - seen):
        violations.append(f"missing required variable {{{missing}}}")
    return violations
```

(`_placeholder_violations` is 19 lines; keep it that way — split the format-spec line into a helper if you add anything.)

- [ ] **Step 4: Run to verify it passes**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/prompts -q`
Expected: all pass (the parametrized self-validation runs once per registered key)

- [ ] **Step 5: Commit**

```bash
git add src/agents/prompts/validation.py tests/unit/agents/prompts/test_validation.py
git commit -m "feat(prompts): save-time template validation (AUTHOR-012)"
```

---

### Task 3: Migrate the content-pipeline prompts

**Files:**
- Modify: `src/agents/prompts/defaults_content.py` (replace the Task 1 stub)
- Modify: `src/agents/content/outline_generator.py:48-69,142-149`, `query_generator.py:18-30,48-54`, `section_prompt.py:24-40`, `section_drafter.py:14,28`, `humanizer.py:33-42,148-151`, `seo_optimizer.py:32-59,149-158,184-192`, `chart_generator.py:31-46,57`, `diagram_generator.py:35-63,170`
- Test: `tests/unit/agents/content/test_prompt_registry_migration.py`

**Interfaces:**
- Consumes: `register`, `render_prompt`, `DEFAULT_PROMPTS` (Task 1)
- Produces: keys `content_outline.system/.user`, `content_queries.system/.user`, `content_draft.system`, `content_humanize.system`, `content_seo.system/.user`, `content_discover.system/.user`, `content_charts.prompt`, `content_diagrams.prompt`. Module constants `outline_generator._SYSTEM_PROMPT`, `section_prompt.SYSTEM_PROMPT`, `section_drafter._SYSTEM_PROMPT` remain importable (aliases of the registry default) because `tests/unit/agents/content/test_prompt_updates.py` and `test_section_prompt.py` import them.

- [ ] **Step 1: Capture the goldens BEFORE touching the constants — write the failing test**

The test renders each prompt through the registry and compares against the literal strings that exist today. Copy each expected string verbatim from the source lines listed above (they are the current constants — do not retype from memory; use the file).

```python
# tests/unit/agents/content/test_prompt_registry_migration.py
"""AUTHOR-012 — content-pipeline prompts render byte-identically via the registry."""

from __future__ import annotations

from src.agents.content import (
    chart_generator,
    diagram_generator,
    outline_generator,
    query_generator,
    section_prompt,
    seo_optimizer,
)
from src.agents.prompts import DEFAULT_PROMPTS, bind_prompt_overrides, render_prompt


class TestGoldens:
    def test_outline_system_is_registry_default(self) -> None:
        assert outline_generator._SYSTEM_PROMPT == DEFAULT_PROMPTS["content_outline.system"].template
        assert "Respond with valid JSON only." in outline_generator._SYSTEM_PROMPT

    def test_outline_user_renders_all_slots(self) -> None:
        out = render_prompt(
            "content_outline.user",
            title="T", description="D", domain="X",
            findings_summary="F", requirements="R", schema_hint="S",
        )
        assert out == (
            "Generate an article outline for this topic:\n\n"
            "Title: T\nDescription: D\nDomain: X\n\n"
            "Research findings:\nF\n\nR\nReturn JSON: S"
        )

    def test_queries_user_matches_legacy_literal(self) -> None:
        out = render_prompt("content_queries.user", sections_text="SEC")
        assert out == (
            "Generate retrieval queries for each section:\n\nSEC\n\n"
            'Return JSON array: [{"section_index": 0, "queries": ["query1", "query2"]}]'
        )

    def test_draft_system_keeps_word_target_slot(self) -> None:
        assert section_prompt.SYSTEM_PROMPT == DEFAULT_PROMPTS["content_draft.system"].template
        assert "approximately 300 words" in render_prompt("content_draft.system", target_word_count=300)

    def test_seo_user_matches_legacy_literal(self) -> None:
        out = render_prompt("content_seo.user", title="T", body_excerpt="B")
        assert out == (
            "Generate SEO metadata for this article:\n\nTitle: T\nBody (excerpt): B\n\n"
            "Requirements: title 50-60 chars, description 150-160 chars, "
            "5-10 keywords. Return JSON only."
        )

    def test_seo_system_keeps_literal_json_braces(self) -> None:
        out = render_prompt("content_seo.system")
        assert '{"title": "50-60 char", "description": "150-160 char", ' in out

    def test_discover_user_matches_legacy_literal(self) -> None:
        out = render_prompt("content_discover.user", sections_text="S", citations_text="C")
        assert out == (
            "Extract summary and key claims from this article:\n\nS\n\n"
            "Citations available: C\nReturn JSON only."
        )

    def test_charts_and_diagrams_prompts_end_with_sections(self) -> None:
        assert render_prompt("content_charts.prompt", sections_text="SS").endswith("## Article Sections\nSS")
        assert render_prompt("content_diagrams.prompt", sections_text="SS").endswith("## Article Sections\nSS")
        assert "propose 0-3 data charts" in DEFAULT_PROMPTS["content_charts.prompt"].template
        assert "Do not exceed 5 total." in DEFAULT_PROMPTS["content_diagrams.prompt"].template

    def test_humanize_system_registered(self) -> None:
        assert "<<<BLOCK>>>" in DEFAULT_PROMPTS["content_humanize.system"].template


class TestOverridesReachCallSites:
    def test_query_generator_uses_override(self) -> None:
        # The module must call the registry at call time, not cache at import.
        from src.models.content_pipeline import ArticleOutline, OutlineSection

        outline = ArticleOutline(
            title="t", subtitle="s", content_type="article",
            sections=[OutlineSection(index=0, title="A", description="d", key_points=["k"], target_word_count=100, relevant_facets=[0])],
            total_target_words=100, reasoning="r",
        )
        with bind_prompt_overrides({"content_queries.user": "OVR {sections_text}"}):
            msg = query_generator._build_user_message(outline)
        assert msg.startswith("OVR Section 0: A")

    def test_chart_prompt_uses_override(self) -> None:
        with bind_prompt_overrides({"content_charts.prompt": "C {sections_text}"}):
            assert chart_generator._build_prompt([]) == "C "

    def test_diagram_prompt_uses_override(self) -> None:
        with bind_prompt_overrides({"content_diagrams.prompt": "D {sections_text}"}):
            assert diagram_generator._build_prompt([]) == "D "

    def test_seo_messages_use_override(self) -> None:
        with bind_prompt_overrides({"content_seo.system": "SYS-OVR"}):
            messages = seo_optimizer._seo_messages("T", "B", "")
        assert messages[0].content == "SYS-OVR"
```

If `ArticleOutline` / `OutlineSection` field names differ from the above, read `src/models/content_pipeline.py` and adjust the fixture — the assertion is on the rendered prefix only.

- [ ] **Step 2: Run to verify it fails**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/content/test_prompt_registry_migration.py -q`
Expected: FAIL — `KeyError: 'content_outline.system'` (only the Task 1 probe keys exist) and `AttributeError: _build_user_message`

- [ ] **Step 3: Register the defaults (`defaults_content.py`)**

Replace the Task 1 stub. For each entry, the `template` literal is the **exact** current constant copied from the source file (the Task 1 probe text for `content_queries.*` is replaced by the real literals from `query_generator.py:18-30`):

```python
# src/agents/prompts/defaults_content.py
"""Content-pipeline default prompts (AUTHOR-012). Each `template` is the
literal that lived in the generator module before the registry existed."""

from src.agents.prompts.registry import PromptTemplate, register

register(
    PromptTemplate(
        key="content_outline.system", step="content_outline",
        description="Outline generator: content-strategist system role + style rules.",
        template=(  # verbatim from outline_generator._SYSTEM_PROMPT
            "You are an expert content strategist. Generate a structured "
            "article outline from research findings. The outline should have "
            "sections with narrative flow: introduction, findings, "
            "analysis, and conclusion. Follow the section count and word "
            "budgets given in the requirements. "
            "Do not use em-dashes. Use periods or commas instead. "
            "Avoid formal transitions like moreover, furthermore, in conclusion. "
            "Write in a natural conversational tone. Vary sentence length. "
            "Be specific and concrete, not abstract. "
            "Respond with valid JSON only."
        ),
        variables=frozenset(),
    ),
    PromptTemplate(
        key="content_outline.user", step="content_outline",
        description="Outline generator: topic, findings, sizing requirements, schema.",
        template=(  # verbatim from outline_generator._USER_TEMPLATE
            "Generate an article outline for this topic:\n\n"
            "Title: {title}\n"
            "Description: {description}\n"
            "Domain: {domain}\n\n"
            "Research findings:\n{findings_summary}\n\n"
            "{requirements}\n"
            "Return JSON: {schema_hint}"
        ),
        variables=frozenset({"title", "description", "domain", "findings_summary", "requirements", "schema_hint"}),
    ),
    PromptTemplate(
        key="content_queries.system", step="content_queries",
        description="Retrieval-query generator: system role.",
        template=<verbatim query_generator._SYSTEM_PROMPT>, variables=frozenset(),
    ),
    PromptTemplate(
        key="content_queries.user", step="content_queries",
        description="Retrieval-query generator: sections + JSON shape.",
        template=<verbatim query_generator._USER_TEMPLATE>, variables=frozenset({"sections_text"}),
    ),
    PromptTemplate(
        key="content_draft.system", step="content_draft",
        description="Section drafter: base system prompt (audience/tone lines are appended in code).",
        template=<verbatim section_prompt.SYSTEM_PROMPT>, variables=frozenset({"target_word_count"}),
    ),
    PromptTemplate(
        key="content_humanize.system", step="content_humanize",
        description="Humanizer rewrite pass: system role (sentinel contract).",
        template=<verbatim humanizer._REWRITE_SYSTEM>, variables=frozenset(),
    ),
    PromptTemplate(
        key="content_seo.system", step="content_seo",
        description="SEO metadata: system role + JSON shape.",
        template=<verbatim seo_optimizer._SEO_SYSTEM>, variables=frozenset(),
    ),
    PromptTemplate(
        key="content_seo.user", step="content_seo",
        description="SEO metadata: title + body excerpt.",
        template=<verbatim seo_optimizer._SEO_USER>, variables=frozenset({"title", "body_excerpt"}),
    ),
    PromptTemplate(
        key="content_discover.system", step="content_discover",
        description="AI discoverability: summary + key claims system role.",
        template=<verbatim seo_optimizer._DISCOVER_SYSTEM>, variables=frozenset(),
    ),
    PromptTemplate(
        key="content_discover.user", step="content_discover",
        description="AI discoverability: sections + citations.",
        template=<verbatim seo_optimizer._DISCOVER_USER>, variables=frozenset({"sections_text", "citations_text"}),
    ),
    PromptTemplate(
        key="content_charts.prompt", step="content_charts",
        description="Chart proposals from section drafts (single-turn prompt).",
        template=<verbatim chart_generator._PROMPT_TEMPLATE>, variables=frozenset({"sections_text"}),
    ),
    PromptTemplate(
        key="content_diagrams.prompt", step="content_diagrams",
        description="Diagram proposals from section drafts (single-turn prompt).",
        template=<verbatim diagram_generator._PROMPT_TEMPLATE>, variables=frozenset({"sections_text"}),
    ),
)
```

`<verbatim X>` means: open the source file and paste the exact parenthesised string literal — including the `{{`/`}}` escapes in `content_queries.user`. If `defaults_content.py` exceeds 200 lines, move the four `content_seo.*`/`content_discover.*` entries plus charts/diagrams into `defaults_content_post.py` and import it from `src/agents/prompts/__init__.py` the same way.

- [ ] **Step 4: Switch each call site to the registry**

`outline_generator.py`:
```python
from src.agents.prompts import DEFAULT_PROMPTS, render_prompt
# keep the name for tests/unit/agents/content/test_prompt_updates.py:
_SYSTEM_PROMPT = DEFAULT_PROMPTS["content_outline.system"].template
# delete the _USER_TEMPLATE constant; in generate_outline():
    user_msg = render_prompt(
        "content_outline.user",
        title=topic.title, description=topic.description, domain=topic.domain,
        findings_summary=_summarize_findings(findings),
        requirements=_requirements_block(ctx), schema_hint=_SCHEMA_HINT,
    )
    # and the SystemMessage:
    SystemMessage(content=render_prompt("content_outline.system"))
```
(Whatever `generate_outline` currently does with `_SYSTEM_PROMPT` after line 149 — it builds a `SystemMessage(content=_SYSTEM_PROMPT)` — change that one occurrence to `render_prompt("content_outline.system")`. Keep `_SCHEMA_HINT` as code.)

`query_generator.py`: delete both constants; add
```python
def _build_user_message(outline: ArticleOutline) -> str:
    return render_prompt("content_queries.user", sections_text=_format_sections(outline))
```
and in `generate_section_queries` use `SystemMessage(content=render_prompt("content_queries.system"))`, `HumanMessage(content=_build_user_message(outline))`.

`section_prompt.py`: `SYSTEM_PROMPT = DEFAULT_PROMPTS["content_draft.system"].template` (keeps the exported name); `build_system_prompt` line 40 becomes `system = render_prompt("content_draft.system", target_word_count=section.target_word_count)`. `section_drafter.py:28` stays `_SYSTEM_PROMPT = SYSTEM_PROMPT`.

`humanizer.py`: delete `_REWRITE_SYSTEM`; line 149 → `SystemMessage(content=render_prompt("content_humanize.system"))`. Grep the repo for other `_REWRITE_SYSTEM` users (`src/services/content/humanize_*`) and switch them the same way.

`seo_optimizer.py`: delete the four constants; add
```python
def _seo_messages(title: str, body_text: str, extras: str) -> list[SystemMessage | HumanMessage]:
    return [
        SystemMessage(content=render_prompt("content_seo.system")),
        HumanMessage(
            content=render_prompt("content_seo.user", title=title, body_excerpt=body_text[:2000]) + extras
        ),
    ]
```
and use it in `generate_seo_metadata` (replacing lines 149-158); in `generate_ai_discoverability` use `render_prompt("content_discover.system")` / `render_prompt("content_discover.user", sections_text=…, citations_text=…)`.

`chart_generator.py` / `diagram_generator.py`: delete `_PROMPT_TEMPLATE`; add
```python
def _build_prompt(section_drafts: list[SectionDraft]) -> str:
    sections_text = "\n\n".join(f"### {d.title}\n{d.body_markdown}" for d in section_drafts)
    return render_prompt("content_charts.prompt", sections_text=sections_text)   # "content_diagrams.prompt" in diagram_generator
```
and call it from `propose_charts` / `propose_diagrams`. Leave `_SPEC_MERMAID_TEMPLATE` untouched (image-planner path, out of scope).

- [ ] **Step 5: Run the migration test + every existing content test**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/content tests/unit/agents/prompts tests/unit/services/content -q`
Expected: all pass, including `test_prompt_updates.py` and `test_section_prompt.py` unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/agents/prompts/defaults_content.py src/agents/content tests/unit/agents/content/test_prompt_registry_migration.py
git commit -m "refactor(prompts): content-pipeline prompts read from the registry (AUTHOR-012)"
```

---

### Task 4: Migrate the research prompts

**Files:**
- Modify: `src/agents/prompts/defaults_research.py`, `src/agents/research/planner.py:19-40,65-71`, `evaluator.py:26-38,90-95`, `web_search.py:25-34,126-130`, `literature_review.py:28-39,131-135`
- Test: `tests/unit/agents/research/test_prompt_registry_migration.py`

**Interfaces:**
- Produces: keys `plan_research.system/.user` (user vars `title, description, domain, context_block`), `evaluate_completeness.system/.user` (`title, domain, findings_summary`), `research_web_claims.system/.user` (`title, snippets`), `research_literature_claims.system/.user` (`title, abstracts`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agents/research/test_prompt_registry_migration.py
"""AUTHOR-012 — research prompts render byte-identically via the registry."""

from __future__ import annotations

from src.agents.prompts import DEFAULT_PROMPTS, bind_prompt_overrides, render_prompt


class TestGoldens:
    def test_plan_user_matches_legacy_literal(self) -> None:
        out = render_prompt("plan_research.user", title="T", description="D", domain="X", context_block="CB")
        assert out.startswith("Plan research for this topic:\nTitle: T\nDescription: D\nDomain: X\nCB\n")
        assert out.endswith('"source_type": "web|academic|both"}], "reasoning": "..."}')

    def test_evaluate_user_matches_legacy_literal(self) -> None:
        out = render_prompt("evaluate_completeness.user", title="T", domain="X", findings_summary="F")
        assert out == (
            "Topic: T (X)\n\nFindings per facet:\nF\n\n"
            "Are these findings sufficient? Identify weak facets by index.\n"
            'Return JSON: {"is_complete": bool, "weak_facets": [int], "reasoning": "..."}'
        )

    def test_web_claims_user_matches_legacy_literal(self) -> None:
        out = render_prompt("research_web_claims.user", title="T", snippets="S")
        assert out == (
            "Search results about 'T':\n\nS\n\n"
            "Extract 3-5 key factual claims and a 2-3 sentence summary.\n"
            'Return JSON: {"claims": ["..."], "summary": "..."}'
        )

    def test_literature_claims_user_matches_legacy_literal(self) -> None:
        out = render_prompt("research_literature_claims.user", title="T", abstracts="A")
        assert out == (
            "Paper abstracts about 'T':\n\nA\n\n"
            "Extract 3-5 key factual claims (cite as Author et al. (year)) "
            "and a 2-3 sentence summary of research contributions.\n"
            'Return JSON: {"claims": ["..."], "summary": "..."}'
        )

    def test_systems_registered(self) -> None:
        assert "research planning assistant" in DEFAULT_PROMPTS["plan_research.system"].template
        assert "completeness evaluator" in DEFAULT_PROMPTS["evaluate_completeness.system"].template
        assert "search results" in DEFAULT_PROMPTS["research_web_claims.system"].template
        assert "paper abstracts" in DEFAULT_PROMPTS["research_literature_claims.system"].template


class TestOverrideReachesPlanner:
    def test_planner_user_message_uses_override(self) -> None:
        from uuid import uuid4

        from src.agents.research.planner import _build_user_message
        from src.models.research import TopicInput

        topic = TopicInput(id=uuid4(), title="T", description="D", domain="X")
        with bind_prompt_overrides({"plan_research.user": "OVR {title}"}):
            assert _build_user_message(topic) == "OVR T"
```

- [ ] **Step 2: Run to verify it fails**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/research/test_prompt_registry_migration.py -q`
Expected: FAIL — `KeyError: 'plan_research.user'`

- [ ] **Step 3: Register + migrate**

`defaults_research.py`: eight `PromptTemplate` entries, `template=<verbatim>` from the lines listed under **Files** (same `register(...)` shape as Task 3; steps `plan_research`, `evaluate_completeness`, `research_web_claims`, `research_literature_claims`; descriptions: "Research planner: system role / topic + context", "Completeness evaluator: system role / findings per facet", "Web-search claim extraction: system role / search snippets", "Literature-review claim extraction: system role / paper abstracts").

`planner.py`: delete both constants; add
```python
def _build_user_message(topic: TopicInput) -> str:
    return render_prompt(
        "plan_research.user",
        title=topic.title, description=topic.description, domain=topic.domain,
        context_block=_build_context_block(topic),
    )
```
and `messages = [SystemMessage(content=render_prompt("plan_research.system")), HumanMessage(content=_build_user_message(topic))]`.

`evaluator.py`: `user_msg = render_prompt("evaluate_completeness.user", title=…, domain=…, findings_summary=…)`; system via `render_prompt("evaluate_completeness.system")`.

`web_search.py:126-128`: `msg = render_prompt("research_web_claims.user", title=_sanitize(title), snippets=snippets)`; `SystemMessage(content=render_prompt("research_web_claims.system"))`. `literature_review.py:131-133`: same with `research_literature_claims.*` and `abstracts=abstracts`. Delete the four `_CLAIMS_*` constants.

- [ ] **Step 4: Run**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/agents/prompts/defaults_research.py src/agents/research tests/unit/agents/research/test_prompt_registry_migration.py
git commit -m "refactor(prompts): research prompts read from the registry (AUTHOR-012)"
```

---

### Task 5: Migrate the editing prompts (rewrite, tone presets, topic analyzer)

**Files:**
- Modify: `src/agents/prompts/defaults_editing.py`, `src/services/content/section_rewriter.py:50-72,89-97,114-120,148-151,171`, `src/services/topic_analyzer.py:19-43,85-88,114-129`
- Test: `tests/unit/services/test_prompt_registry_editing.py`

**Interfaces:**
- Produces: keys `section_rewrite.system`, `section_rewrite.tone.{shorter,more_concrete,more_conversational,more_authoritative}`, `topic_analyze.system`, `topic_analyze.full` (`title, domains_section, valid_tones`), `topic_analyze.regenerate` (`field, title, current_json`).
- `TONE_PRESETS` stays exported from `section_rewriter` as `dict[TonePreset, str]` of the registry **defaults** (tests import it); `expand_tone_preset(preset)` now resolves through the registry at call time.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/services/test_prompt_registry_editing.py
"""AUTHOR-012 — editing prompts (rewrite / tone presets / topic analyzer)."""

from __future__ import annotations

from src.agents.prompts import DEFAULT_PROMPTS, bind_prompt_overrides, render_prompt
from src.services.content.section_rewriter import TONE_PRESETS, expand_tone_preset
from src.services.topic_analyzer import TopicAnalyzer


class TestTonePresets:
    def test_presets_are_registry_defaults(self) -> None:
        for name, text in TONE_PRESETS.items():
            assert DEFAULT_PROMPTS[f"section_rewrite.tone.{name}"].template == text

    def test_expand_uses_override(self) -> None:
        with bind_prompt_overrides({"section_rewrite.tone.shorter": "Cut it."}):
            assert expand_tone_preset("shorter") == "Cut it."
        assert expand_tone_preset("shorter").startswith("Make this paragraph noticeably shorter")


class TestRewriterSystem:
    def test_registered_and_mentions_data_spec_id(self) -> None:
        assert "data-spec-id" in render_prompt("section_rewrite.system")


class TestTopicAnalyzer:
    def test_full_prompt_matches_legacy_literal(self) -> None:
        analyzer = TopicAnalyzer(llm=object())  # type: ignore[arg-type]
        out = analyzer._build_prompt("T", ["ai"], None, None)
        assert out.startswith("Analyze this topic and suggest article metadata:\n\nTitle: T\n\nAvailable domains: ['ai']\n")
        assert '- "preferred_angle": suggested editorial angle' in out

    def test_regenerate_prompt_uses_override(self) -> None:
        from src.api.schemas.topic_analysis import TopicAnalysisResult

        current = TopicAnalysisResult(description="d", domain="x", keywords=[], target_audience="a", content_tone="neutral", preferred_angle="p")
        analyzer = TopicAnalyzer(llm=object())  # type: ignore[arg-type]
        with bind_prompt_overrides({"topic_analyze.regenerate": "R {field} {title} {current_json}"}):
            out = analyzer._build_prompt("T", None, "domain", current)
        assert out.startswith("R domain T {")
```

If `TopicAnalysisResult` requires other fields, read `src/api/schemas/topic_analysis.py` and fill them — the assertion is only on the prefix.

- [ ] **Step 2: Run to verify it fails**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/test_prompt_registry_editing.py -q`
Expected: FAIL — `KeyError: 'section_rewrite.tone.shorter'`

- [ ] **Step 3: Register + migrate**

`defaults_editing.py`: register `section_rewrite.system` (verbatim `_REWRITER_SYSTEM`, no variables), the four `section_rewrite.tone.<name>` keys (verbatim `TONE_PRESETS[<name>]`, no variables, description "Tone preset: <name>"), `topic_analyze.system` (verbatim `_SYSTEM_PROMPT`), `topic_analyze.full` (verbatim `_FULL_ANALYSIS_TEMPLATE`, vars `title, domains_section, valid_tones`), `topic_analyze.regenerate` (verbatim `_REGENERATE_TEMPLATE`, vars `field, title, current_json`).

`section_rewriter.py`:
```python
TONE_PRESETS: dict[TonePreset, str] = {
    name: DEFAULT_PROMPTS[f"section_rewrite.tone.{name}"].template
    for name in ("shorter", "more_concrete", "more_conversational", "more_authoritative")
}

def expand_tone_preset(preset: TonePreset) -> str:
    """Server-side instruction for a tone preset (registry-resolved)."""
    return render_prompt(f"section_rewrite.tone.{preset}")
```
Delete the literal dict and `_REWRITER_SYSTEM`; line 149 → `SystemMessage(content=render_prompt("section_rewrite.system"))`; line 171 `prompt_used=render_prompt("section_rewrite.system")`. Keep `_BANNED_PATTERNS_BLOCK` as code (spec §3.2).

`topic_analyzer.py`: delete the three constants; `_build_prompt` uses `render_prompt("topic_analyze.regenerate", field=…, title=…, current_json=…)` and `render_prompt("topic_analyze.full", title=…, domains_section=…, valid_tones=VALID_TONES)`; `analyze()` uses `SystemMessage(content=render_prompt("topic_analyze.system"))`.

- [ ] **Step 4: Run**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services tests/unit/api/test_content_endpoints.py tests/unit/api/test_topics_endpoints.py -q` (use whatever the existing content/topic endpoint test files are named — `ls tests/unit/api | grep -E "content|topic"`)
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/agents/prompts/defaults_editing.py src/services/content/section_rewriter.py src/services/topic_analyzer.py tests/unit/services/test_prompt_registry_editing.py
git commit -m "refactor(prompts): rewrite, tone presets and topic analyzer read from the registry (AUTHOR-012)"
```

---

### Task 6: `prompt_overrides` table, migration, repositories

**Files:**
- Create: `src/models/prompt_override.py`, `src/db/tables_prompt_overrides.py`, `src/db/prompt_override_repository.py`, `alembic/versions/e2a7c4d9b1f3_add_prompt_overrides.py`
- Modify: `src/db/tables.py:22-24` (import the new row module next to `BriefRow`)
- Test: `tests/unit/db/test_prompt_override_repository.py`, `tests/integration/db/test_pg_prompt_overrides.py`

**Interfaces:**
- Produces: `PromptOverride(key: str, template: str, updated_by: str, updated_at: datetime)`; `PromptOverrideRepository` Protocol with `load_all() -> dict[str, str]`, `get(key) -> PromptOverride | None`, `upsert(key, template, updated_by) -> PromptOverride` (keyword-only after `key`), `delete(key) -> bool`; `PgPromptOverrideRepository(sf)`, `InMemoryPromptOverrideRepository()`.

- [ ] **Step 1: Write the failing unit test (in-memory repo — the Pg repo shares the contract)**

```python
# tests/unit/db/test_prompt_override_repository.py
"""AUTHOR-012 — override repository contract (in-memory twin)."""

from __future__ import annotations

import pytest

from src.db.prompt_override_repository import InMemoryPromptOverrideRepository


@pytest.mark.asyncio
class TestInMemoryPromptOverrideRepository:
    async def test_upsert_then_load_all(self) -> None:
        repo = InMemoryPromptOverrideRepository()
        saved = await repo.upsert("content_outline.user", template="T1", updated_by="user-1")
        assert saved.key == "content_outline.user" and saved.template == "T1"
        assert saved.updated_by == "user-1" and saved.updated_at is not None
        assert await repo.load_all() == {"content_outline.user": "T1"}

    async def test_upsert_twice_keeps_one_row(self) -> None:
        repo = InMemoryPromptOverrideRepository()
        await repo.upsert("k.system", template="A", updated_by="u")
        await repo.upsert("k.system", template="B", updated_by="u2")
        assert await repo.load_all() == {"k.system": "B"}
        got = await repo.get("k.system")
        assert got is not None and got.updated_by == "u2"

    async def test_delete_returns_false_when_absent(self) -> None:
        repo = InMemoryPromptOverrideRepository()
        assert await repo.delete("k.system") is False
        await repo.upsert("k.system", template="A", updated_by="u")
        assert await repo.delete("k.system") is True
        assert await repo.get("k.system") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/db/test_prompt_override_repository.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement model, table, repos, migration**

```python
# src/models/prompt_override.py
"""Persisted prompt override (AUTHOR-012)."""

from datetime import datetime

from pydantic import BaseModel, Field


class PromptOverride(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    template: str = Field(min_length=1)
    updated_by: str = Field(max_length=100)
    updated_at: datetime
```

```python
# src/db/tables_prompt_overrides.py
"""SQLAlchemy table for global prompt overrides (AUTHOR-012).

Own module: `src/db/tables.py` is over the 200-line budget. Imported from
`tables.py` so `Base.metadata` is complete for Alembic and `create_all`.
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDMixin


class PromptOverrideRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "prompt_overrides"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    template: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(String(100))
```

In `src/db/tables.py` add, right after the `BriefRow` import block:
```python
from src.db.tables_prompt_overrides import (
    PromptOverrideRow,  # noqa: F401 — registers table on Base.metadata
)
```

```python
# src/db/prompt_override_repository.py
"""Repositories for `prompt_overrides` (AUTHOR-012). One row per key."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.tables_prompt_overrides import PromptOverrideRow
from src.models.prompt_override import PromptOverride

logger = structlog.get_logger()


class PromptOverrideRepository(Protocol):
    async def load_all(self) -> dict[str, str]: ...
    async def get(self, key: str) -> PromptOverride | None: ...
    async def upsert(self, key: str, *, template: str, updated_by: str) -> PromptOverride: ...
    async def delete(self, key: str) -> bool: ...


def _row_to_model(row: PromptOverrideRow) -> PromptOverride:
    return PromptOverride(
        key=row.key, template=row.template,
        updated_by=row.updated_by, updated_at=row.updated_at,
    )


class PgPromptOverrideRepository:
    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def load_all(self) -> dict[str, str]:
        async with self._sf() as db:
            rows = (await db.execute(select(PromptOverrideRow))).scalars().all()
            return {r.key: r.template for r in rows}

    async def get(self, key: str) -> PromptOverride | None:
        async with self._sf() as db:
            row = await self._find(db, key)
            return _row_to_model(row) if row else None

    async def upsert(self, key: str, *, template: str, updated_by: str) -> PromptOverride:
        async with self._sf() as db:
            row = await self._find(db, key)
            if row is None:
                row = PromptOverrideRow(key=key, template=template, updated_by=updated_by)
                db.add(row)
            else:
                row.template, row.updated_by = template, updated_by
            await db.commit()
            await db.refresh(row)
            logger.info("prompt_override_saved", key=key, updated_by=updated_by)
            return _row_to_model(row)

    async def delete(self, key: str) -> bool:
        async with self._sf() as db:
            result = await db.execute(delete(PromptOverrideRow).where(PromptOverrideRow.key == key))
            await db.commit()
            logger.info("prompt_override_reset", key=key, existed=bool(result.rowcount))
            return bool(getattr(result, "rowcount", 0))

    @staticmethod
    async def _find(db: AsyncSession, key: str) -> PromptOverrideRow | None:
        stmt = select(PromptOverrideRow).where(PromptOverrideRow.key == key)
        return (await db.execute(stmt)).scalar_one_or_none()


class InMemoryPromptOverrideRepository:
    """Unit tests + no-DB lifespan branch."""

    def __init__(self) -> None:
        self._rows: dict[str, PromptOverride] = {}

    async def load_all(self) -> dict[str, str]:
        return {k: v.template for k, v in self._rows.items()}

    async def get(self, key: str) -> PromptOverride | None:
        return self._rows.get(key)

    async def upsert(self, key: str, *, template: str, updated_by: str) -> PromptOverride:
        row = PromptOverride(key=key, template=template, updated_by=updated_by, updated_at=datetime.now(UTC))
        self._rows[key] = row
        return row

    async def delete(self, key: str) -> bool:
        return self._rows.pop(key, None) is not None
```

Migration (`down_revision` is the current head `d5e8f2a1c3b9` — re-check with `uv run alembic heads` before writing):
```python
"""add prompt_overrides table

Revision ID: e2a7c4d9b1f3
Revises: d5e8f2a1c3b9
Create Date: 2026-08-31 12:00:00.000000

AUTHOR-012 — global prompt overrides, one row per registry key.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2a7c4d9b1f3"
down_revision: str | Sequence[str] | None = "d5e8f2a1c3b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_overrides",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("key", name="uq_prompt_overrides_key"),
    )
    op.create_index("ix_prompt_overrides_key", "prompt_overrides", ["key"])


def downgrade() -> None:
    op.drop_index("ix_prompt_overrides_key", table_name="prompt_overrides")
    op.drop_table("prompt_overrides")
```

Integration test (same shape as `tests/integration/db/test_pg_briefs.py`; cleans `DELETE FROM prompt_overrides WHERE key LIKE 'it.%'`):
```python
# tests/integration/db/test_pg_prompt_overrides.py
"""Real-PostgreSQL round trip for PgPromptOverrideRepository (AUTHOR-012)."""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import tables  # noqa: F401
from src.db.base import Base
from src.db.engine import get_session_factory
from src.db.prompt_override_repository import PgPromptOverrideRepository

_DB_URL = "postgresql+asyncpg://cognify:cognify@localhost:5432/cognify"


@pytest_asyncio.fixture
async def sf() -> async_sessionmaker[AsyncSession]:  # type: ignore[misc]
    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = get_session_factory(engine)
    yield factory  # type: ignore[misc]
    async with factory() as db:
        await db.execute(text("DELETE FROM prompt_overrides WHERE key LIKE 'it.%'"))
        await db.commit()
    await engine.dispose()


@pytest.mark.integration
async def test_prompt_override_round_trip(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = PgPromptOverrideRepository(sf)
    await repo.upsert("it.system", template="A", updated_by="it-user")
    await repo.upsert("it.system", template="B", updated_by="it-user-2")
    assert (await repo.load_all()).get("it.system") == "B"
    got = await repo.get("it.system")
    assert got is not None and got.updated_by == "it-user-2"
    assert await repo.delete("it.system") is True
    assert await repo.delete("it.system") is False
```

- [ ] **Step 4: Run**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/db/test_prompt_override_repository.py -q` → 3 passed.
Then, with the Docker postgres up: `uv run alembic upgrade head` (from the worktree, `COGNIFY_DATABASE_URL` pointing at localhost — the main checkout `.env` already does) and `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/integration/db/test_pg_prompt_overrides.py -q -m integration` → 1 passed. Also `uv run alembic downgrade -1 && uv run alembic upgrade head` once to prove the downgrade.

- [ ] **Step 5: Commit**

```bash
git add src/models/prompt_override.py src/db/tables_prompt_overrides.py src/db/tables.py src/db/prompt_override_repository.py alembic/versions/e2a7c4d9b1f3_add_prompt_overrides.py tests/unit/db/test_prompt_override_repository.py tests/integration/db/test_pg_prompt_overrides.py
git commit -m "feat(prompts): prompt_overrides table, migration e2a7c4d9b1f3, Pg + in-memory repositories (AUTHOR-012)"
```

---

### Task 7: `/prompts` API + app wiring

**Files:**
- Create: `src/api/schemas/prompts.py`, `src/api/routers/prompts.py`
- Modify: `src/api/main.py` (import + `include_router` after `settings_router`; `app.state.prompt_override_repo` in both lifespan branches — Pg next to `brief_service` at line 279, in-memory next to line 389 in `create_app`)
- Test: `tests/unit/api/test_prompts_endpoints.py`

**Interfaces:**
- Consumes: `DEFAULT_PROMPTS`, `validate_template`, `PromptOverrideRepository`
- Produces: `PromptView`, `PromptListResponse`, `UpdatePromptRequest`; routes `GET /prompts`, `GET /prompts/{key}`, `PUT /prompts/{key}`, `DELETE /prompts/{key}`; `app.state.prompt_override_repo`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/api/test_prompts_endpoints.py
"""AUTHOR-012 — /prompts endpoints."""

from __future__ import annotations

import httpx
import pytest

from src.agents.prompts import DEFAULT_PROMPTS
from src.config.settings import Settings
from src.db.prompt_override_repository import InMemoryPromptOverrideRepository

from .conftest import make_auth_header

KEY = "content_outline.user"
GOOD = (
    "Outline for {title} / {description} / {domain}\n{findings_summary}\n"
    "{requirements}\n{schema_hint}"
)


@pytest.fixture
def prompts_app(auth_app):
    auth_app.state.prompt_override_repo = InMemoryPromptOverrideRepository()
    return auth_app


@pytest.fixture
async def client(prompts_app) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=prompts_app), base_url="http://test"
    ) as ac:
        yield ac


class TestList:
    async def test_editor_sees_every_registered_key(self, client, auth_settings: Settings) -> None:
        resp = await client.get("/api/v1/prompts", headers=make_auth_header("editor", auth_settings))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert {i["key"] for i in items} == set(DEFAULT_PROMPTS)
        row = next(i for i in items if i["key"] == KEY)
        assert row["is_overridden"] is False
        assert row["template"] == row["default_template"] == DEFAULT_PROMPTS[KEY].template
        assert set(row["variables"]) == set(DEFAULT_PROMPTS[KEY].variables)
        assert row["step"] == "content_outline"

    async def test_viewer_forbidden(self, client, auth_settings: Settings) -> None:
        resp = await client.get("/api/v1/prompts", headers=make_auth_header("viewer", auth_settings))
        assert resp.status_code == 403


class TestPut:
    async def test_admin_override_is_returned_and_listed(self, client, auth_settings: Settings) -> None:
        resp = await client.put(
            f"/api/v1/prompts/{KEY}", json={"template": GOOD},
            headers=make_auth_header("admin", auth_settings),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_overridden"] is True and body["template"] == GOOD
        assert body["updated_by"] == "user-1" and body["updated_at"]
        assert body["default_template"] == DEFAULT_PROMPTS[KEY].template
        single = await client.get(f"/api/v1/prompts/{KEY}", headers=make_auth_header("editor", auth_settings))
        assert single.json()["template"] == GOOD

    async def test_editor_cannot_put(self, client, auth_settings: Settings) -> None:
        resp = await client.put(
            f"/api/v1/prompts/{KEY}", json={"template": GOOD},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 403

    async def test_invalid_template_is_422_with_violations(self, client, auth_settings: Settings) -> None:
        resp = await client.put(
            f"/api/v1/prompts/{KEY}", json={"template": "only {title} and {bogus}"},
            headers=make_auth_header("admin", auth_settings),
        )
        assert resp.status_code == 422
        violations = resp.json()["detail"]["violations"]
        assert "unknown variable {bogus}" in violations
        assert "missing required variable {domain}" in violations

    async def test_unknown_key_404(self, client, auth_settings: Settings) -> None:
        resp = await client.put(
            "/api/v1/prompts/nope.system", json={"template": "x"},
            headers=make_auth_header("admin", auth_settings),
        )
        assert resp.status_code == 404


class TestDelete:
    async def test_reset_restores_default(self, client, auth_settings: Settings) -> None:
        admin = make_auth_header("admin", auth_settings)
        await client.put(f"/api/v1/prompts/{KEY}", json={"template": GOOD}, headers=admin)
        resp = await client.delete(f"/api/v1/prompts/{KEY}", headers=admin)
        assert resp.status_code == 200
        assert resp.json()["is_overridden"] is False
        assert resp.json()["template"] == DEFAULT_PROMPTS[KEY].template

    async def test_reset_without_override_404(self, client, auth_settings: Settings) -> None:
        resp = await client.delete(f"/api/v1/prompts/{KEY}", headers=make_auth_header("admin", auth_settings))
        assert resp.status_code == 404


class TestRateLimit:
    async def test_list_is_rate_limited(self, client, auth_settings: Settings) -> None:
        headers = make_auth_header("editor", auth_settings)
        codes = [(await client.get("/api/v1/prompts", headers=headers)).status_code for _ in range(31)]
        assert codes[-1] == 429
```

- [ ] **Step 2: Run to verify it fails**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_prompts_endpoints.py -q`
Expected: FAIL — 404s (router not registered) / import errors

- [ ] **Step 3: Implement schemas, router, wiring**

```python
# src/api/schemas/prompts.py
"""Request/response schemas for the prompt registry API (AUTHOR-012)."""

from datetime import datetime

from pydantic import BaseModel, Field


class PromptView(BaseModel):
    key: str
    step: str
    description: str
    variables: list[str]
    default_template: str
    template: str
    is_overridden: bool
    updated_by: str | None = None
    updated_at: datetime | None = None


class PromptListResponse(BaseModel):
    items: list[PromptView]


class UpdatePromptRequest(BaseModel):
    template: str = Field(min_length=1)
```

```python
# src/api/routers/prompts.py
"""Prompt registry endpoints (AUTHOR-012): view every registered prompt,
override one (admin), reset one (admin)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette import status as http_status

from src.agents.prompts import DEFAULT_PROMPTS, PromptTemplate
from src.agents.prompts.validation import validate_template
from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_admin, require_editor_or_above
from src.api.errors import NotFoundError, ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.prompts import PromptListResponse, PromptView, UpdatePromptRequest
from src.db.prompt_override_repository import PromptOverrideRepository
from src.models.prompt_override import PromptOverride

prompts_router = APIRouter()


def _repo(request: Request) -> PromptOverrideRepository:
    repo = getattr(request.app.state, "prompt_override_repo", None)
    if repo is None:
        raise ServiceUnavailableError(message="Prompt override store not configured.")
    return repo  # type: ignore[no-any-return]


def _spec(key: str) -> PromptTemplate:
    spec = DEFAULT_PROMPTS.get(key)
    if spec is None:
        raise NotFoundError(message=f"unknown prompt key: {key}")
    return spec


def _view(spec: PromptTemplate, override: PromptOverride | None) -> PromptView:
    return PromptView(
        key=spec.key, step=spec.step, description=spec.description,
        variables=sorted(spec.variables), default_template=spec.template,
        template=override.template if override else spec.template,
        is_overridden=override is not None,
        updated_by=override.updated_by if override else None,
        updated_at=override.updated_at if override else None,
    )


# Route decorator OUTERMOST or slowapi never evaluates the limit (AUTHOR-006).
@prompts_router.get("/prompts", response_model=PromptListResponse)
@limiter.limit("30/minute")
async def list_prompts(
    request: Request, user: TokenPayload = Depends(require_editor_or_above)
) -> PromptListResponse:
    overrides = await _repo(request).load_all()
    items = [
        _view(spec, _as_override(key, overrides)) for key, spec in sorted(DEFAULT_PROMPTS.items())
    ]
    return PromptListResponse(items=items)


def _as_override(key: str, overrides: dict[str, str]) -> PromptOverride | None:
    # load_all() carries only templates; the list view has no author/time.
    template = overrides.get(key)
    if template is None:
        return None
    from datetime import UTC, datetime

    return PromptOverride(key=key, template=template, updated_by="", updated_at=datetime.now(UTC))


@prompts_router.get("/prompts/{key}", response_model=PromptView)
@limiter.limit("30/minute")
async def get_prompt(
    request: Request, key: str, user: TokenPayload = Depends(require_editor_or_above)
) -> PromptView:
    return _view(_spec(key), await _repo(request).get(key))


@prompts_router.put("/prompts/{key}", response_model=PromptView)
@limiter.limit("30/minute")
async def put_prompt(
    request: Request,
    key: str,
    body: UpdatePromptRequest,
    user: TokenPayload = Depends(require_admin),
) -> PromptView:
    spec = _spec(key)
    violations = validate_template(body.template, spec)
    if violations:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"violations": violations},
        )
    saved = await _repo(request).upsert(key, template=body.template, updated_by=user.sub)
    return _view(spec, saved)


@prompts_router.delete("/prompts/{key}", response_model=PromptView)
@limiter.limit("30/minute")
async def reset_prompt(
    request: Request, key: str, user: TokenPayload = Depends(require_admin)
) -> PromptView:
    spec = _spec(key)
    if not await _repo(request).delete(key):
        raise NotFoundError(message=f"no override for prompt key: {key}")
    return _view(spec, None)
```

Simplify `_as_override`: change the list view to drop `updated_by`/`updated_at` for the list (they stay `None`) and only mark `is_overridden` + `template` — replace `_as_override` with an inline `PromptView(... is_overridden=key in overrides, template=overrides.get(key, spec.template) ...)` helper `_list_view(spec, overrides)` so no fake timestamp is fabricated. (Write it that way; the test only asserts `is_overridden`/`template` on the list.)

Wiring in `src/api/main.py`:
- import `from src.api.routers.prompts import prompts_router` with the other routers, and `include_router(prompts_router, prefix=settings.api_v1_prefix, tags=["prompts"])` after `settings_router`.
- DB branch (after line 279): `from src.db.prompt_override_repository import PgPromptOverrideRepository` + `app.state.prompt_override_repo = PgPromptOverrideRepository(sf)`.
- `create_app` (after line 389): `app.state.prompt_override_repo = InMemoryPromptOverrideRepository()` (import from the same module) — the DB branch replaces it at lifespan.

- [ ] **Step 4: Run**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_prompts_endpoints.py tests/unit/api -q`
Expected: all pass (the 429 test relies on the `reset_rate_limiter` autouse fixture in `tests/unit/api/conftest.py`).

- [ ] **Step 5: Commit**

```bash
git add src/api/schemas/prompts.py src/api/routers/prompts.py src/api/main.py tests/unit/api/test_prompts_endpoints.py
git commit -m "feat(prompts): GET/PUT/DELETE /prompts with validation + app wiring (AUTHOR-012)"
```

---

### Task 8: Runtime binding — pipeline runs and request-path LLM calls

**Files:**
- Modify: `src/services/pipeline_runner.py` (`PipelineDeps` + both runners), `src/services/bootstrap.py` (`PipelineServices.prompt_override_repo`), `src/tasks/pipeline_tasks.py:57-61`, `src/api/routers/research_pipeline.py:50-54`
- Create: `src/api/prompt_scope.py`
- Modify: `src/api/routers/content.py` (`section_rewrite`, `paragraph_tone`, `humanize_preview`), `src/api/routers/content_regenerate.py` (`section_regenerate`), `src/api/routers/article_metadata.py` (`regenerate_seo_field`), `src/api/routers/content_humanize_stream.py` (`gen()`), `src/api/routers/topics.py` (`analyze_topic`)
- Test: `tests/unit/services/test_pipeline_runner_prompts.py`, `tests/unit/api/test_prompt_scope.py`

**Interfaces:**
- Produces: `PipelineDeps.prompt_overrides: PromptOverridesLoader | None = None` where `PromptOverridesLoader = Callable[[], Awaitable[Mapping[str, str]]]`; `load_prompt_overrides(request) -> Mapping[str, str]` FastAPI dependency (never raises — logs `prompt_overrides_unavailable` and returns `{}`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/test_pipeline_runner_prompts.py
"""AUTHOR-012 — one override snapshot is bound for the whole pipeline run."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.agents.prompts import current_prompt_overrides
from src.services.pipeline_runner import PipelineDeps, _run_drafting_pipeline


def _research_svc(status: str = "awaiting_outline_review") -> MagicMock:
    svc = MagicMock()
    detail = MagicMock()
    detail.session.status = status
    svc.get_session = AsyncMock(return_value=detail)
    svc.update_session_status = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_drafting_run_sees_bound_overrides() -> None:
    seen: dict[str, str] = {}

    async def generate_from_outline(session_id):  # noqa: ANN001, ANN202
        seen.update(current_prompt_overrides.get())

    gate = MagicMock()
    gate.generate_from_outline = generate_from_outline
    deps = PipelineDeps(
        research_svc=_research_svc(), content_svc=None, outline_gate=gate,
        prompt_overrides=AsyncMock(return_value={"content_draft.system": "X"}),
    )
    await _run_drafting_pipeline(deps, uuid4())
    assert seen == {"content_draft.system": "X"}
    assert current_prompt_overrides.get() == {}  # unbound after the run


@pytest.mark.asyncio
async def test_loader_failure_falls_back_to_defaults() -> None:
    seen: dict[str, str] = {"sentinel": "unset"}

    async def generate_from_outline(session_id):  # noqa: ANN001, ANN202
        seen.clear()
        seen.update(current_prompt_overrides.get())

    gate = MagicMock()
    gate.generate_from_outline = generate_from_outline
    deps = PipelineDeps(
        research_svc=_research_svc(), content_svc=None, outline_gate=gate,
        prompt_overrides=AsyncMock(side_effect=RuntimeError("db down")),
    )
    await _run_drafting_pipeline(deps, uuid4())
    assert seen == {}
```

```python
# tests/unit/api/test_prompt_scope.py
"""AUTHOR-012 — request-scoped override loading never blocks the request."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.prompt_scope import load_prompt_overrides


@pytest.mark.asyncio
async def test_returns_repo_snapshot() -> None:
    request = MagicMock()
    request.app.state.prompt_override_repo = MagicMock(load_all=AsyncMock(return_value={"k": "v"}))
    assert await load_prompt_overrides(request) == {"k": "v"}


@pytest.mark.asyncio
async def test_missing_repo_returns_empty() -> None:
    request = MagicMock()
    request.app.state = MagicMock(spec=[])  # no prompt_override_repo attribute
    assert await load_prompt_overrides(request) == {}


@pytest.mark.asyncio
async def test_repo_error_returns_empty() -> None:
    request = MagicMock()
    request.app.state.prompt_override_repo = MagicMock(load_all=AsyncMock(side_effect=RuntimeError("x")))
    assert await load_prompt_overrides(request) == {}
```

- [ ] **Step 2: Run to verify they fail**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/test_pipeline_runner_prompts.py tests/unit/api/test_prompt_scope.py -q`
Expected: FAIL — `TypeError: unexpected keyword 'prompt_overrides'` / `ModuleNotFoundError: src.api.prompt_scope`

- [ ] **Step 3: Implement**

`src/services/pipeline_runner.py`:
```python
from collections.abc import Awaitable, Callable, Mapping
from src.agents.prompts import bind_prompt_overrides

PromptOverridesLoader = Callable[[], Awaitable[Mapping[str, str]]]


@dataclass(frozen=True)
class PipelineDeps:
    research_svc: ResearchService
    content_svc: ContentService | None
    outline_gate: OutlineGateService | None
    # AUTHOR-012 — loads the global prompt overrides once per run.
    prompt_overrides: PromptOverridesLoader | None = None


async def _load_prompt_overrides(deps: PipelineDeps) -> Mapping[str, str]:
    """One snapshot per run; a store outage must never block generation."""
    if deps.prompt_overrides is None:
        return {}
    try:
        return dict(await deps.prompt_overrides())
    except Exception as exc:  # noqa: BLE001
        logger.warning("prompt_overrides_unavailable", error=str(exc))
        return {}
```
Then wrap the bodies: in `_run_full_pipeline` and `_run_drafting_pipeline`, load first and put the existing `try:` block inside `with bind_prompt_overrides(overrides):`. Concretely, `_run_drafting_pipeline` becomes:
```python
async def _run_drafting_pipeline(deps: PipelineDeps, session_id: UUID) -> None:
    """Resume the pipeline from an editor-approved outline."""
    overrides = await _load_prompt_overrides(deps)
    with bind_prompt_overrides(overrides):
        try:
            await _drive_to_completion(
                deps.research_svc, session_id,
                lambda: deps.outline_gate.generate_from_outline(session_id),  # type: ignore[union-attr]
            )
        except asyncio.CancelledError:
            await deps.research_svc.update_session_status(session_id, "cancelled")
            raise
```
and `_run_full_pipeline` the same way around its whole `try:` (research + gate + content all share the snapshot). If either function crosses 20 lines, move the `try:` body into `_full_pipeline_body(deps, session_id, topic)`.

`src/services/bootstrap.py`: add `prompt_override_repo: PgPromptOverrideRepository` to `PipelineServices` (import from `src.db.prompt_override_repository`) and construct it in `build_pipeline_services`.

`src/tasks/pipeline_tasks.py:57-61`: `PipelineDeps(..., prompt_overrides=services.prompt_override_repo.load_all)`.
`src/api/routers/research_pipeline.py:50-54`: `prompt_overrides=getattr(getattr(request.app.state, "prompt_override_repo", None), "load_all", None)`.

```python
# src/api/prompt_scope.py
"""Request-scoped prompt overrides (AUTHOR-012).

Endpoints that call the LLM outside a pipeline run (section rewrite /
regenerate, SEO regenerate, humanize preview + stream, topic analyze) load
the current overrides once per request and bind them around the service
call with `bind_prompt_overrides`. Binding is explicit in the handler
(not a `yield` dependency) so StreamingResponse bodies, which run after
dependency teardown, can bind inside their generator.
"""

from collections.abc import Mapping

import structlog
from fastapi import Request

logger = structlog.get_logger()


async def load_prompt_overrides(request: Request) -> Mapping[str, str]:
    repo = getattr(request.app.state, "prompt_override_repo", None)
    if repo is None:
        return {}
    try:
        return dict(await repo.load_all())
    except Exception as exc:  # noqa: BLE001
        logger.warning("prompt_overrides_unavailable", error=str(exc))
        return {}
```

Handlers — add `overrides: Mapping[str, str] = Depends(load_prompt_overrides)` to the signature and wrap the LLM call:
- `content.py::section_rewrite` — `with bind_prompt_overrides(overrides): result = await rewrite_section_prose(...)`.
- `content.py::paragraph_tone` — wrap **both** `expand_tone_preset(body.preset)` and the `await section_rewrite(request, rewrite, user, overrides)` call (pass the loaded mapping through; `section_rewrite`'s own bind is nested and harmless).
- `content.py::humanize_preview` — wrap `await preview_humanization(...)`.
- `content_regenerate.py::section_regenerate` — wrap `await service.regenerate(...)`.
- `article_metadata.py::regenerate_seo_field` — wrap the `_regenerate_seo(...)` await.
- `content_humanize_stream.py::gen()` — `with bind_prompt_overrides(overrides): async for frame in stream_humanization(...): yield frame` (bind inside the generator).
- `topics.py::analyze_topic` — wrap `await analyzer.analyze(...)`.

The `Depends` dependency exceeds the 3-param rule on some handlers only nominally (FastAPI injections don't count against it in this repo — `section_rewrite` already has 3 injected params); keep the signature order `request, body, user, overrides`.

- [ ] **Step 4: Run**

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services tests/unit/api tests/unit/tasks -q` (skip `tests/unit/tasks` if it does not exist)
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/services/pipeline_runner.py src/services/bootstrap.py src/tasks/pipeline_tasks.py src/api/routers src/api/prompt_scope.py tests/unit/services/test_pipeline_runner_prompts.py tests/unit/api/test_prompt_scope.py
git commit -m "feat(prompts): bind override snapshot per pipeline run and per LLM request (AUTHOR-012)"
```

---

### Task 9: Frontend — types, API module, hook, role helper, nav entry

**Files:**
- Create: `frontend/src/types/prompts.ts`, `frontend/src/lib/api/prompts.ts`, `frontend/src/hooks/use-prompts.ts`, `frontend/src/lib/auth/role.ts`
- Modify: `frontend/src/types/settings.ts:3-9` (add `"prompts"`), `frontend/src/components/settings/settings-nav.tsx:5-12` (add tab, `FileText` icon), `settings-nav.test.tsx:6-13`
- Test: `frontend/src/hooks/use-prompts.test.tsx`, `frontend/src/lib/auth/role.test.ts`, `frontend/src/lib/api/prompts.test.ts`

**Interfaces:**
- Produces: `PromptView` TS type (snake_case, mirrors the API); `listPrompts(): Promise<PromptView[]>`, `updatePrompt(key, template)`, `resetPrompt(key)`, `extractPromptViolations(err): string[]`; `usePrompts() → { prompts, isLoading, error, save(key, template), reset(key) }` (mutations invalidate `["prompts"]`); `currentRole(): "admin" | "editor" | "viewer" | null` (decodes the JWT payload in `localStorage.cognify_access_token`).

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/api/prompts.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "@/lib/api/client";
import { extractPromptViolations, listPrompts, resetPrompt, updatePrompt } from "./prompts";

vi.mock("@/lib/api/client", () => ({
  apiClient: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const view = {
  key: "content_outline.user", step: "content_outline", description: "d",
  variables: ["title"], default_template: "D", template: "D",
  is_overridden: false, updated_by: null, updated_at: null,
};

describe("prompts api", () => {
  beforeEach(() => vi.clearAllMocks());

  it("listPrompts unwraps items", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [view] } });
    expect(await listPrompts()).toEqual([view]);
    expect(apiClient.get).toHaveBeenCalledWith("/prompts");
  });

  it("updatePrompt PUTs the template", async () => {
    vi.mocked(apiClient.put).mockResolvedValue({ data: view });
    await updatePrompt("content_outline.user", "T");
    expect(apiClient.put).toHaveBeenCalledWith("/prompts/content_outline.user", { template: "T" });
  });

  it("resetPrompt DELETEs", async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({ data: view });
    await resetPrompt("content_outline.user");
    expect(apiClient.delete).toHaveBeenCalledWith("/prompts/content_outline.user");
  });

  it("extractPromptViolations reads detail.violations on 422 only", () => {
    const err = { response: { status: 422, data: { detail: { violations: ["unknown variable {x}"] } } } };
    expect(extractPromptViolations(err)).toEqual(["unknown variable {x}"]);
    expect(extractPromptViolations({ response: { status: 500 } })).toEqual([]);
  });
});
```

```ts
// frontend/src/lib/auth/role.test.ts
import { describe, it, expect, afterEach } from "vitest";
import { currentRole } from "./role";

function token(payload: object): string {
  const b64 = btoa(JSON.stringify(payload)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `h.${b64}.s`;
}

describe("currentRole", () => {
  afterEach(() => localStorage.removeItem("cognify_access_token"));

  it("returns the role claim from the stored JWT", () => {
    localStorage.setItem("cognify_access_token", token({ sub: "u", role: "admin" }));
    expect(currentRole()).toBe("admin");
  });

  it("returns null without a token or with garbage", () => {
    expect(currentRole()).toBeNull();
    localStorage.setItem("cognify_access_token", "not-a-jwt");
    expect(currentRole()).toBeNull();
  });
});
```

```tsx
// frontend/src/hooks/use-prompts.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { usePrompts } from "./use-prompts";
import * as api from "@/lib/api/prompts";

vi.mock("@/lib/api/prompts");

const view = {
  key: "content_outline.user", step: "content_outline", description: "d",
  variables: ["title"], default_template: "D", template: "D",
  is_overridden: false, updated_by: null, updated_at: null,
};

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("usePrompts", () => {
  beforeEach(() => {
    vi.mocked(api.listPrompts).mockResolvedValue([view]);
    vi.mocked(api.updatePrompt).mockResolvedValue({ ...view, template: "X", is_overridden: true });
    vi.mocked(api.resetPrompt).mockResolvedValue(view);
  });

  it("loads prompts and refetches after save and reset", async () => {
    const { result } = renderHook(() => usePrompts(), { wrapper });
    await waitFor(() => expect(result.current.prompts).toHaveLength(1));
    await act(() => result.current.save("content_outline.user", "X"));
    expect(api.updatePrompt).toHaveBeenCalledWith("content_outline.user", "X");
    await act(() => result.current.reset("content_outline.user"));
    expect(api.resetPrompt).toHaveBeenCalledWith("content_outline.user");
    expect(api.listPrompts).toHaveBeenCalledTimes(3);
  });
});
```

Update `settings-nav.test.tsx`: rename the first test to "renders all 7 tab items" and add `expect(screen.getByText("Prompts")).toBeInTheDocument();` (the existing test says 5 but lists 6 tabs — leave the others, add Prompts).

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npx vitest run src/lib/api/prompts.test.ts src/lib/auth/role.test.ts src/hooks/use-prompts.test.tsx src/components/settings/settings-nav.test.tsx`
Expected: FAIL — cannot resolve `./prompts`, `./role`, `./use-prompts`; nav test misses "Prompts"

- [ ] **Step 3: Implement**

```ts
// frontend/src/types/prompts.ts
export interface PromptView {
  key: string;
  step: string;
  description: string;
  variables: string[];
  default_template: string;
  template: string;
  is_overridden: boolean;
  updated_by: string | null;
  updated_at: string | null;
}
```

```ts
// frontend/src/lib/api/prompts.ts
import { apiClient } from "@/lib/api/client";
import type { PromptView } from "@/types/prompts";

export async function listPrompts(): Promise<PromptView[]> {
  const { data } = await apiClient.get<{ items: PromptView[] }>("/prompts");
  return data.items;
}

export async function updatePrompt(key: string, template: string): Promise<PromptView> {
  const { data } = await apiClient.put<PromptView>(`/prompts/${key}`, { template });
  return data;
}

export async function resetPrompt(key: string): Promise<PromptView> {
  const { data } = await apiClient.delete<PromptView>(`/prompts/${key}`);
  return data;
}

interface AxiosLike {
  response?: { status?: number; data?: { detail?: { violations?: string[] } } };
}

export function extractPromptViolations(err: unknown): string[] {
  const e = err as AxiosLike;
  if (e?.response?.status !== 422) return [];
  return e.response.data?.detail?.violations ?? [];
}
```

```ts
// frontend/src/lib/auth/role.ts
export type Role = "admin" | "editor" | "viewer";

const TOKEN_KEY = "cognify_access_token";

/** Role claim of the stored access token (client-side hint only — the API enforces RBAC). */
export function currentRole(): Role | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem(TOKEN_KEY);
  const payload = token?.split(".")[1];
  if (!payload) return null;
  try {
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const role = (JSON.parse(json) as { role?: string }).role;
    return role === "admin" || role === "editor" || role === "viewer" ? role : null;
  } catch {
    return null;
  }
}
```

```ts
// frontend/src/hooks/use-prompts.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listPrompts, resetPrompt, updatePrompt } from "@/lib/api/prompts";
import type { PromptView } from "@/types/prompts";

export const PROMPTS_QUERY_KEY = ["prompts"] as const;

export function usePrompts() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: PROMPTS_QUERY_KEY, queryFn: listPrompts });
  const invalidate = () => qc.invalidateQueries({ queryKey: PROMPTS_QUERY_KEY });

  const saveM = useMutation({
    mutationFn: ({ key, template }: { key: string; template: string }) => updatePrompt(key, template),
    onSuccess: invalidate,
  });
  const resetM = useMutation({ mutationFn: resetPrompt, onSuccess: invalidate });

  return {
    prompts: query.data ?? ([] as PromptView[]),
    isLoading: query.isLoading,
    error: query.error ? (query.error instanceof Error ? query.error.message : "Failed to load prompts") : null,
    save: (key: string, template: string) => saveM.mutateAsync({ key, template }),
    reset: (key: string) => resetM.mutateAsync(key),
    isSaving: saveM.isPending || resetM.isPending,
  };
}
```

`types/settings.ts`: add `| "prompts"` to `SettingsTab`. `settings-nav.tsx`: import `FileText` from lucide-react and add `{ key: "prompts", label: "Prompts", icon: FileText }` after the `llm` entry.

- [ ] **Step 4: Run**

Run: the same vitest command as Step 2
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/prompts.ts frontend/src/types/settings.ts frontend/src/lib/api/prompts.ts frontend/src/lib/api/prompts.test.ts frontend/src/lib/auth frontend/src/hooks/use-prompts.ts frontend/src/hooks/use-prompts.test.tsx frontend/src/components/settings/settings-nav.tsx frontend/src/components/settings/settings-nav.test.tsx
git commit -m "feat(frontend): prompts API module, usePrompts hook, role helper, Prompts nav entry (AUTHOR-012)"
```

---

### Task 10: Frontend — Prompts tab, editor, page wiring

**Files:**
- Create: `frontend/src/components/settings/prompts-tab.tsx`, `prompt-editor.tsx`, `prompts-settings.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx` (render `<PromptsSettings />` for `activeTab === "prompts"`)
- Test: `frontend/src/components/settings/prompts-tab.test.tsx`, `prompt-editor.test.tsx`, `prompts-settings.test.tsx`

**Interfaces:**
- `PromptsTab({ prompts, selectedKey, onSelect })` — list grouped by `step`, "Overridden" badge, variable chips.
- `PromptEditor({ prompt, canEdit, violations, saving, onSave(template), onReset() })`.
- `PromptsSettings()` — container: `usePrompts()`, selection state, `currentRole() === "admin"`, `useToast`, maps 422 to violations.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/src/components/settings/prompts-tab.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PromptsTab } from "./prompts-tab";
import type { PromptView } from "@/types/prompts";

const base: PromptView = {
  key: "content_outline.user", step: "content_outline", description: "Outline user turn",
  variables: ["title", "domain"], default_template: "D", template: "D",
  is_overridden: false, updated_by: null, updated_at: null,
};
const overridden: PromptView = { ...base, key: "content_seo.user", step: "content_seo", is_overridden: true, template: "X" };

describe("PromptsTab", () => {
  it("groups by step, shows variables and the Overridden badge", () => {
    render(<PromptsTab prompts={[base, overridden]} selectedKey={null} onSelect={vi.fn()} />);
    expect(screen.getByText("content_outline")).toBeInTheDocument();
    expect(screen.getByText("content_seo")).toBeInTheDocument();
    expect(screen.getByText("{title}")).toBeInTheDocument();
    expect(screen.getAllByText("Overridden")).toHaveLength(1);
  });

  it("selects a prompt on click", () => {
    const onSelect = vi.fn();
    render(<PromptsTab prompts={[base]} selectedKey={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("content_outline.user"));
    expect(onSelect).toHaveBeenCalledWith("content_outline.user");
  });
});
```

```tsx
// frontend/src/components/settings/prompt-editor.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PromptEditor } from "./prompt-editor";
import type { PromptView } from "@/types/prompts";

const prompt: PromptView = {
  key: "content_outline.user", step: "content_outline", description: "d",
  variables: ["title"], default_template: "Default {title}", template: "Default {title}",
  is_overridden: false, updated_by: null, updated_at: null,
};

describe("PromptEditor", () => {
  it("disables Save until the template changes, then saves", () => {
    const onSave = vi.fn();
    render(<PromptEditor prompt={prompt} canEdit violations={[]} saving={false} onSave={onSave} onReset={vi.fn()} />);
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "New {title}" } });
    fireEvent.click(save);
    expect(onSave).toHaveBeenCalledWith("New {title}");
  });

  it("shows Reset only when overridden and renders violations", () => {
    render(
      <PromptEditor prompt={{ ...prompt, is_overridden: true, template: "X {title}" }} canEdit
        violations={["unknown variable {bogus}"]} saving={false} onSave={vi.fn()} onReset={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Reset to default" })).toBeInTheDocument();
    expect(screen.getByText("unknown variable {bogus}")).toBeInTheDocument();
  });

  it("is read-only for non-admins", () => {
    render(<PromptEditor prompt={prompt} canEdit={false} violations={[]} saving={false} onSave={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByRole("textbox")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.getByText(/Only admins can edit prompts/)).toBeInTheDocument();
  });
});
```

```tsx
// frontend/src/components/settings/prompts-settings.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PromptsSettings } from "./prompts-settings";

const save = vi.fn();
const reset = vi.fn();
const showToast = vi.fn();
vi.mock("@/hooks/use-prompts", () => ({
  usePrompts: () => ({
    prompts: [{
      key: "content_outline.user", step: "content_outline", description: "d",
      variables: ["title"], default_template: "D {title}", template: "D {title}",
      is_overridden: false, updated_by: null, updated_at: null,
    }],
    isLoading: false, error: null, save, reset, isSaving: false,
  }),
}));
vi.mock("@/components/ui/toaster", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/lib/auth/role", () => ({ currentRole: () => "admin" }));

describe("PromptsSettings", () => {
  beforeEach(() => { save.mockReset(); reset.mockReset(); showToast.mockReset(); });

  it("saves the edited template and toasts", async () => {
    save.mockResolvedValue({});
    render(<PromptsSettings />);
    fireEvent.click(screen.getByText("content_outline.user"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "E {title}" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith("content_outline.user", "E {title}"));
    expect(showToast).toHaveBeenCalledWith("Prompt saved");
  });

  it("surfaces 422 violations instead of a toast", async () => {
    save.mockRejectedValue({ response: { status: 422, data: { detail: { violations: ["missing required variable {title}"] } } } });
    render(<PromptsSettings />);
    fireEvent.click(screen.getByText("content_outline.user"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "no vars" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("missing required variable {title}")).toBeInTheDocument();
    expect(showToast).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/prompts-tab.test.tsx src/components/settings/prompt-editor.test.tsx src/components/settings/prompts-settings.test.tsx`
Expected: FAIL — modules not found

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/settings/prompts-tab.tsx
import { cn } from "@/lib/utils";
import type { PromptView } from "@/types/prompts";

interface PromptsTabProps {
  prompts: PromptView[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}

function groupByStep(prompts: PromptView[]): [string, PromptView[]][] {
  const groups = new Map<string, PromptView[]>();
  for (const p of prompts) groups.set(p.step, [...(groups.get(p.step) ?? []), p]);
  return [...groups.entries()];
}

export function PromptsTab({ prompts, selectedKey, onSelect }: PromptsTabProps) {
  return (
    <div className="space-y-5" data-testid="prompts-tab">
      {groupByStep(prompts).map(([step, items]) => (
        <section key={step}>
          <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">{step}</h3>
          <ul className="mt-2 divide-y divide-neutral-100 rounded-lg border border-neutral-200">
            {items.map((p) => (
              <li key={p.key}>
                <button
                  type="button"
                  onClick={() => onSelect(p.key)}
                  className={cn(
                    "flex w-full items-start justify-between gap-3 px-4 py-3 text-left hover:bg-neutral-50",
                    selectedKey === p.key && "bg-primary-light",
                  )}
                >
                  <span>
                    <span className="block font-mono text-sm text-neutral-900">{p.key}</span>
                    <span className="block text-xs text-neutral-500">{p.description}</span>
                    <span className="mt-1 flex flex-wrap gap-1">
                      {p.variables.map((v) => (
                        <span key={v} className="rounded-full bg-neutral-100 px-2 py-0.5 font-mono text-xs text-neutral-600">
                          {`{${v}}`}
                        </span>
                      ))}
                    </span>
                  </span>
                  {p.is_overridden && (
                    <span className="shrink-0 rounded-full bg-warning-light px-2.5 py-0.5 text-xs font-medium text-warning">
                      Overridden
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
```

```tsx
// frontend/src/components/settings/prompt-editor.tsx
import { useEffect, useState } from "react";
import type { PromptView } from "@/types/prompts";

interface PromptEditorProps {
  prompt: PromptView;
  canEdit: boolean;
  violations: string[];
  saving: boolean;
  onSave: (template: string) => void;
  onReset: () => void;
}

export function PromptEditor({ prompt, canEdit, violations, saving, onSave, onReset }: PromptEditorProps) {
  const [draft, setDraft] = useState(prompt.template);
  useEffect(() => setDraft(prompt.template), [prompt.key, prompt.template]);
  const dirty = draft !== prompt.template;

  return (
    <div className="space-y-3" data-testid="prompt-editor">
      <div>
        <h3 className="font-mono text-sm font-semibold text-neutral-900">{prompt.key}</h3>
        <p className="text-xs text-neutral-500">{prompt.description}</p>
      </div>
      <textarea
        value={draft}
        readOnly={!canEdit}
        onChange={(e) => setDraft(e.target.value)}
        rows={14}
        className="w-full rounded-md border border-neutral-200 p-3 font-mono text-sm text-neutral-800 focus:border-primary focus:outline-none"
      />
      {violations.length > 0 && (
        <ul className="rounded-md border border-error/40 bg-error-light p-3 text-xs text-error">
          {violations.map((v) => <li key={v}>{v}</li>)}
        </ul>
      )}
      {!canEdit ? (
        <p className="text-xs text-neutral-500">Only admins can edit prompts.</p>
      ) : (
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!dirty || saving}
            onClick={() => onSave(draft)}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
          >
            Save
          </button>
          {prompt.is_overridden && (
            <button
              type="button"
              disabled={saving}
              onClick={onReset}
              className="rounded-md bg-neutral-100 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-50"
            >
              Reset to default
            </button>
          )}
        </div>
      )}
    </div>
  );
}
```

```tsx
// frontend/src/components/settings/prompts-settings.tsx
"use client";

import { useState } from "react";
import { PromptEditor } from "@/components/settings/prompt-editor";
import { PromptsTab } from "@/components/settings/prompts-tab";
import { useToast } from "@/components/ui/toaster";
import { usePrompts } from "@/hooks/use-prompts";
import { extractPromptViolations } from "@/lib/api/prompts";
import { currentRole } from "@/lib/auth/role";

export function PromptsSettings() {
  const { prompts, isLoading, error, save, reset, isSaving } = usePrompts();
  const { showToast } = useToast();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [violations, setViolations] = useState<string[]>([]);
  const canEdit = currentRole() === "admin";
  const selected = prompts.find((p) => p.key === selectedKey) ?? null;

  const handleSave = async (template: string) => {
    if (!selected) return;
    try {
      await save(selected.key, template);
      setViolations([]);
      showToast("Prompt saved");
    } catch (err) {
      const found = extractPromptViolations(err);
      setViolations(found.length ? found : ["Save failed"]);
    }
  };

  const handleReset = async () => {
    if (!selected) return;
    await reset(selected.key);
    setViolations([]);
    showToast("Prompt reset to default");
  };

  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">Prompts</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Edits apply to the next run. Every template must use exactly its listed variables.
      </p>
      {error && <p className="mt-3 text-sm text-error">{error}</p>}
      {isLoading ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <PromptsTab prompts={prompts} selectedKey={selectedKey} onSelect={(k) => { setSelectedKey(k); setViolations([]); }} />
          {selected ? (
            <PromptEditor prompt={selected} canEdit={canEdit} violations={violations} saving={isSaving} onSave={handleSave} onReset={handleReset} />
          ) : (
            <p className="text-sm text-neutral-500">Select a prompt to view or edit it.</p>
          )}
        </div>
      )}
    </div>
  );
}
```

`settings/page.tsx`: import `PromptsSettings` and add `{activeTab === "prompts" && <PromptsSettings />}` after the `llm` block.

- [ ] **Step 4: Run the whole frontend suite + lint + size budget**

Run: `cd frontend && npx vitest run && npx eslint src --max-warnings=5 && npx tsc --noEmit | tail -3`
Expected: all Vitest green (incl. `file-size-budget.test.ts`); eslint 0 errors; `tsc` at the 13-error baseline (no new errors).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings frontend/src/app/\(dashboard\)/settings/page.tsx
git commit -m "feat(frontend): Settings → Prompts tab with editor, reset and violation display (AUTHOR-012)"
```

---

### Task 11: Full verification + live smoke

**Files:** none new.

- [ ] **Step 1: Backend gates**

Run:
```bash
COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/ -q
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
uv run mypy src/ --ignore-missing-imports | tail -1
```
Expected: 0 failures; ruff clean; mypy error count ≤ the develop baseline (116) with none in new files (`mypy src/agents/prompts src/api/routers/prompts.py src/api/prompt_scope.py src/db/prompt_override_repository.py`).

- [ ] **Step 2: Live smoke (stack up on the main checkout's images is fine — run the API in-process from the worktree against the Docker DB, as the AUTHOR-010 smoke did)**

1. `uv run alembic upgrade head` (→ `e2a7c4d9b1f3`).
2. Start the API: `uv run uvicorn src.api.main:app --port 8010 --env-file D:/Workbench/github/cognify/.env`.
3. `GET /api/v1/prompts` as editor → every key present, none overridden.
4. `PUT /api/v1/prompts/content_outline.user` as admin with the default template plus the sentence `Mention the phrase PROMPT-OVERRIDE-SMOKE in the reasoning field.` appended → 200, `is_overridden: true`. Then PUT a template missing `{findings_summary}` → 422 with `missing required variable {findings_summary}`.
5. Generate a short article (`POST /research/sessions` on any topic, `length_target: short`) → after `article_complete`, `SELECT prompt_messages FROM llm_calls WHERE session_id=… AND call_name='content_outline'` contains `PROMPT-OVERRIDE-SMOKE`, and the API log shows `prompt_override_applied key=content_outline.user`.
6. `DELETE /api/v1/prompts/content_outline.user` → 200, `is_overridden: false`; a second generation's outline prompt no longer contains the sentinel.
7. Browser: Settings → Prompts renders the grouped list; as admin edit + save shows the "Prompt saved" toast; an invalid edit shows the violation list inline; Reset removes the badge. Log in as `editor@cognify.dev` → textarea read-only, "Only admins can edit prompts."
Record outcomes (session ids, counts) in the PR body.

- [ ] **Step 3: Commit any fixes**

```bash
git commit -am "fix(prompts): smoke findings (AUTHOR-012)"   # only if something needed fixing
```

---

### Task 12: Docs + PR

**Files:**
- Modify: `docs/superpowers/specs/2026-08-31-author-012-prompt-registry-design.md` §3.2 (replace the shared `research_claims` row with `research_web_claims.*` (`title, snippets`) and `research_literature_claims.*` (`title, abstracts`); total 18 key groups), `project-management/PROGRESS.md` (AUTHOR-012 row → Done with PR number; RESUME block: one paragraph with the smoke record and the follow-ups), `project-management/BACKLOG.md` (AUTHOR-012 row → DONE; summary table 15/17 done, remaining 18 SP), `CLAUDE.md` (Epic 11 paragraph: one sentence on the registry + `/prompts` + Prompts tab; "Next action"), `docs/LEARNINGS.md` (add **L-014**: "Prompts are registry keys — never add a new module-level prompt constant; register a `PromptTemplate` and call `render_prompt`; zero-variable templates are returned verbatim; overrides are one snapshot per run"), `.claude/rules/` untouched.
- Plan checkboxes ticked.

- [ ] **Step 1: Edit the docs listed above**
- [ ] **Step 2: Commit and push, open the PR against `develop`**

```bash
git add docs project-management CLAUDE.md
git commit -m "docs(AUTHOR-012): spec amendment, L-014, progress/backlog/CLAUDE status"
git push -u origin feature/AUTHOR-012-prompt-registry
gh pr create --base develop --title "feat(prompts): AUTHOR-012 prompt registry + global overrides + Settings Prompts tab" --body-file <pr-body.md>
```
PR body: summary, the 18 key groups, the per-run snapshot semantics, the byte-identical guarantee + how it is tested, migration id, smoke record, follow-ups (per-user tier, history, image-planner prompts), `AB#` none (no Azure item for Epic 11).

- [ ] **Step 3: Code review (`/code-review medium`), address findings, CI green, merge with `--admin`, then post-merge housekeeping** (pull develop in the main checkout, `docker compose up --build -d api worker`, `uv run alembic upgrade head` against the stack, remove the worktree, update memory `project_epic11_status.md`).

---

## Self-review

- **Spec coverage:** §3.1 registry → Task 1; §3.2 keys → Tasks 3/4/5 (with the two-pair correction carried into Task 12); §3.3 validation → Task 2; §4 storage → Task 6; §5 API → Task 7; §6 runtime binding (pipeline + request + failure mode + logging) → Task 8 (+ `prompt_override_applied` in Task 1); §7 frontend → Tasks 9/10; §8 tests → each task + Task 11 smoke; §9 non-goals respected (no per-user, no history, image planner untouched, schema hints stay code).
- **Placeholders:** the only `<verbatim …>` markers are explicit copy instructions pointing at exact source lines, by design (the literals already exist in the repo and retyping them is the error source we are guarding against).
- **Type consistency:** `render_prompt(key, **variables)` / `resolve_prompt(key)` / `bind_prompt_overrides(mapping)` / `current_prompt_overrides` are used with the same names in Tasks 1–8; `PromptOverrideRepository.upsert(key, *, template, updated_by)` matches Tasks 6/7; `PipelineDeps.prompt_overrides` loader signature matches Task 8's two call sites; frontend `PromptView` field names are the API's snake_case in Tasks 7/9/10.
