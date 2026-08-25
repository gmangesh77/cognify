# AUTHOR-008: Length Target + Content Type Through the Outliner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** The session's `length_target` (`short|medium|long|pillar`) and `content_type` (`article|how-to|analysis|report`) — collected since AUTHOR-003 but never consumed — drive the outliner's per-section word budgets and structure guidance, and the downstream word-count guardrails become budget-aware instead of hardcoded 200/500/1500.

**Architecture:** No contract change — `OutlineSection.target_word_count` and `ArticleOutline.total_target_words` already exist; the work is (a) seeding two new `ContentState` keys from the session, (b) a `length_budgets` module (defaults + `COGNIFY_LENGTH_BUDGETS_JSON` overrides, mirroring the AUTHOR-005 pricing pattern), (c) a dynamic Requirements block + content-type guidance in the outline prompt, (d) outline-derived (not settings-derived) warn/expansion bands in `validate.py` and `section_drafter.py` so no extra settings threading is needed downstream, (e) a word-budget chip in the outline review UI.

**Tech Stack:** Python 3.12 / LangGraph / pydantic-settings; React 19 + Vitest.

**Spec:** program plan `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §4.1 (length_target → "word budgets in settings") + review `docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md` §6 #8 ("thread to outliner (word budgets per section like ImpactAI's `_normalize_section_budgets`)").

## Global Constraints

- Functions < 20 lines, files < 200 lines, max 3 params; named exports; mypy strict.
- `ContentType` values are `article`, **`how-to`** (hyphen!), `analysis`, `report` (`src/models/content.py:16`). `LengthTarget = Literal["short","medium","long","pillar"]` (`src/models/brief.py:24`).
- Absent/unknown `length_target` MUST behave exactly like today (medium = 4-8 sections, 200-500/section, 1500-3000 total) — every existing article/session has `length_target=None`.
- Do NOT add fields to `OutlineSection`/`ArticleOutline` (frozen models; huge consumer surface incl. hand-mirrored `src/api/schemas/articles.py` and JSONB backcompat).
- L-012: read `session.length_target`/`session.content_type` only in `build_initial_state` — never the brief.

---

### Task 1: `length_budgets` module + settings override

**Files:**
- Create: `src/agents/content/length_budgets.py`
- Modify: `src/config/settings.py` (next to `llm_pricing_json`)
- Test: `tests/unit/agents/content/test_length_budgets.py`

**Interfaces:**
- Produces: `LengthBudget = dict[str, int]`; `DEFAULT_LENGTH_BUDGETS: dict[str, LengthBudget]`; `budget_for(length_target: str | None, overrides: dict[str, dict[str, int]]) -> LengthBudget`; `content_type_guidance(content_type: str | None) -> str | None`; settings field `length_budgets_json: dict[str, dict[str, int]] = {}`.

- [x] **Step 1: Write the failing tests**

```python
"""Tests for length-target word budgets (AUTHOR-008)."""

from src.agents.content.length_budgets import (
    DEFAULT_LENGTH_BUDGETS,
    budget_for,
    content_type_guidance,
)

_KEYS = {"sections_min", "sections_max", "section_min", "section_max", "total_min", "total_max"}


class TestDefaults:
    def test_all_four_targets_have_complete_budgets(self) -> None:
        assert set(DEFAULT_LENGTH_BUDGETS) == {"short", "medium", "long", "pillar"}
        for budget in DEFAULT_LENGTH_BUDGETS.values():
            assert set(budget) == _KEYS

    def test_medium_matches_legacy_hardcoded_numbers(self) -> None:
        m = DEFAULT_LENGTH_BUDGETS["medium"]
        assert (m["sections_min"], m["sections_max"]) == (4, 8)
        assert (m["section_min"], m["section_max"]) == (200, 500)
        assert (m["total_min"], m["total_max"]) == (1500, 3000)

    def test_budgets_scale_monotonically(self) -> None:
        order = ["short", "medium", "long", "pillar"]
        totals = [DEFAULT_LENGTH_BUDGETS[k]["total_max"] for k in order]
        assert totals == sorted(totals)


