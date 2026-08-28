# AUTHOR-010 — Model tiering per step (`COGNIFY_LLM_MODEL_BY_STEP`) + Settings display

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators route each tracked pipeline step (`content_queries`, `content_draft`, `plan_research`, …) to a different Claude model via one env JSON map, with today's single-model behaviour as the untouched default, and show the effective step→model table read-only in Settings → LLM.

**Architecture:** A `TieredChatModel` wrapper (new `src/utils/tiered_llm.py`) holds a default model plus a `step → model` dict and delegates each call to the model for the step name currently bound in the existing `current_step_name` contextvar; it exposes `model` so the existing `TrackedChatModel` records (and the usage badge prices) the model that actually ran. `_build_llm` in `bootstrap_builders.py` returns it only when the map is non-empty. `_wrap_node` now binds the step name even without a step repo, so tiering also works in no-DB mode and the outline-only half-graph. `GET /settings/llm` gains two read-only fields; the LLM tab renders them in a small card. Scope decision (2026-08-28, with the user): env map + read-only display; the DB-stored Primary/Drafting dropdowns stay unwired (follow-up).

**Tech Stack:** Python 3.12 / pydantic-settings / langchain-core `BaseChatModel` / pytest + `FakeListChatModel`; Next.js 15 / Vitest + Testing Library.

