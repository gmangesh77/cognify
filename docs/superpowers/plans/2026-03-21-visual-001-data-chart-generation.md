# VISUAL-001: Data Chart Generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic data chart generation to the content pipeline — LLM proposes chart specs from drafted sections, Matplotlib renders them to transparent PNGs, and the resulting `ImageAsset` objects populate `CanonicalArticle.visuals`.

**Architecture:** New pipeline node `generate_charts` runs after `seo_optimize`. LLM reads section drafts → proposes 0-3 `ChartSpec` JSON objects → Matplotlib renders each to PNG → `ImageAsset` list flows through `ArticleDraft.visuals` → `assemble_canonical_article()`. Best-effort: pipeline succeeds even with zero charts.

**Tech Stack:** Python 3.12, Matplotlib, LangChain BaseChatModel, Pydantic, structlog, pytest

**Spec:** `docs/superpowers/specs/2026-03-21-visual-001-data-chart-generation-design.md`

**Baseline:** 697 backend tests passing (1 pre-existing integration error in `test_research_flow.py`).

**Worktree:** `D:/Workbench/github/cognify-visual-001` on branch `feature/VISUAL-001-data-chart-generation`

---

## File Structure

### New Files

| File | Responsibility | ~Lines |
|------|---------------|--------|
| `src/models/visual.py` | `ChartType` enum, `ChartSpec` model | ~30 |
| `src/agents/content/chart_generator.py` | `propose_charts()` and `render_chart()` | ~120 |
| `tests/unit/models/test_visual_models.py` | ChartSpec model validation tests | ~50 |
| `tests/unit/agents/content/test_chart_generator.py` | propose + render tests | ~130 |
| `tests/unit/agents/content/test_chart_node.py` | Pipeline node integration tests | ~70 |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `matplotlib>=3.8.0` |
| `src/config/settings.py:84` | Add `chart_output_dir: str` |
| `src/models/content_pipeline.py:127` | Add `visuals` field to `ArticleDraft` |
| `src/agents/content/pipeline.py:37-52` | Add `visuals` to `ContentState` |
| `src/agents/content/pipeline.py:74,89-90` | Add chart node, rewire `seo_optimize` → `generate_charts` → `END` |
| `src/agents/content/nodes.py` | Add `make_chart_node()` factory |
| `src/services/content.py:207-217` | Add `visuals` to `_store_drafted()` |
| `src/agents/content/article_assembler.py:21-45` | Accept `visuals` param |
| `src/services/content_finalize.py:65-70` | Pass `draft.visuals` to assembler |
| `tests/unit/agents/content/test_article_assembler.py` | Add visuals test |

---

## Task 1: Add Matplotlib Dependency and Settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/config/settings.py`

- [ ] **Step 1: Add matplotlib to pyproject.toml**

In `pyproject.toml`, add to the `dependencies` list:

```
"matplotlib>=3.8.0",
```

- [ ] **Step 2: Add chart_output_dir to Settings**

In `src/config/settings.py`, after line 83 (`embedding_version`), add:

```python
    # Chart generation
    chart_output_dir: str = "generated_assets/charts"
```

- [ ] **Step 3: Install dependency**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv sync --dev`

- [ ] **Step 4: Verify import works**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run python -c "import matplotlib; print(matplotlib.__version__)"`
Expected: Version number printed (3.8+).

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-001
git add pyproject.toml uv.lock src/config/settings.py
git commit -m "chore(visual-001): add matplotlib dependency and chart_output_dir setting"
```

---

## Task 2: ChartSpec and ChartType Models

**Files:**
- Create: `tests/unit/models/test_visual_models.py`
- Create: `src/models/visual.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/unit/models/test_visual_models.py`:

```python
"""Tests for visual asset models."""

import pytest

from src.models.visual import ChartSpec, ChartType


class TestChartType:
    def test_enum_values(self) -> None:
        assert ChartType.BAR == "bar"
        assert ChartType.LINE == "line"
        assert ChartType.PIE == "pie"

    def test_enum_has_exactly_three_members(self) -> None:
        assert len(ChartType) == 3