class TestBudgetFor:
    def test_none_falls_back_to_medium(self) -> None:
        assert budget_for(None, {}) == DEFAULT_LENGTH_BUDGETS["medium"]

    def test_unknown_falls_back_to_medium(self) -> None:
        assert budget_for("epic", {}) == DEFAULT_LENGTH_BUDGETS["medium"]

    def test_override_merges_per_key_not_wholesale(self) -> None:
        merged = budget_for("long", {"long": {"total_max": 6000}})
        assert merged["total_max"] == 6000
        assert merged["section_min"] == DEFAULT_LENGTH_BUDGETS["long"]["section_min"]

    def test_override_for_other_target_is_ignored(self) -> None:
        assert budget_for("short", {"long": {"total_max": 6000}}) == DEFAULT_LENGTH_BUDGETS["short"]


class TestContentTypeGuidance:
    def test_article_and_none_yield_no_guidance(self) -> None:
        assert content_type_guidance("article") is None
        assert content_type_guidance(None) is None

    def test_how_to_analysis_report_have_guidance(self) -> None:
        for ct in ("how-to", "analysis", "report"):
            text = content_type_guidance(ct)
            assert text and len(text) > 20
```

- [x] **Step 2: Run to verify failure** — `uv run pytest tests/unit/agents/content/test_length_budgets.py -q` → FAIL (module missing).

- [x] **Step 3: Implement `src/agents/content/length_budgets.py`**

```python
"""Length-target word budgets for the outliner (AUTHOR-008).

Defaults live here (next to the consumer); ``COGNIFY_LENGTH_BUDGETS_JSON``
in settings holds sparse per-key overrides, merged two-level so
``{"long": {"total_max": 6000}}`` keeps long's other numbers.
"""

from __future__ import annotations

LengthBudget = dict[str, int]

DEFAULT_LENGTH_BUDGETS: dict[str, LengthBudget] = {
    "short": {
        "sections_min": 3, "sections_max": 5,
        "section_min": 150, "section_max": 350,
        "total_min": 800, "total_max": 1200,
    },
    "medium": {
        "sections_min": 4, "sections_max": 8,
        "section_min": 200, "section_max": 500,
        "total_min": 1500, "total_max": 3000,
    },
    "long": {
        "sections_min": 6, "sections_max": 10,
        "section_min": 400, "section_max": 700,
        "total_min": 3000, "total_max": 5000,
    },
    "pillar": {
        "sections_min": 8, "sections_max": 12,
        "section_min": 500, "section_max": 900,
        "total_min": 5000, "total_max": 8000,
    },
}

_CONTENT_TYPE_GUIDANCE: dict[str, str] = {
    "how-to": (
        "Structure as a practical how-to guide: after a short introduction, "
        "each section is a sequential, actionable step with concrete "
        "instructions; end with common pitfalls or next steps."
    ),
    "analysis": (
        "Structure as an analysis: open with the thesis, dedicate sections "
        "to supporting evidence, address counterpoints, close with "
        "implications."
    ),
    "report": (
        "Structure as a report: lead with key findings, follow with "
        "data-driven detail sections, close with outlook and "
        "recommendations."
    ),
}


def budget_for(
    length_target: str | None,
    overrides: dict[str, dict[str, int]],
) -> LengthBudget:
    """Resolve the budget for a length target; unknown/None -> medium."""
    key = length_target if length_target in DEFAULT_LENGTH_BUDGETS else "medium"
    return {**DEFAULT_LENGTH_BUDGETS[key], **overrides.get(key, {})}


def content_type_guidance(content_type: str | None) -> str | None:
    """Structural prompt guidance per content type; None for article/default."""
    if content_type is None:
        return None
    return _CONTENT_TYPE_GUIDANCE.get(content_type)