**Spec:** `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §5.8 + §9 Phase B (AUTHOR-010 row); `docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md` §6 #14.

## Global Constraints

- All functions < 20 lines, files < 200 lines, max 3 params (CLAUDE.md); `frontend/src/file-size-budget.test.ts` enforces `src/app` + `src/components`. `frontend/src/hooks/use-settings.ts` is already 353 lines — add ≤ 10 lines there, do not split it in this ticket.
- TDD: failing test first. Backend `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/ -q`; frontend `cd frontend && npx vitest run`. Never `create_app()` with an Anthropic key in tests (Milvus-connect hang).
- New setting: `Settings.llm_model_by_step: dict[str, str] = {}` (`COGNIFY_LLM_MODEL_BY_STEP`), same JSON-dict pattern as `llm_pricing_json` / `length_budgets_json`. Default `{}` = byte-identical to today.
- Map keys are the **tracked step names** exactly as stored in `llm_calls.call_name`: `content_outline`, `content_queries`, `content_draft`, `content_validate`, `content_citations`, `content_humanize`, `content_seo`, `content_charts`, `content_diagrams`, `plan_research`, `evaluate_completeness`, `section_regenerate`, `seo_regenerate`. Unknown keys are honoured but warned about once at build time.
- Route decorator OUTERMOST, `@limiter.limit` inside (AUTHOR-006 lesson) — fix this on the two `/settings/llm` routes you touch (they currently have the dead order).
- No new colour/font tokens; the card uses the existing card + table tokens from `frontend/DESIGN.md`.
- One PR off `develop`, never stacked. No Azure Boards items for Epic 11.
- Conventional commits: `feat(llm): …`, `feat(api): …`, `feat(frontend): …`, `docs: …`.

## File map

| Area | Create | Modify |
|---|---|---|
| Wrapper | `src/utils/tiered_llm.py`, `tests/unit/utils/test_tiered_llm.py` | — |
| Builder + setting | — | `src/config/settings.py`, `src/services/bootstrap_builders.py`, `tests/unit/services/test_bootstrap.py`, `.env.example` |
| Step binding | — | `src/agents/content/pipeline.py`, `tests/unit/agents/content/test_pipeline_progress.py` |
| API | — | `src/api/schemas/settings.py`, `src/api/routers/settings_config.py`, `tests/unit/api/test_settings_endpoints.py` |
| Frontend | `frontend/src/components/settings/model-tiering-card.tsx`, `frontend/src/components/settings/model-tiering-card.test.tsx` | `frontend/src/types/settings.ts`, `frontend/src/hooks/use-settings.ts`, `frontend/src/hooks/use-settings.test.ts`, `frontend/src/components/settings/llm-config-tab.tsx`, `frontend/src/components/settings/llm-config-tab.test.tsx` |
| Docs | — | `project-management/PROGRESS.md`, `project-management/BACKLOG.md`, `CLAUDE.md`, this plan |

---

### Task 1: `TieredChatModel`

**Files:**
- Create: `src/utils/tiered_llm.py`
- Test: `tests/unit/utils/test_tiered_llm.py`

**Interfaces:**
- Produces:
  ```python
  KNOWN_LLM_STEPS: frozenset[str]   # the 13 tracked step names listed in Global Constraints
  class TieredChatModel(BaseChatModel):
      default: BaseChatModel
      by_step: dict[str, BaseChatModel]
      @property model -> str            # model name of the model that would serve the current step
      def active(self) -> BaseChatModel # by_step.get(current_step_name.get()) or default
  ```
  `_generate` / `_agenerate` delegate to `active()`; `_llm_type == "tiered"`.

- [ ] **Step 1: Write the failing tests** — `tests/unit/utils/test_tiered_llm.py`:

```python
"""AUTHOR-010 — per-step model routing via the tracker's step contextvar."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from src.utils.tiered_llm import KNOWN_LLM_STEPS, TieredChatModel
from src.utils.tracked_llm import current_step_name


class _NamedFake(FakeListChatModel):
    """FakeListChatModel with a `model` attribute like ChatAnthropic."""

    model: str = "fake"


def _fake(name: str, reply: str) -> _NamedFake:
    return _NamedFake(model=name, responses=[reply, reply, reply])


def _tiered() -> TieredChatModel:
    return TieredChatModel(
        default=_fake("claude-sonnet", "from sonnet"),
        by_step={"content_queries": _fake("claude-haiku", "from haiku")},
    )


class TestTieredChatModel:
    async def test_routes_to_step_model_when_step_is_bound(self) -> None:
        llm = _tiered()
        token = current_step_name.set("content_queries")
        try:
            out = await llm.ainvoke([HumanMessage(content="hi")])
        finally:
            current_step_name.reset(token)
        assert out.content == "from haiku"

    async def test_falls_back_to_default_for_unmapped_step(self) -> None:
        llm = _tiered()
        token = current_step_name.set("content_draft")
        try:
            out = await llm.ainvoke([HumanMessage(content="hi")])
        finally:
            current_step_name.reset(token)
        assert out.content == "from sonnet"

    async def test_falls_back_to_default_when_no_step_bound(self) -> None:
        out = await _tiered().ainvoke([HumanMessage(content="hi")])
        assert out.content == "from sonnet"

    def test_sync_invoke_routes_too(self) -> None:
        llm = _tiered()
        token = current_step_name.set("content_queries")
        try:
            out = llm.invoke([HumanMessage(content="hi")])
        finally:
            current_step_name.reset(token)
        assert out.content == "from haiku"

    def test_model_property_reflects_active_model(self) -> None:
        llm = _tiered()
        assert llm.model == "claude-sonnet"
        token = current_step_name.set("content_queries")
        try:
            assert llm.model == "claude-haiku"
        finally:
            current_step_name.reset(token)

    def test_llm_type(self) -> None:
        assert _tiered()._llm_type == "tiered"

    def test_known_steps_cover_the_content_and_research_graphs(self) -> None:
        for step in (
            "content_outline", "content_queries", "content_draft", "content_validate",
            "content_citations", "content_humanize", "content_seo", "content_charts",
            "content_diagrams", "plan_research", "evaluate_completeness",
            "section_regenerate", "seo_regenerate",
        ):
            assert step in KNOWN_LLM_STEPS


class TestTrackedOverTiered:
    async def test_tracker_records_the_model_that_ran(self) -> None:
        from uuid import uuid4

        from src.utils.tracked_llm import TrackedChatModel, current_session_id

        saved: list[object] = []

        class _Repo:
            async def create(self, call: object) -> None:
                saved.append(call)

        tracked = TrackedChatModel(inner=_tiered(), repo=_Repo())
        sid_token = current_session_id.set(uuid4())
        step_token = current_step_name.set("content_queries")
        try:
            await tracked.ainvoke([HumanMessage(content="hi")])
        finally:
            current_step_name.reset(step_token)
            current_session_id.reset(sid_token)
        assert len(saved) == 1
        assert getattr(saved[0], "model_name") == "claude-haiku"
        assert getattr(saved[0], "call_name") == "content_queries"
```

- [ ] **Step 2: Run to verify they fail** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/utils/test_tiered_llm.py -q` → import error.

- [ ] **Step 3: Implement** — `src/utils/tiered_llm.py`:

```python
"""AUTHOR-010 — route each pipeline step to its own model.