class TestChartSpec:
    def test_valid_bar_spec(self) -> None:
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            title="Attack Types",
            x_labels=["Injection", "Poisoning", "Evasion"],
            y_values=[45.0, 30.0, 25.0],
            y_label="Percentage",
            caption="Distribution of AI attack types in 2026.",
            source_section_index=0,
        )
        assert spec.chart_type == ChartType.BAR
        assert len(spec.x_labels) == 3

    def test_valid_line_spec(self) -> None:
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            title="Growth Over Time",
            x_labels=["Q1", "Q2", "Q3", "Q4"],
            y_values=[10.0, 25.0, 40.0, 55.0],
            y_label="Incidents",
            caption="Quarterly incident growth.",
            source_section_index=1,
        )
        assert spec.chart_type == ChartType.LINE

    def test_valid_pie_spec(self) -> None:
        spec = ChartSpec(
            chart_type=ChartType.PIE,
            title="Budget Allocation",
            x_labels=["Defense", "Monitoring", "Training"],
            y_values=[50.0, 30.0, 20.0],
            y_label="Percentage",
            caption="Security budget breakdown.",
            source_section_index=2,
        )
        assert spec.chart_type == ChartType.PIE

    def test_rejects_empty_title(self) -> None:
        with pytest.raises(ValueError):
            ChartSpec(
                chart_type=ChartType.BAR,
                title="",
                x_labels=["A", "B"],
                y_values=[1.0, 2.0],
                y_label="Y",
                caption="Test.",
                source_section_index=0,
            )

    def test_rejects_single_label(self) -> None:
        with pytest.raises(ValueError):
            ChartSpec(
                chart_type=ChartType.BAR,
                title="Test",
                x_labels=["Only"],
                y_values=[1.0],
                y_label="Y",
                caption="Test.",
                source_section_index=0,
            )

    def test_rejects_negative_section_index(self) -> None:
        with pytest.raises(ValueError):
            ChartSpec(
                chart_type=ChartType.BAR,
                title="Test",
                x_labels=["A", "B"],
                y_values=[1.0, 2.0],
                y_label="Y",
                caption="Test.",
                source_section_index=-1,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/unit/models/test_visual_models.py -v 2>&1 | tail -15`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement models**

Create `src/models/visual.py`:

```python
"""Models for visual asset generation (charts, diagrams)."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ChartType(StrEnum):
    """Supported chart types for data visualization."""

    BAR = "bar"
    LINE = "line"
    PIE = "pie"


class ChartSpec(BaseModel, frozen=True):
    """LLM-proposed chart specification."""

    chart_type: ChartType
    title: str = Field(min_length=1, max_length=120)
    x_labels: list[str] = Field(min_length=2, max_length=12)
    y_values: list[float] = Field(min_length=2, max_length=12)
    y_label: str = Field(min_length=1, max_length=60)
    caption: str = Field(min_length=1, max_length=200)
    source_section_index: int = Field(ge=0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/unit/models/test_visual_models.py -v 2>&1 | tail -15`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-001
git add src/models/visual.py tests/unit/models/test_visual_models.py
git commit -m "feat(visual-001): add ChartType enum and ChartSpec model"
```

---

## Task 3: Chart Generator — propose_charts and render_chart

**Files:**
- Create: `tests/unit/agents/content/test_chart_generator.py`
- Create: `src/agents/content/chart_generator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/agents/content/test_chart_generator.py`:

```python
"""Tests for chart generation — LLM proposal and Matplotlib rendering."""

import json
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agents.content.chart_generator import propose_charts, render_chart
from src.models.content_pipeline import SectionDraft
from src.models.visual import ChartSpec, ChartType


def _make_section(index: int, body: str) -> SectionDraft:
    return SectionDraft(
        section_index=index,
        title=f"Section {index}",
        body_markdown=body,
        word_count=len(body.split()),
        citations_used=[],
    )


def _make_llm_response(specs: list[dict]) -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke.return_value = AsyncMock(content=json.dumps(specs))
    return llm


VALID_BAR_SPEC = {
    "chart_type": "bar",
    "title": "Attack Frequency",
    "x_labels": ["Injection", "Poisoning", "Evasion"],
    "y_values": [45.0, 30.0, 25.0],
    "y_label": "Count",
    "caption": "Most common attack vectors.",
    "source_section_index": 0,
}

VALID_LINE_SPEC = {
    "chart_type": "line",
    "title": "Quarterly Growth",
    "x_labels": ["Q1", "Q2", "Q3", "Q4"],
    "y_values": [10.0, 25.0, 40.0, 55.0],
    "y_label": "Incidents",
    "caption": "Incident count by quarter.",
    "source_section_index": 1,
}


class TestProposeCharts:
    @pytest.mark.asyncio
    async def test_returns_valid_specs(self) -> None:
        llm = _make_llm_response([VALID_BAR_SPEC, VALID_LINE_SPEC])
        sections = [_make_section(0, "Attacks increased 45%."), _make_section(1, "Growth data.")]
        result = await propose_charts(sections, llm)
        assert len(result) == 2
        assert result[0].chart_type == ChartType.BAR
        assert result[1].chart_type == ChartType.LINE

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_array(self) -> None:
        llm = _make_llm_response([])
        sections = [_make_section(0, "No data here.")]
        result = await propose_charts(sections, llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_for_malformed_json(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = AsyncMock(content="not valid json")
        sections = [_make_section(0, "Some text.")]
        result = await propose_charts(sections, llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_discards_invalid_keeps_valid(self) -> None:
        invalid_spec = {**VALID_BAR_SPEC, "title": ""}
        llm = _make_llm_response([invalid_spec, VALID_LINE_SPEC])
        sections = [_make_section(0, "Text."), _make_section(1, "More.")]
        result = await propose_charts(sections, llm)
        assert len(result) == 1
        assert result[0].chart_type == ChartType.LINE

    @pytest.mark.asyncio
    async def test_discards_mismatched_lengths(self) -> None:
        bad_spec = {**VALID_BAR_SPEC, "y_values": [1.0, 2.0]}  # 3 labels, 2 values
        llm = _make_llm_response([bad_spec])
        sections = [_make_section(0, "Text.")]
        result = await propose_charts(sections, llm)
        assert result == []


class TestRenderChart:
    def test_renders_bar_chart_to_png(self, tmp_path: Path) -> None:
        spec = ChartSpec.model_validate(VALID_BAR_SPEC)
        session_id = uuid4()
        result = render_chart(spec, str(tmp_path), session_id)
        assert result is not None
        assert Path(result.url).exists()
        assert Path(result.url).suffix == ".png"
        assert result.caption == spec.caption
        assert result.alt_text == spec.title

    def test_renders_line_chart_to_png(self, tmp_path: Path) -> None:
        spec = ChartSpec.model_validate(VALID_LINE_SPEC)
        result = render_chart(spec, str(tmp_path), uuid4())
        assert result is not None
        assert Path(result.url).exists()

    def test_renders_pie_chart_to_png(self, tmp_path: Path) -> None:
        pie_spec = ChartSpec(
            chart_type=ChartType.PIE,
            title="Budget Split",
            x_labels=["Defense", "Ops"],
            y_values=[60.0, 40.0],
            y_label="Pct",
            caption="Budget allocation.",
            source_section_index=0,
        )
        result = render_chart(pie_spec, str(tmp_path), uuid4())
        assert result is not None
        assert Path(result.url).exists()

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        spec = ChartSpec.model_validate(VALID_BAR_SPEC)
        session_id = uuid4()
        output_dir = tmp_path / "nested" / "charts"
        result = render_chart(spec, str(output_dir), session_id)
        assert result is not None
        assert output_dir.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/unit/agents/content/test_chart_generator.py -v 2>&1 | tail -15`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement chart_generator.py**

Create `src/agents/content/chart_generator.py`:

```python
"""Chart generation from article section drafts.

LLM proposes chart specifications, Matplotlib renders to PNG.
Best-effort: failures are logged and skipped, never crash the pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import matplotlib
import matplotlib.pyplot as plt
import structlog
from pydantic import ValidationError

from src.models.content import ImageAsset
from src.models.visual import ChartSpec

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from src.models.content_pipeline import SectionDraft

matplotlib.use("Agg")  # Non-interactive backend
logger = structlog.get_logger()

_PROMPT_TEMPLATE = """You are a data visualization expert. Read the article sections below and propose 0-3 data charts.

For each chart, provide:
- chart_type: "bar", "line", or "pie"
- title: chart title (max 120 chars)
- x_labels: category labels or x-axis points
- y_values: numeric values corresponding to each label
- y_label: y-axis label
- caption: one-sentence description for the article
- source_section_index: which section (0-indexed) the data comes from

Only propose charts where concrete numerical data exists in the text. Return an empty array [] if no chartable data is found.

Return ONLY a JSON array. No explanation.

## Article Sections
{sections_text}"""


async def propose_charts(
    section_drafts: list[SectionDraft],
    llm: BaseChatModel,
) -> list[ChartSpec]:
    """Ask LLM to propose 0-3 chart specs from section drafts."""
    sections_text = "\n\n".join(
        f"### {d.title}\n{d.body_markdown}" for d in section_drafts
    )
    prompt = _PROMPT_TEMPLATE.format(sections_text=sections_text)
    try:
        response = await llm.ainvoke(prompt)
        raw = json.loads(response.content)
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        logger.warning("chart_proposal_parse_failed", error=str(exc))
        return []

    if not isinstance(raw, list):
        logger.warning("chart_proposal_not_list", type=type(raw).__name__)
        return []

    specs: list[ChartSpec] = []
    for item in raw[:3]:
        try:
            spec = ChartSpec.model_validate(item)
            if len(spec.x_labels) != len(spec.y_values):
                logger.warning("chart_spec_length_mismatch", title=spec.title)
                continue
            specs.append(spec)
        except (ValidationError, TypeError) as exc:
            logger.warning("chart_spec_invalid", error=str(exc))
    return specs


def render_chart(
    spec: ChartSpec,
    output_dir: str,
    session_id: UUID,
) -> ImageAsset | None:
    """Render a ChartSpec to PNG via Matplotlib. Returns None on failure."""
    chart_id = uuid4()
    out_path = Path(output_dir) / str(session_id)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{chart_id}.png"

    try:
        fig, ax = plt.subplots(figsize=(8, 5))

        if spec.chart_type == "bar":
            ax.bar(spec.x_labels, spec.y_values)
            ax.set_ylabel(spec.y_label)
            ax.grid(axis="y", alpha=0.3)
        elif spec.chart_type == "line":
            ax.plot(spec.x_labels, spec.y_values, marker="o")
            ax.set_ylabel(spec.y_label)
            ax.grid(alpha=0.3)
        elif spec.chart_type == "pie":
            ax.pie(spec.y_values, labels=spec.x_labels, autopct="%1.1f%%")

        ax.set_title(spec.title, fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(str(file_path), dpi=150, transparent=True)
        plt.close(fig)

        logger.info("chart_rendered", chart_type=spec.chart_type, path=str(file_path))
        return ImageAsset(
            url=str(file_path),
            caption=spec.caption,
            alt_text=spec.title,
            metadata={"chart_type": spec.chart_type, "source_section": spec.source_section_index},
        )
    except Exception as exc:
        logger.warning("chart_render_failed", error=str(exc), title=spec.title)
        plt.close("all")
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/unit/agents/content/test_chart_generator.py -v 2>&1 | tail -20`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-001
git add src/agents/content/chart_generator.py tests/unit/agents/content/test_chart_generator.py
git commit -m "feat(visual-001): add chart proposal and rendering functions"
```

---

## Task 4: Pipeline Integration — ContentState, Chart Node, Graph Wiring

**Files:**
- Modify: `src/models/content_pipeline.py`
- Modify: `src/agents/content/pipeline.py`
- Modify: `src/agents/content/nodes.py`
- Create: `tests/unit/agents/content/test_chart_node.py`

- [ ] **Step 1: Write failing chart node tests**

Create `tests/unit/agents/content/test_chart_node.py`:

```python
"""Tests for chart generation pipeline node."""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agents.content.nodes import make_chart_node
from src.models.content_pipeline import SectionDraft


def _make_section(index: int, body: str) -> SectionDraft:
    return SectionDraft(
        section_index=index,
        title=f"Section {index}",
        body_markdown=body,
        word_count=len(body.split()),
        citations_used=[],
    )


VALID_SPEC = {
    "chart_type": "bar",
    "title": "Test Chart",
    "x_labels": ["A", "B"],
    "y_values": [10.0, 20.0],
    "y_label": "Count",
    "caption": "A test chart.",
    "source_section_index": 0,
}


class TestChartNode:
    @pytest.mark.asyncio
    async def test_produces_visuals_from_llm_specs(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = AsyncMock(content=json.dumps([VALID_SPEC]))
        node = make_chart_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Attacks: A=10, B=20.")],
        }
        result = await node(state)
        assert "visuals" in result
        assert len(result["visuals"]) == 1
        assert result["visuals"][0].caption == "A test chart."

    @pytest.mark.asyncio
    async def test_returns_empty_visuals_for_no_specs(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = AsyncMock(content="[]")
        node = make_chart_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "No data.")],
        }
        result = await node(state)
        assert result["visuals"] == []

    @pytest.mark.asyncio
    async def test_returns_empty_visuals_for_no_drafts(self, tmp_path) -> None:
        llm = AsyncMock()
        node = make_chart_node(llm, str(tmp_path))
        state = {"session_id": uuid4()}
        result = await node(state)
        assert result["visuals"] == []

    @pytest.mark.asyncio
    async def test_skips_failed_renders(self, tmp_path) -> None:
        bad_spec = {**VALID_SPEC, "y_values": []}  # will fail rendering
        good_spec = VALID_SPEC
        llm = AsyncMock()
        llm.ainvoke.return_value = AsyncMock(content=json.dumps([bad_spec, good_spec]))
        node = make_chart_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Data.")],
        }
        result = await node(state)
        # bad_spec is discarded by propose_charts (min_length=2), only good_spec renders
        assert len(result["visuals"]) == 1
```

- [ ] **Step 2: Add visuals field to ArticleDraft**

In `src/models/content_pipeline.py`, after line 127 (`references_markdown: str = ""`), add:

```python
    visuals: list = Field(default_factory=list)  # list[ImageAsset], avoids circular import
```

- [ ] **Step 3: Add visuals to ContentState**

In `src/agents/content/pipeline.py`, after line 52 (`seo_result: NotRequired[SEOResult]`), add:

```python
    visuals: NotRequired[list]
```

- [ ] **Step 4: Add make_chart_node to nodes.py**

In `src/agents/content/nodes.py`, add these imports at the top:

```python
import asyncio
from uuid import UUID

from src.agents.content.chart_generator import propose_charts, render_chart
```

Then add the factory function after `make_citations_node()`:

```python
def make_chart_node(llm: BaseChatModel, output_dir: str) -> Any:  # noqa: ANN401
    """Factory for the chart generation node."""

    async def chart_node(state: ContentState) -> dict[str, object]:
        section_drafts = state.get("section_drafts", [])
        session_id: UUID = state["session_id"]
        if not section_drafts:
            return {"visuals": []}
        specs = await propose_charts(section_drafts, llm)
        visuals = []
        for spec in specs:
            asset = await asyncio.to_thread(render_chart, spec, output_dir, session_id)
            if asset is not None:
                visuals.append(asset)
        logger.info("chart_generation_complete", chart_count=len(visuals))
        return {"visuals": visuals}

    return chart_node
```

- [ ] **Step 5: Wire chart node into pipeline graph**

In `src/agents/content/pipeline.py`:

Add import at top (after existing node imports):
```python
from src.agents.content.nodes import make_chart_node
```

(Note: `make_chart_node` is already accessible since `nodes.py` is imported.)

After line 74 (`graph.add_node("seo_optimize", ...)`), add:
```python
    graph.add_node("generate_charts", make_chart_node(llm, settings.chart_output_dir if settings else "generated_assets/charts"))
```

Replace line 90 (`graph.add_edge("seo_optimize", END)`) with:
```python
    graph.add_edge("seo_optimize", "generate_charts")
    graph.add_edge("generate_charts", END)
```

- [ ] **Step 6: Run chart node tests**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/unit/agents/content/test_chart_node.py -v 2>&1 | tail -15`
Expected: All PASS.

- [ ] **Step 7: Run existing pipeline tests to check no regressions**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/unit/agents/content/ -v 2>&1 | tail -20`
Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
cd D:/Workbench/github/cognify-visual-001
git add src/models/content_pipeline.py src/agents/content/pipeline.py src/agents/content/nodes.py tests/unit/agents/content/test_chart_node.py
git commit -m "feat(visual-001): add chart node to content pipeline"
```

---

## Task 5: Data Flow — _store_drafted, Assembler, Finalize

**Files:**
- Modify: `src/services/content.py`
- Modify: `src/agents/content/article_assembler.py`
- Modify: `src/services/content_finalize.py`
- Modify: `tests/unit/agents/content/test_article_assembler.py`

- [ ] **Step 1: Write failing assembler test with visuals**

In `tests/unit/agents/content/test_article_assembler.py`, add this test to the existing test class:

```python
def test_visuals_populated_from_parameter(self) -> None:
    from src.models.content import ImageAsset

    topic = _make_topic()
    draft = _make_draft()
    visuals = [
        ImageAsset(url="/charts/test.png", caption="Test chart", alt_text="Chart"),
    ]
    article = assemble_canonical_article(draft, topic, visuals=visuals)
    assert len(article.visuals) == 1
    assert article.visuals[0].caption == "Test chart"


def test_visuals_default_to_empty(self) -> None:
    topic = _make_topic()
    draft = _make_draft()
    article = assemble_canonical_article(draft, topic)
    assert article.visuals == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/unit/agents/content/test_article_assembler.py -v -k "visuals" 2>&1 | tail -10`
Expected: FAIL — `assemble_canonical_article` doesn't accept `visuals` param.

- [ ] **Step 3: Update article_assembler.py**

In `src/agents/content/article_assembler.py`:

Change the function signature (line 21-24) from:
```python
def assemble_canonical_article(
    draft: ArticleDraft,
    topic: TopicInput,
) -> CanonicalArticle:
```
To:
```python
def assemble_canonical_article(
    draft: ArticleDraft,
    topic: TopicInput,
    visuals: list[ImageAsset] | None = None,
) -> CanonicalArticle:
```

Add import at top: `from src.models.content import CanonicalArticle, Citation, ContentType, ImageAsset`
(add `ImageAsset` to existing import line)

Change line 45 from:
```python
            visuals=[],
```
To:
```python
            visuals=visuals if visuals is not None else [],
```

- [ ] **Step 4: Update _store_drafted in content.py**

In `src/services/content.py`, in the `_store_drafted` method, add after line 214 (`"references_markdown": ...`):

```python
                "visuals": list(result.get("visuals") or []),
```

- [ ] **Step 5: Update build_article in content_finalize.py**

In `src/services/content_finalize.py`, change `build_article` (line 65-70) from:
```python
def build_article(
    draft: ArticleDraft,
    topic: TopicInput,
) -> CanonicalArticle:
    """Assemble a CanonicalArticle from a finalized draft."""
    return assemble_canonical_article(draft, topic)
```
To:
```python
def build_article(
    draft: ArticleDraft,
    topic: TopicInput,
) -> CanonicalArticle:
    """Assemble a CanonicalArticle from a finalized draft."""
    return assemble_canonical_article(draft, topic, visuals=draft.visuals)
```

- [ ] **Step 6: Run assembler tests**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/unit/agents/content/test_article_assembler.py -v 2>&1 | tail -15`
Expected: All PASS (including new visuals tests).

- [ ] **Step 7: Run full test suite**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/ -q --tb=short 2>&1 | tail -10`
Expected: All tests pass (697+ existing + ~20 new).

- [ ] **Step 8: Commit**

```bash
cd D:/Workbench/github/cognify-visual-001
git add src/services/content.py src/agents/content/article_assembler.py src/services/content_finalize.py tests/unit/agents/content/test_article_assembler.py
git commit -m "feat(visual-001): wire visuals through ArticleDraft to CanonicalArticle"
```

---

## Task 6: Final Verification

**Files:** None new — verification only.

- [ ] **Step 1: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run pytest tests/ -q --tb=short 2>&1 | tail -15`
Expected: All tests pass, 0 new failures.

- [ ] **Step 2: Run linter**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run ruff check src/ tests/ 2>&1 | tail -10`
Expected: No errors.

- [ ] **Step 3: Run type checker**

Run: `cd D:/Workbench/github/cognify-visual-001 && uv run mypy src/models/visual.py src/agents/content/chart_generator.py 2>&1 | tail -10`
Expected: No errors (or only pre-existing issues).

- [ ] **Step 4: Fix any issues and commit**

If lint/type issues found, fix and commit:
```bash
cd D:/Workbench/github/cognify-visual-001
git add -A && git commit -m "fix(visual-001): resolve lint and type issues"
```

- [ ] **Step 5: Verify test count increased**

Baseline was 697 tests. New tests should bring total to ~720+.