```

- [x] **Step 4: Add the settings field** in `src/config/settings.py` right after `llm_pricing_json`:

```python
    # Length-target word-budget overrides for the outliner, keyed by
    # length target; merged per-key over
    # agents.content.length_budgets.DEFAULT_LENGTH_BUDGETS.
    # Env: COGNIFY_LENGTH_BUDGETS_JSON='{"long": {"total_max": 6000}}'
    length_budgets_json: dict[str, dict[str, int]] = {}
```

- [x] **Step 5: Run tests** — module tests PASS; `uv run pytest tests/unit/config/ -q` still green.
- [x] **Step 6: Commit** — `feat(content): length-target word budgets with settings overrides (AUTHOR-008)`

### Task 2: Seed `content_type` / `length_target` into the graph state

**Files:**
- Modify: `src/agents/content/pipeline.py` (`ContentState`), `src/services/content/graph_state.py`
- Test: `tests/unit/services/test_graph_state.py`

**Interfaces:**
- Produces: `state["content_type"]: str | None`, `state["length_target"]: str | None` available to all nodes.

- [x] **Step 1: Failing test** (template: `test_build_initial_state_seeds_audience_persona_and_brief_id` in the same file)

```python
def test_build_initial_state_seeds_content_type_and_length_target() -> None:
    session = _make_session(content_type="how-to", length_target="pillar")
    state = build_initial_state(session, _topic(), [])
    assert state["content_type"] == "how-to"
    assert state["length_target"] == "pillar"
```

(Adapt `_make_session`/`_topic` to the file's existing helpers — extend the existing session fixture with the two kwargs.)

- [x] **Step 2: Run to verify failure** — KeyError.
- [x] **Step 3: Implement** — in `ContentState` add:

```python
    # AUTHOR-008 — editorial sizing, consumed by the outline node.
    content_type: NotRequired[str | None]
    length_target: NotRequired[str | None]
```

and in `build_initial_state` (after `"keywords"`):

```python
        "content_type": session.content_type,
        "length_target": session.length_target,
```

- [x] **Step 4: Run** — `uv run pytest tests/unit/services/test_graph_state.py -q` PASS.
- [x] **Step 5: Commit** — `feat(content): seed content_type/length_target into graph state (AUTHOR-008)`

### Task 3: Budget-aware outline prompt

**Files:**
- Modify: `src/agents/content/outline_generator.py`, `src/agents/content/nodes.py` (`make_outline_node`), `src/agents/content/pipeline.py` (pass settings)
- Test: `tests/unit/agents/content/test_outline_generator.py`

**Interfaces:**
- Consumes: `budget_for`, `content_type_guidance` (Task 1); state keys (Task 2).
- Produces: `OutlineContext` gains `content_type: str | None = None` and `budget: LengthBudget | None = None`; `make_outline_node(llm, settings=None)`.

- [x] **Step 1: Failing tests** (use the file's existing `_CapturingLLM` + `_outline_json` helpers)

```python
class TestBudgetPrompt:
    @pytest.mark.asyncio
    async def test_pillar_budget_lines_in_prompt(self) -> None:
        llm = _CapturingLLM(responses=[_outline_json(8)])
        ctx = OutlineContext(budget=DEFAULT_LENGTH_BUDGETS["pillar"])
        await generate_outline(_topic(), _findings(), llm, ctx)
        prompt = llm.captured
        assert "8-12 sections" in prompt
        assert "500-900 target words" in prompt
        assert "Total: 5000-8000 words" in prompt

    @pytest.mark.asyncio
    async def test_no_ctx_keeps_legacy_medium_numbers(self) -> None:
        llm = _CapturingLLM(responses=[_outline_json(4)])
        await generate_outline(_topic(), _findings(), llm, None)
        assert "4-8 sections" in llm.captured
        assert "200-500 target words" in llm.captured
        assert "Total: 1500-3000 words" in llm.captured

    @pytest.mark.asyncio
    async def test_content_type_guidance_and_pin_in_prompt(self) -> None:
        llm = _CapturingLLM(responses=[_outline_json(4)])
        ctx = OutlineContext(content_type="how-to")
        await generate_outline(_topic(), _findings(), llm, ctx)
        assert "how-to guide" in llm.captured
        assert 'Set "content_type" to "how-to"' in llm.captured

    @pytest.mark.asyncio
    async def test_article_content_type_adds_no_guidance(self) -> None:
        llm = _CapturingLLM(responses=[_outline_json(4)])
        ctx = OutlineContext(content_type="article")
        await generate_outline(_topic(), _findings(), llm, ctx)
        assert "Set \"content_type\"" not in llm.captured