`TieredChatModel` reads the step name the tracker already binds
(`src.utils.tracked_llm.current_step_name`) and delegates to the model
configured for it, falling back to `default`. Wrap it *inside*
`TrackedChatModel` so `llm_calls.model_name` (and the usage badge) reflect
the model that actually served the call.
"""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from src.utils.tracked_llm import current_step_name

KNOWN_LLM_STEPS: frozenset[str] = frozenset(
    {
        "content_outline",
        "content_queries",
        "content_draft",
        "content_validate",
        "content_citations",
        "content_humanize",
        "content_seo",
        "content_charts",
        "content_diagrams",
        "plan_research",
        "evaluate_completeness",
        "section_regenerate",
        "seo_regenerate",
    }
)


class TieredChatModel(BaseChatModel):
    """Delegates to `by_step[current_step]` when configured, else `default`."""

    default: BaseChatModel
    by_step: dict[str, BaseChatModel]

    @property
    def _llm_type(self) -> str:
        return "tiered"

    @property
    def model(self) -> str:
        """Model name of the model serving the current step (for tracking)."""
        return str(getattr(self.active(), "model", "unknown"))

    def active(self) -> BaseChatModel:
        return self.by_step.get(current_step_name.get(), self.default)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self.active()._generate(messages, stop, run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return await self.active()._agenerate(messages, stop, run_manager, **kwargs)


__all__ = ["KNOWN_LLM_STEPS", "TieredChatModel"]
```

If pydantic complains about the `model` property shadowing its protected `model_` namespace, add `model_config = ConfigDict(protected_namespaces=())` to the class (import `ConfigDict` from `pydantic`).

- [ ] **Step 4: Run to verify they pass** — same command → 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/utils/tiered_llm.py tests/unit/utils/test_tiered_llm.py
git commit -m "feat(llm): TieredChatModel routes calls by tracked step name (AUTHOR-010)"
```

---

### Task 2: Setting + builder (`_build_llm` returns a tiered model when the map is set)

**Files:**
- Modify: `src/config/settings.py`, `src/services/bootstrap_builders.py`, `.env.example`
- Test: `tests/unit/services/test_bootstrap.py`

**Interfaces:**
- `Settings.llm_model_by_step: dict[str, str] = {}`.
- `bootstrap_builders.build_tiered_llm(settings) -> BaseChatModel` (untracked): plain `ChatAnthropic` for `{}`; otherwise `TieredChatModel` with one shared `ChatAnthropic` per distinct model id (`max_tokens=4096`, same as today); logs `llm_tiering_configured` (steps, distinct models) and `llm_tiering_unknown_step` per key not in `KNOWN_LLM_STEPS`.
- `_build_llm(settings, llm_call_repo)` now calls `build_tiered_llm` and wraps in `TrackedChatModel` when a repo is given (unchanged contract).

- [ ] **Step 1: Failing tests** — append to `tests/unit/services/test_bootstrap.py`:

```python
import structlog.testing

from src.services.bootstrap_builders import _build_llm, build_tiered_llm
from src.utils.tiered_llm import TieredChatModel
from src.utils.tracked_llm import TrackedChatModel


class TestModelTiering:
    def test_setting_parses_json_env(self, monkeypatch) -> None:
        monkeypatch.setenv("COGNIFY_LLM_MODEL_BY_STEP", '{"content_queries": "claude-haiku-4-5"}')
        settings = Settings(_env_file=None)
        assert settings.llm_model_by_step == {"content_queries": "claude-haiku-4-5"}

    def test_empty_map_builds_plain_model(self) -> None:
        settings = Settings(_env_file=None, anthropic_api_key="k")
        llm = build_tiered_llm(settings)
        assert not isinstance(llm, TieredChatModel)
        assert getattr(llm, "model") == settings.anthropic_model

    def test_map_builds_tiered_model_sharing_instances(self) -> None:
        settings = Settings(
            _env_file=None,
            anthropic_api_key="k",
            llm_model_by_step={
                "content_queries": "claude-haiku-4-5",
                "content_validate": "claude-haiku-4-5",
                "content_draft": settings_default_model(),
            },
        )
        llm = build_tiered_llm(settings)
        assert isinstance(llm, TieredChatModel)
        assert llm.by_step["content_queries"] is llm.by_step["content_validate"]
        assert llm.by_step["content_draft"] is llm.default
        assert getattr(llm.default, "model") == settings.anthropic_model

    def test_unknown_step_is_warned_but_kept(self) -> None:
        settings = Settings(
            _env_file=None, anthropic_api_key="k", llm_model_by_step={"nope": "claude-haiku-4-5"}
        )
        with structlog.testing.capture_logs() as logs:
            llm = build_tiered_llm(settings)
        assert isinstance(llm, TieredChatModel) and "nope" in llm.by_step
        assert any(log["event"] == "llm_tiering_unknown_step" for log in logs)

    def test_build_llm_wraps_tiered_in_tracker(self) -> None:
        settings = Settings(
            _env_file=None, anthropic_api_key="k", llm_model_by_step={"content_queries": "claude-haiku-4-5"}
        )
        llm = _build_llm(settings, llm_call_repo=object())
        assert isinstance(llm, TrackedChatModel)
        assert isinstance(llm.inner, TieredChatModel)


def settings_default_model() -> str:
    return Settings(_env_file=None).anthropic_model
```

(`Settings(_env_file=None)` calls need `# type: ignore[call-arg]` if mypy runs on tests — match the file's existing style.)

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/test_bootstrap.py -q` → import error on `build_tiered_llm` / unknown field.

- [ ] **Step 2: Implement**

`src/config/settings.py` — after `humanize_preview_max_passes`:

```python
    # AUTHOR-010: route tracked pipeline steps to specific models. Keys are
    # llm_calls.call_name values (content_outline, content_queries,
    # content_draft, content_validate, content_citations, content_humanize,
    # content_seo, content_charts, content_diagrams, plan_research,
    # evaluate_completeness, section_regenerate, seo_regenerate); values are
    # Anthropic model ids. Empty = every step uses `anthropic_model`.
    # Env: COGNIFY_LLM_MODEL_BY_STEP='{"content_queries": "claude-haiku-4-5-20251001"}'
    llm_model_by_step: dict[str, str] = {}
```

`src/services/bootstrap_builders.py` — replace `_build_llm` with:

```python
def _anthropic(settings: Settings, model: str) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,  # type: ignore[call-arg]
        api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
        max_tokens=4096,
    )


def build_tiered_llm(settings: Settings) -> BaseChatModel:
    """AUTHOR-010: one ChatAnthropic per distinct model id, routed per step."""
    from src.utils.tiered_llm import KNOWN_LLM_STEPS, TieredChatModel

    default = _anthropic(settings, settings.anthropic_model)
    if not settings.llm_model_by_step:
        return default
    instances: dict[str, BaseChatModel] = {settings.anthropic_model: default}
    by_step: dict[str, BaseChatModel] = {}
    for step, model in settings.llm_model_by_step.items():
        if step not in KNOWN_LLM_STEPS:
            logger.warning("llm_tiering_unknown_step", step=step, model=model)
        by_step[step] = instances.setdefault(model, _anthropic(settings, model))
    logger.info(
        "llm_tiering_configured", steps=sorted(by_step), models=sorted(instances)
    )
    return TieredChatModel(default=default, by_step=by_step)


def _build_llm(
    settings: Settings,
    llm_call_repo: object | None = None,
) -> BaseChatModel:
    """Build the (optionally tiered, optionally tracked) pipeline LLM."""
    llm = build_tiered_llm(settings)
    if llm_call_repo is not None:
        from src.utils.tracked_llm import TrackedChatModel

        return TrackedChatModel(inner=llm, repo=llm_call_repo)
    return llm
```

(`instances.setdefault(model, _anthropic(...))` would construct eagerly — write it as `if model not in instances: instances[model] = _anthropic(settings, model)` then `by_step[step] = instances[model]` to avoid building a throwaway client.) Add `build_tiered_llm` to the module's `__all__` if one exists.

`.env.example` — after the `COGNIFY_ANTHROPIC_API_KEY` line:

```
# AUTHOR-010 — per-step model tiering (JSON map of tracked step name -> model id).
# Keys: content_outline, content_queries, content_draft, content_validate, content_citations,
# content_humanize, content_seo, content_charts, content_diagrams, plan_research,
# evaluate_completeness, section_regenerate, seo_regenerate. Empty = single model.
# Recommended starting point (cheap model for the mechanical steps):
# COGNIFY_LLM_MODEL_BY_STEP={"content_queries":"claude-haiku-4-5-20251001","content_validate":"claude-haiku-4-5-20251001","content_citations":"claude-haiku-4-5-20251001","evaluate_completeness":"claude-haiku-4-5-20251001"}
```

- [ ] **Step 3: Verify** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/test_bootstrap.py tests/unit/utils/test_tiered_llm.py -q` → all pass.

- [ ] **Step 4: Commit**

```bash
git add src/config/settings.py src/services/bootstrap_builders.py .env.example tests/unit/services/test_bootstrap.py
git commit -m "feat(llm): COGNIFY_LLM_MODEL_BY_STEP builds a tiered pipeline model (AUTHOR-010)"
```

---

### Task 3: Bind the step name in `_wrap_node` even without a step repo

**Files:**
- Modify: `src/agents/content/pipeline.py`
- Test: `tests/unit/agents/content/test_pipeline_progress.py`

**Interfaces:** `_wrap_node(name, node_fn, deps)` keeps its signature. Without a step repo it now returns a wrapper that sets `current_step_name` to `f"content_{name}"` for the node's duration and resets it afterwards (with a step repo, `_record_step` already sets it).

- [ ] **Step 1: Failing test** — append to `test_pipeline_progress.py`:

```python
async def test_wrap_node_binds_step_name_without_step_repo() -> None:
    from src.utils.tracked_llm import current_step_name

    seen: list[str] = []

    async def node(state):  # type: ignore[no-untyped-def]
        seen.append(current_step_name.get())
        return {}

    wrapped = _wrap_node("draft", node, None)
    await wrapped({})  # type: ignore[misc]
    assert seen == ["content_draft"]
    assert current_step_name.get() == "unknown"
```

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/content/test_pipeline_progress.py -q` → FAIL (`seen == ["unknown"]`).

- [ ] **Step 2: Implement** — in `pipeline.py`, add above `_wrap_node`:

```python
def _bind_step_name(step_name: str, node_fn: object) -> object:
    """AUTHOR-010: bind the tracker's step contextvar even with no step repo."""
    from src.utils.tracked_llm import current_step_name

    async def bound(state: ContentState) -> dict:  # type: ignore[type-arg]
        token = current_step_name.set(step_name)
        try:
            return await node_fn(state)  # type: ignore[misc]
        finally:
            current_step_name.reset(token)

    return bound