```

- [x] **Step 2: Run to verify failure** — unknown kwargs on `OutlineContext`.
- [x] **Step 3: Implement in `outline_generator.py`:**
  - Extend the dataclass: `content_type: str | None = None`, `budget: LengthBudget | None = None` (import `LengthBudget`, `DEFAULT_LENGTH_BUDGETS`, `content_type_guidance` from `.length_budgets`).
  - Replace the static requirements lines in `_USER_TEMPLATE` with a `{requirements}` placeholder; keep the `Requirements:\n` heading INSIDE the generated block so the existing context-lines splice keeps working unchanged:

```python
_USER_TEMPLATE = (
    "Generate an article outline for this topic:\n\n"
    "Title: {title}\n"
    "Description: {description}\n"
    "Domain: {domain}\n\n"
    "Research findings:\n{findings_summary}\n\n"
    "{requirements}\n"
    "Return JSON: {schema_hint}"
)


def _requirements_block(ctx: OutlineContext | None) -> str:
    """Render the sizing requirements from the resolved budget."""
    b = ctx.budget if ctx is not None and ctx.budget else DEFAULT_LENGTH_BUDGETS["medium"]
    lines = [
        "Requirements:",
        f"- {b['sections_min']}-{b['sections_max']} sections ordered for narrative flow",
        f"- Each section: {b['section_min']}-{b['section_max']} target words",
        f"- Total: {b['total_min']}-{b['total_max']} words",
        "- Map each section to relevant facet indices",
    ]
    if ctx is not None and ctx.content_type and ctx.content_type != "article":
        lines.append(f'- Set "content_type" to "{ctx.content_type}"')
    return "\n".join(lines) + "\n"
```

  - In `_build_context_lines`, append the guidance line (before the instruction line):

```python
    guidance = content_type_guidance(ctx.content_type)
    if guidance:
        context_lines.append(guidance)
```

  - In `generate_outline`, pass `requirements=_requirements_block(ctx)` into the format call. The `user_msg.replace("Requirements:\n", ...)` splice still matches because the block starts with that literal.
- [x] **Step 4: `make_outline_node(llm, settings=None)`** in `nodes.py` — resolve budget from state + settings and extend the ctx:

```python
def make_outline_node(
    llm: BaseChatModel,
    settings: Settings | None = None,
) -> Any:  # noqa: ANN401
    """Factory for the outline generation node."""
    overrides = settings.length_budgets_json if settings else {}

    async def outline_node(state: ContentState) -> dict[str, object]:
        ...
        ctx = OutlineContext(
            target_audience=state.get("target_audience"),
            preferred_angle=state.get("preferred_angle"),
            content_tone=state.get("content_tone"),
            keywords=state.get("keywords"),
            instruction=state.get("outline_instruction"),
            content_type=state.get("content_type"),
            budget=budget_for(state.get("length_target"), overrides),
        )