```

and change the early return in `_wrap_node` from `return node_fn` to `return _bind_step_name(f"content_{name}", node_fn)`.

- [ ] **Step 3: Verify** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/agents/content -q` → all pass (the FakeLLM graph tests are unaffected: a bound contextvar changes nothing when the LLM isn't tiered).

- [ ] **Step 4: Commit**

```bash
git add src/agents/content/pipeline.py tests/unit/agents/content/test_pipeline_progress.py
git commit -m "feat(content): bind step name for tiering without a step repo (AUTHOR-010)"
```

---

### Task 4: `GET /settings/llm` exposes the effective tiering (read-only)

**Files:**
- Modify: `src/api/schemas/settings.py`, `src/api/routers/settings_config.py`
- Test: `tests/unit/api/test_settings_endpoints.py`

**Interfaces:** `LlmConfigResponse` gains `default_model: str = ""` and `model_by_step: dict[str, str] = {}`; both GET and PUT responses fill them from `request.app.state.settings` (`anthropic_model`, `llm_model_by_step`). `UpdateLlmConfigRequest` unchanged (fields are read-only). Decorator order on both routes fixed (route outermost).

- [ ] **Step 1: Failing tests** — inside `TestLlmConfigEndpoints` (the class holding `test_get_llm_config_ok`):

```python
    async def test_get_llm_config_includes_tiering_from_settings(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        settings_app.state.settings = auth_settings.model_copy(
            update={"llm_model_by_step": {"content_queries": "claude-haiku-4-5"}}
        )
        settings_app.state.settings_repos.llm.get_or_create = AsyncMock(
            return_value=LlmConfig()
        )
        resp = await settings_client.get(
            "/api/v1/settings/llm", headers=make_auth_header("admin", auth_settings)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["default_model"] == auth_settings.anthropic_model
        assert body["model_by_step"] == {"content_queries": "claude-haiku-4-5"}

    async def test_put_llm_config_ignores_tiering_fields(
        self,
        settings_client: httpx.AsyncClient,
        settings_app,
        auth_settings: Settings,
    ) -> None:
        settings_app.state.settings_repos.llm.get_or_create = AsyncMock(
            return_value=LlmConfig()
        )
        settings_app.state.settings_repos.llm.update = AsyncMock(return_value=LlmConfig())
        resp = await settings_client.put(
            "/api/v1/settings/llm",
            json={"model_by_step": {"content_draft": "x"}, "primary_model": "claude-opus-4"},
            headers=make_auth_header("admin", auth_settings),
        )
        assert resp.status_code == 200
        assert resp.json()["model_by_step"] == {}
```

Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_settings_endpoints.py -q` → the first fails (`KeyError: 'default_model'`).

- [ ] **Step 2: Implement**

`src/api/schemas/settings.py`:

```python
class LlmConfigResponse(BaseModel):
    primary_model: str
    drafting_model: str
    image_generation: str
    image_provider: str
    image_model: str | None = None
    # AUTHOR-010 — read-only, from COGNIFY_ANTHROPIC_MODEL / COGNIFY_LLM_MODEL_BY_STEP.
    default_model: str = ""
    model_by_step: dict[str, str] = {}
```

`src/api/routers/settings_config.py` — add a helper and use it in both handlers; swap the decorator order:

```python
def _llm_response(request: Request, config: object) -> LlmConfigResponse:
    settings = request.app.state.settings
    return LlmConfigResponse(
        **config.model_dump(),  # type: ignore[attr-defined]
        default_model=settings.anthropic_model,
        model_by_step=dict(settings.llm_model_by_step),
    )


# Route decorator OUTERMOST or slowapi never evaluates the limit (AUTHOR-006).
@settings_config_router.get("/settings/llm", response_model=LlmConfigResponse)
@limiter.limit("30/minute")
async def get_llm_config(...):
    config = await _get_repos(request).llm.get_or_create()
    return _llm_response(request, config)


@settings_config_router.put("/settings/llm", response_model=LlmConfigResponse)
@limiter.limit("30/minute")
async def update_llm_config(...):
    ...
    return _llm_response(request, saved)
```

- [ ] **Step 3: Verify** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_settings_endpoints.py -q` → all pass (existing LLM tests still pass because `model_dump()` of `LlmConfig` has no clashing keys).

- [ ] **Step 4: Commit**

```bash
git add src/api/schemas/settings.py src/api/routers/settings_config.py tests/unit/api/test_settings_endpoints.py
git commit -m "feat(api): /settings/llm exposes default_model + model_by_step read-only (AUTHOR-010)"
```

---

### Task 5: Frontend — types, hook mapping, `ModelTieringCard` in the LLM tab

**Files:**
- Create: `frontend/src/components/settings/model-tiering-card.tsx`, `frontend/src/components/settings/model-tiering-card.test.tsx`
- Modify: `frontend/src/types/settings.ts`, `frontend/src/hooks/use-settings.ts`, `frontend/src/hooks/use-settings.test.ts`, `frontend/src/components/settings/llm-config-tab.tsx`, `frontend/src/components/settings/llm-config-tab.test.tsx`

**Interfaces:**
- `LlmConfig` gains `defaultModel: string; modelByStep: Record<string, string>`; `ApiLlmConfig` gains `default_model?: string; model_by_step?: Record<string, string>`; `toLlmConfig` maps them (`?? ""`, `?? {}`); `DEFAULT_LLM_CONFIG` adds `defaultModel: "", modelByStep: {}`; `fromLlmConfig` unchanged.
- `ModelTieringCard({ defaultModel, modelByStep })` renders `data-testid="model-tiering-card"`: heading "Model tiering", the env var name, "Default model: {defaultModel}" (`data-testid="tiering-default-model"`), and either a table (`data-testid="tiering-row"` per entry, sorted by step) or the empty line "All steps use the default model." (`data-testid="tiering-empty"`).
- `LlmConfigTab` renders `<ModelTieringCard defaultModel={config.defaultModel} modelByStep={config.modelByStep} />` at the bottom.

- [ ] **Step 1: Failing tests**

`model-tiering-card.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ModelTieringCard } from "./model-tiering-card";

describe("ModelTieringCard", () => {
  it("shows the empty state when no steps are mapped", () => {
    render(<ModelTieringCard defaultModel="claude-sonnet-4-6" modelByStep={{}} />);
    expect(screen.getByTestId("tiering-default-model")).toHaveTextContent("claude-sonnet-4-6");
    expect(screen.getByTestId("tiering-empty")).toBeInTheDocument();
    expect(screen.queryAllByTestId("tiering-row")).toHaveLength(0);
  });

  it("lists mapped steps sorted by step name", () => {
    render(
      <ModelTieringCard
        defaultModel="claude-sonnet-4-6"
        modelByStep={{ content_validate: "claude-haiku-4-5", content_queries: "claude-haiku-4-5" }}
      />,
    );
    const rows = screen.getAllByTestId("tiering-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("content_queries");
    expect(rows[1]).toHaveTextContent("content_validate");
    expect(rows[0]).toHaveTextContent("claude-haiku-4-5");
    expect(screen.getByText(/COGNIFY_LLM_MODEL_BY_STEP/)).toBeInTheDocument();
  });
});
```

`llm-config-tab.test.tsx` — extend `mockConfig` to a complete `LlmConfig` (`imageProvider: "dalle_3", imageModel: null, defaultModel: "claude-sonnet-4-6", modelByStep: { content_queries: "claude-haiku-4-5" }`) and add:

```tsx
  it("renders the read-only model tiering card", () => {
    render(<LlmConfigTab config={mockConfig} onUpdate={vi.fn()} />);
    expect(screen.getByTestId("model-tiering-card")).toBeInTheDocument();
    expect(screen.getAllByTestId("tiering-row")).toHaveLength(1);
  });
```

`use-settings.test.ts` — extend `MOCK_LLM` with `default_model: "claude-sonnet-4-6", model_by_step: { content_queries: "claude-haiku-4-5" }` and add:

```ts
  it("maps model tiering fields from the API", async () => {
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.llmConfig.defaultModel).toBe("claude-sonnet-4-6"));
    expect(result.current.llmConfig.modelByStep).toEqual({ content_queries: "claude-haiku-4-5" });
  });
```

(match the file's existing `renderHook`/`waitFor` imports and how other tests await the initial load.)

Run: `cd frontend && npx vitest run src/components/settings src/hooks/use-settings.test.ts` → the three new cases fail.

- [ ] **Step 2: Implement**

`types/settings.ts`:

```ts
export interface LlmConfig {
  primaryModel: PrimaryModel;
  draftingModel: DraftingModel;
  imageGeneration: ImageModel;
  imageProvider: ImageProvider;
  imageModel: string | null;
  /** AUTHOR-010 — read-only, from COGNIFY_ANTHROPIC_MODEL / COGNIFY_LLM_MODEL_BY_STEP. */
  defaultModel: string;
  modelByStep: Record<string, string>;
}
```

`use-settings.ts` — `ApiLlmConfig` gets `default_model?: string; model_by_step?: Record<string, string>;`, `toLlmConfig` returns `defaultModel: api.default_model ?? "", modelByStep: api.model_by_step ?? {}`, `DEFAULT_LLM_CONFIG` gets `defaultModel: "", modelByStep: {}`.

`model-tiering-card.tsx`:

```tsx
"use client";

/** AUTHOR-010 — read-only view of the env-driven step → model map. */
export function ModelTieringCard({
  defaultModel,
  modelByStep,
}: {
  defaultModel: string;
  modelByStep: Record<string, string>;
}) {
  const rows = Object.entries(modelByStep).sort(([a], [b]) => a.localeCompare(b));
  return (
    <section
      data-testid="model-tiering-card"
      className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm"
    >
      <h3 className="font-heading text-base font-medium text-neutral-900">Model tiering</h3>
      <p className="mt-1 text-xs text-neutral-500">
        Set per step with <code className="font-mono">COGNIFY_LLM_MODEL_BY_STEP</code> (JSON map of
        tracked step name → model id). Read-only here.
      </p>
      <p data-testid="tiering-default-model" className="mt-3 text-sm text-neutral-700">
        Default model: <span className="font-mono">{defaultModel || "—"}</span>
      </p>
      {rows.length === 0 ? (
        <p data-testid="tiering-empty" className="mt-2 text-sm text-neutral-500">
          All steps use the default model.
        </p>
      ) : (
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="bg-neutral-50 text-left text-xs font-medium uppercase text-neutral-500">
              <th className="px-2 py-1">Step</th>
              <th className="px-2 py-1">Model</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([step, model]) => (
              <tr key={step} data-testid="tiering-row" className="border-b border-neutral-100">
                <td className="px-2 py-1 font-mono text-neutral-700">{step}</td>
                <td className="px-2 py-1 font-mono text-neutral-700">{model}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```

`llm-config-tab.tsx` — import `ModelTieringCard` and render it after the image-model block inside the `space-y-6` container:

```tsx
        <ModelTieringCard defaultModel={config.defaultModel} modelByStep={config.modelByStep} />
```

- [ ] **Step 3: Verify** — `cd frontend && npx vitest run && npx tsc --noEmit 2>&1 | grep -c "error TS"` → all green; the tsc count must be **≤ 13** (completing `mockConfig` may remove pre-existing errors — record the new number).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/settings.ts frontend/src/hooks/use-settings.ts frontend/src/hooks/use-settings.test.ts frontend/src/components/settings/model-tiering-card.tsx frontend/src/components/settings/model-tiering-card.test.tsx frontend/src/components/settings/llm-config-tab.tsx frontend/src/components/settings/llm-config-tab.test.tsx
git commit -m "feat(frontend): read-only model tiering card in Settings > LLM (AUTHOR-010)"
```

---

### Task 6: Verification, live smoke, docs, PR

- [ ] **Step 1: Backend gates** — `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/ -q` (≥ 1795 + ~16); `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`; `uv run mypy src/ --ignore-missing-imports 2>&1 | tail -1` (no new errors in touched files; baseline 116 in this venv).
- [ ] **Step 2: Frontend gates** — `cd frontend && npx vitest run && npm run lint && npx tsc --noEmit 2>&1 | grep -c "error TS"` → green, 0 eslint errors, tsc ≤ 13.
- [ ] **Step 3: Live smoke** (API in-process, same recipe as AUTHOR-009 — `--env-file D:/Workbench/github/cognify/.env`, `COGNIFY_DATABASE_URL=` blank, `COGNIFY_DEBUG=true`, `COGNIFY_MILVUS_URI=./smoke_milvus.db`, `COGNIFY_EMBEDDING_WARMUP=false`, plus `COGNIFY_LLM_MODEL_BY_STEP='{"section_regenerate":"claude-haiku-4-5-20251001"}'`): (a) boot log shows `llm_tiering_configured steps=['section_regenerate']`; (b) `GET /settings/llm` (admin) returns `default_model` + the map; (c) `POST /content/humanize-preview/stream` with a sloppy paragraph still reports `model=claude-sonnet-4-…` in its `pass` event (unmapped step → default); (d) run the same stream with the map key changed to a step that path uses — humanize preview binds no step, so instead verify routing with a mapped `content_queries` through a short outline-only session **only if** the stack is up; otherwise verify routing via the unit tests and record that the end-to-end model switch is deferred to the post-merge stack rebuild (check `llm_calls.model_name` for a `content_queries` row then).
- [ ] **Step 4: Docs** — PROGRESS.md row → Done + RESUME item 12 (what shipped, the scope decision, smoke results, follow-ups: wire Primary/Drafting dropdowns or remove them; editable per-step map after AUTHOR-012; `settings_config.py` other routes still have the dead limiter order; `use-settings.ts` > 200 lines); BACKLOG.md row DONE + counts (Epic 11 Done 12 / Remaining 5 / ~28 SP; velocity 398 SP); CLAUDE.md status sentence + Next action (PUBLISH-002 or Phase C AUTHOR-011); tick this plan.
- [ ] **Step 5: Commit + PR**

```bash
git add project-management/ CLAUDE.md docs/superpowers/plans/2026-08-28-author-010-model-tiering.md
git commit -m "docs: AUTHOR-010 done — progress/backlog/CLAUDE status"
git push -u origin feature/AUTHOR-010-model-tiering
gh pr create --base develop --title "AUTHOR-010: per-step model tiering (COGNIFY_LLM_MODEL_BY_STEP) + Settings display" --body-file <scratchpad>/pr-body-author-010.md
```

---

## Self-review

- **Spec coverage**: §5.8 "JSON map step→model, default `{}` = current single model" → Task 2 setting + builder; "`TrackedChatModel` factory reads it per node name" → Task 1 wrapper keyed on the tracker's contextvar, wrapped inside `TrackedChatModel` (Task 2 `_build_llm`); Phase B row "+ Settings display" → Tasks 4–5; review #14's example (Haiku for queries/validate) → `.env.example` recommendation. Task 3 closes the no-DB gap so the map applies wherever the tracker's step names do.
- **Placeholders**: none; every step has code or an exact edit.
- **Type consistency**: `TieredChatModel.by_step`/`default` names match Task 2's builder and tests; `KNOWN_LLM_STEPS` used by the builder's warning; response fields `default_model`/`model_by_step` match `ApiLlmConfig` → `defaultModel`/`modelByStep` → `ModelTieringCard` props; test ids in Task 5 tests match the card.