```

(import `budget_for` + `Settings`; `Settings` is already imported by `pipeline.py` — in `nodes.py` import under TYPE_CHECKING if needed, or plainly.)
- [x] **Step 5:** `pipeline.py:172` — `make_outline_node(llm, settings)`.
- [x] **Step 6: Node-level test** in `test_outline_generator.py` or `tests/unit/agents/content/test_pipeline.py`: state with `length_target="short"` → capturing LLM prompt contains `"3-5 sections"`. Simplest as a direct `make_outline_node` invocation test with a minimal state dict.
- [x] **Step 7: Run** — outline generator + pipeline + outline-gate + content-service test files. All green.
- [x] **Step 8: Commit** — `feat(content): budget + content-type aware outline prompt (AUTHOR-008)`

### Task 4: Outline-derived guardrails (validate + drafter warning)

**Files:**
- Modify: `src/agents/content/validate.py`, `src/agents/content/nodes.py` (`make_validate_node` call site), `src/agents/content/section_drafter.py` (`_log_word_count`)
- Test: extend the validate tests (`tests/unit/agents/content/test_validate.py` if present, else where `validate_drafts` is tested) + `tests/unit/agents/content/test_section_drafter.py`

**Interfaces:**
- Produces: `validate_drafts(drafts, outline: ArticleOutline | None = None)` — expansion threshold `max(0.6 × outline.total_target_words, ...)` when outline given, legacy 1500 otherwise; per-section warn band `0.5–1.5 × section target` when outline given, legacy 200/500 otherwise. `_log_word_count` warns outside `0.5–1.5 × section.target_word_count`.

- [x] **Step 1: Failing tests**

```python
class TestBudgetAwareValidation:
    def test_pillar_outline_raises_expansion_threshold(self) -> None:
        # 6 drafts x 400 words = 2400 — fine under legacy 1500 rule,
        # but a 6000-word pillar outline should demand expansion.
        outline = _outline_with(total_target_words=6000, section_targets=[750] * 6)
        drafts = [_draft(i, words=400) for i in range(6)]
        result = validate_drafts(drafts, outline)
        assert result.needs_expansion is True

    def test_no_outline_keeps_legacy_1500_threshold(self) -> None:
        drafts = [_draft(i, words=400) for i in range(4)]  # 1600 total
        assert validate_drafts(drafts).needs_expansion is False

    def test_short_outline_does_not_demand_1500(self) -> None:
        outline = _outline_with(total_target_words=900, section_targets=[300] * 3)
        drafts = [_draft(i, words=250) for i in range(3)]  # 750 >= 0.6*900
        assert validate_drafts(drafts, outline).needs_expansion is False
```

(`_outline_with` / `_draft` are small local fixture builders — construct real `ArticleOutline`/`SectionDraft` instances mirroring the file's existing fixtures.)

Drafter test (`test_section_drafter.py`): `_log_word_count` with a 900-target section and 700 words does NOT warn; with 300 words DOES warn (patch `logger.warning` or capture via structlog `capture_logs`; follow existing test style in the file).

- [x] **Step 2: Run to verify failure.**
- [x] **Step 3: Implement** in `validate.py`:

```python
def validate_drafts(
    drafts: list[SectionDraft],
    outline: ArticleOutline | None = None,
) -> ValidationResult:
    total = sum(d.word_count for d in drafts)
    citations = _deduplicate_citations(drafts)
    shortest = _find_shortest(drafts)
    floor = _expansion_floor(outline)
    result = ValidationResult(
        total_word_count=total,
        all_citations=citations,
        needs_expansion=total < floor,
        shortest_index=shortest,
    )
    _log_section_warnings(drafts, outline)
    _log_validation_result(drafts, result, floor)
    return result


def _expansion_floor(outline: ArticleOutline | None) -> int:
    """Words below which the article needs expansion (AUTHOR-008)."""
    if outline is None or outline.total_target_words <= 0:
        return _MIN_TOTAL_WORDS
    return int(outline.total_target_words * 0.6)


def _section_band(
    outline: ArticleOutline | None,
    section_index: int,
) -> tuple[int, int]:
    """Acceptable word band for one section: 0.5-1.5x its outline target."""
    if outline is not None:
        for s in outline.sections:
            if s.index == section_index and s.target_word_count > 0:
                return (s.target_word_count // 2, s.target_word_count * 3 // 2)
    return (200, 500)
```

`_log_section_warnings(drafts, outline)` uses `_section_band`; `_log_validation_result` logs `target=floor`. Import `ArticleOutline`.
- [x] **Step 4:** `make_validate_node`'s `validate_node` passes the outline: `result = validate_drafts(drafts, _coerce_outline(state))`.
- [x] **Step 5:** `section_drafter._log_word_count` — replace `if wc < 200 or wc > 500:` with a band from the section's own target:

```python
    lo, hi = section.target_word_count // 2, section.target_word_count * 3 // 2
    if section.target_word_count <= 0:
        lo, hi = 200, 500
    if wc < lo or wc > hi:
```

- [x] **Step 6: Run** the two test files + `tests/unit/agents/content/test_pipeline.py` (redraft path uses `validate_drafts` — its `_full_pipeline_responses` outlines have targets, verify no behavior change breaks the redraft test).
- [x] **Step 7: Commit** — `feat(content): outline-derived word-count guardrails (AUTHOR-008)`

### Task 5: Frontend — word-budget chip + smarter new-section default

**Files:**
- Modify: `frontend/src/components/research/outline-section-editor.tsx` (chip in header row), `frontend/src/components/research/outline-review-step.tsx` (`newSection` default + total line)
- Test: `frontend/src/components/research/outline-section-editor.test.tsx`, `outline-review-step.test.tsx`

**Interfaces:**
- Consumes: `section.target_word_count`, `outline.total_target_words` (already in `types/research.ts` — no type change).

- [x] **Step 1: Failing tests**

```tsx
// outline-section-editor.test.tsx
it("shows the section word budget", () => {
  renderEditor({ ...baseSection, target_word_count: 450 });
  expect(screen.getByText("~450 words")).toBeInTheDocument();
});

// outline-review-step.test.tsx
it("defaults a new section's budget to the outline average", async () => {
  // baseOutline sections all target_word_count 300 → average 300
  render(<OutlineReviewStep {...props} />);
  await userEvent.click(screen.getByRole("button", { name: /add section/i }));
  // saving propagates the outline; assert the added section carries 300
  ...assert via the onChange/updateOutline mock per the file's existing pattern
});
```

(Adapt precisely to each file's existing render helpers/mocks.)
- [x] **Step 2: Run to verify failure** — `cd frontend && npx vitest run src/components/research`.
- [x] **Step 3: Implement:**
  - `outline-section-editor.tsx` header row (next to the reorder buttons): `<span className="text-xs font-medium text-neutral-500">~{section.target_word_count} words</span>` (design tokens per DESIGN.md caption scale; no new colors).
  - `outline-review-step.tsx`: `newSection(sections)` — average of existing `target_word_count`s rounded to nearest 50, fallback 300:

```tsx
function averageBudget(sections: OutlineSection[]): number {
  if (sections.length === 0) return 300;
  const avg = sections.reduce((n, s) => n + s.target_word_count, 0) / sections.length;
  return Math.max(50, Math.round(avg / 50) * 50);
}
```

  - Optional single line near the outline title: `Total target: ~{outline.total_target_words} words` (`text-xs text-neutral-500`), if it fits without layout churn.
- [x] **Step 4: Run** — the two test files, then the full frontend suite.
- [x] **Step 5: Commit** — `feat(frontend): word-budget chip + budget-aware add-section (AUTHOR-008)`

### Task 6: Full verification + docs

- [x] **Step 1:** `uv run pytest tests/unit/ -q` (blank `COGNIFY_ANTHROPIC_API_KEY` — no `.env` in this worktree) — 0 failures.
- [x] **Step 2:** `cd frontend && npx vitest run` — 0 failures; `npx tsc --noEmit` — only the 13 pre-existing errors.
- [x] **Step 3:** `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`.
- [x] **Step 4:** Update `project-management/PROGRESS.md` (AUTHOR-008 row → Done + RESUME item) and `BACKLOG.md` (velocity +3 SP), check plan checkboxes.
- [x] **Step 5:** Request code review (requesting-code-review skill), fix findings.
- [ ] **Step 6:** Live smoke after stack rebuild: generate with length=Short → outline review shows 3-5 sections with ~150-350 budgets; generate with content type=How-to → step-shaped section titles; article totals in band.
- [ ] **Step 7:** Push + PR to develop.
