# VISUAL-003: Diagram Generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate 0-2 Mermaid diagrams per article (flowcharts and sequence diagrams) from article content, rendered to PNG via Mermaid CLI.

**Architecture:** LLM proposes DiagramSpec objects from section drafts. Async render function calls `mmdc` CLI via `create_subprocess_exec`. Pipeline node accumulates diagram visuals with existing charts/illustrations. Best-effort: failures skip, pipeline continues.

**Tech Stack:** Python 3.12, Mermaid CLI (`@mermaid-js/mermaid-cli`), Pydantic, LangGraph, pytest

**Spec:** [`docs/superpowers/specs/2026-03-22-visual-003-diagram-generation-design.md`](../specs/2026-03-22-visual-003-diagram-generation-design.md)

**Worktree:** `D:/Workbench/github/cognify-visual-003` (branch: `feature/VISUAL-003-diagram-generation`)

**Baseline:** 809 backend tests passing, 235 frontend tests passing (2 pre-existing failures in `use-scan-topics.test.ts`).

---

## Task 1: Install Mermaid CLI and add settings

**Files:**
- Create: `package.json` at project root (if not exists)
- Modify: `src/config/settings.py`

- [ ] **Step 1: Install mermaid-cli**

```bash
cd D:/Workbench/github/cognify-visual-003
npm init -y 2>/dev/null || true
npm install --save-dev @mermaid-js/mermaid-cli
```

Verify: `cd D:/Workbench/github/cognify-visual-003 && ./node_modules/.bin/mmdc --version`

- [ ] **Step 2: Add settings**

In `src/config/settings.py`, after the `illustration_timeout` line, add:

```python
    # Diagram generation (Mermaid CLI)
    diagram_output_dir: str = "generated_assets/diagrams"
```

- [ ] **Step 3: Add node_modules to .gitignore if not present**

Check if root `.gitignore` includes `node_modules/`. If not, add it.

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-visual-003
git add package.json package-lock.json src/config/settings.py .gitignore
git commit -m "chore: add mermaid-cli dependency and diagram settings"
```

---

## Task 2: Add DiagramSpec model

**Files:**
- Modify: `src/models/visual.py`
- Test: `tests/unit/models/test_visual_models.py`

- [ ] **Step 1: Write the failing tests**

In `tests/unit/models/test_visual_models.py`, add:

```python
from src.models.visual import DiagramSpec, DiagramType


class TestDiagramType:
    def test_flowchart_value(self) -> None:
        assert DiagramType.FLOWCHART == "flowchart"

    def test_sequence_value(self) -> None:
        assert DiagramType.SEQUENCE == "sequence"

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValueError):
            DiagramType("invalid")


class TestDiagramSpec:
    def test_valid_flowchart_spec(self) -> None:
        spec = DiagramSpec(
            diagram_type=DiagramType.FLOWCHART,
            title="Auth Flow",
            mermaid_syntax="graph TD\n    A[Start] --> B[End]",
            caption="Authentication flow diagram",
            source_section_index=0,
        )
        assert spec.diagram_type == "flowchart"
        assert spec.title == "Auth Flow"

    def test_valid_sequence_spec(self) -> None:
        spec = DiagramSpec(
            diagram_type=DiagramType.SEQUENCE,
            title="API Call Sequence",
            mermaid_syntax="sequenceDiagram\n    A->>B: Request",
            caption="API interaction sequence",
            source_section_index=1,
        )
        assert spec.diagram_type == "sequence"

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DiagramSpec(
                diagram_type=DiagramType.FLOWCHART,
                title="",
                mermaid_syntax="graph TD\n    A --> B",
                caption="Caption",
                source_section_index=0,
            )

    def test_short_mermaid_syntax_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DiagramSpec(
                diagram_type=DiagramType.FLOWCHART,
                title="Title",
                mermaid_syntax="short",
                caption="Caption",
                source_section_index=0,
            )

    def test_empty_caption_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DiagramSpec(
                diagram_type=DiagramType.FLOWCHART,
                title="Title",
                mermaid_syntax="graph TD\n    A --> B",
                caption="",
                source_section_index=0,
            )
```

Add the `ValidationError` import at top if not present: `from pydantic import ValidationError`

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/unit/models/test_visual_models.py -k "Diagram" -v`
Expected: FAIL — `DiagramSpec` not found.

- [ ] **Step 3: Implement DiagramSpec**

In `src/models/visual.py`, add after `ChartSpec`:

```python
class DiagramType(StrEnum):
    """Supported diagram types."""

    FLOWCHART = "flowchart"
    SEQUENCE = "sequence"


class DiagramSpec(BaseModel, frozen=True):
    """LLM-proposed diagram specification with Mermaid syntax."""

    diagram_type: DiagramType
    title: str = Field(min_length=1, max_length=120)
    mermaid_syntax: str = Field(min_length=10)
    caption: str = Field(min_length=1, max_length=200)
    source_section_index: int = Field(ge=0)
```

- [ ] **Step 4: Run tests**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/unit/models/test_visual_models.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-003
git add src/models/visual.py tests/unit/models/test_visual_models.py
git commit -m "feat(visual): add DiagramType and DiagramSpec models"
```

---

## Task 3: Implement render_mermaid and propose_diagrams

**Files:**
- Create: `src/agents/content/diagram_generator.py`
- Create: `tests/unit/agents/content/test_diagram_generator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/agents/content/test_diagram_generator.py`:

```python
"""Tests for diagram generation: Mermaid rendering and LLM proposal."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.agents.content.diagram_generator import propose_diagrams, render_mermaid
from src.models.content_pipeline import SectionDraft
from src.models.visual import DiagramSpec, DiagramType


def _make_section(index: int, body: str) -> SectionDraft:
    return SectionDraft(
        section_index=index,
        title=f"Section {index}",
        body_markdown=body,
        word_count=len(body.split()),
        citations_used=[],
    )


VALID_SPEC = {
    "diagram_type": "flowchart",
    "title": "Auth Flow",
    "mermaid_syntax": "graph TD\n    A[Start] --> B[Login] --> C[Dashboard]",
    "caption": "Authentication flow overview.",
    "source_section_index": 0,
}

VALID_SEQUENCE_SPEC = {
    "diagram_type": "sequence",
    "title": "API Call",
    "mermaid_syntax": "sequenceDiagram\n    Client->>Server: GET /api\n    Server-->>Client: 200 OK",
    "caption": "API request sequence.",
    "source_section_index": 0,
}


class TestRenderMermaid:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.png"
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await render_mermaid("graph TD\n    A-->B", output_file)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_nonzero_exit(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.png"
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"parse error"))
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await render_mermaid("invalid syntax", output_file)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_file_not_found(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.png"
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("mmdc not found"),
        ):
            result = await render_mermaid("graph TD\n    A-->B", output_file)
        assert result is False


class TestProposeDiagrams:
    @pytest.mark.asyncio
    async def test_returns_valid_specs(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content=json.dumps([VALID_SPEC])
        )
        sections = [_make_section(0, "The auth flow starts with login.")]
        result = await propose_diagrams(sections, llm)
        assert len(result) == 1
        assert result[0].diagram_type == DiagramType.FLOWCHART

    @pytest.mark.asyncio
    async def test_returns_empty_on_empty_array(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="[]")
        result = await propose_diagrams([_make_section(0, "No diagrams.")], llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_malformed_json(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="not json")
        result = await propose_diagrams([_make_section(0, "Text.")], llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_discards_invalid_keeps_valid(self) -> None:
        bad_spec = {**VALID_SPEC, "title": ""}  # empty title fails min_length=1
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content=json.dumps([bad_spec, VALID_SEQUENCE_SPEC])
        )
        sections = [_make_section(0, "Text.")]
        result = await propose_diagrams(sections, llm)
        assert len(result) == 1
        assert result[0].diagram_type == DiagramType.SEQUENCE

    @pytest.mark.asyncio
    async def test_discards_out_of_range_section_index(self) -> None:
        bad_spec = {**VALID_SPEC, "source_section_index": 5}
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content=json.dumps([bad_spec])
        )
        result = await propose_diagrams([_make_section(0, "Text.")], llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_truncates_to_max_two(self) -> None:
        specs = [VALID_SPEC, VALID_SEQUENCE_SPEC, {**VALID_SPEC, "title": "Third"}]
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps(specs))
        result = await propose_diagrams([_make_section(0, "Text.")], llm)
        assert len(result) <= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/unit/agents/content/test_diagram_generator.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement diagram_generator.py**

Create `src/agents/content/diagram_generator.py`:

```python
"""Diagram generation from article section drafts.

LLM proposes Mermaid diagram specs, mmdc CLI renders to PNG.
Best-effort: failures are logged and skipped, never crash the pipeline.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from pydantic import ValidationError

from src.models.visual import DiagramSpec

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from src.models.content_pipeline import SectionDraft

logger = structlog.get_logger()

_MMDC_PATH = Path(__file__).parents[3] / "node_modules" / ".bin" / "mmdc"

_PROMPT_TEMPLATE = (
    "You are a technical diagram expert. "
    "Read the article sections below and propose 0-2 diagrams.\n\n"
    "Supported types: flowchart, sequence.\n\n"
    "For each diagram, provide:\n"
    '- diagram_type: "flowchart" or "sequence"\n'
    "- title: diagram title (max 120 chars)\n"
    "- mermaid_syntax: valid Mermaid diagram code\n"
    "- caption: one-sentence description for the article\n"
    "- source_section_index: which section (0-indexed) the diagram illustrates\n\n"
    "Only propose diagrams where a process flow or interaction sequence "
    "is described in the text. Return an empty array [] if nothing is diagrammable.\n\n"
    "Return ONLY a JSON array. No explanation.\n\n"
    "## Article Sections\n{sections_text}"
)


async def render_mermaid(syntax: str, output_path: Path) -> bool:
    """Render Mermaid syntax to PNG via mmdc CLI. Returns True on success."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mmd", delete=False
        ) as tmp:
            tmp.write(syntax)
            tmp_path = Path(tmp.name)

        mmdc = str(_MMDC_PATH)
        process = await asyncio.create_subprocess_exec(
            mmdc,
            "-i", str(tmp_path),
            "-o", str(output_path),
            "-b", "transparent",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(), timeout=15.0
        )

        tmp_path.unlink(missing_ok=True)

        if process.returncode != 0:
            logger.warning(
                "mermaid_render_failed",
                exit_code=process.returncode,
                stderr=stderr.decode()[:200],
            )
            return False

        logger.info("mermaid_rendered", path=str(output_path))
        return True

    except FileNotFoundError:
        logger.warning("mmdc_not_found", path=str(_MMDC_PATH))
        return False
    except asyncio.TimeoutError:
        logger.warning("mermaid_render_timeout")
        return False
    except Exception as exc:
        logger.warning("mermaid_render_error", error=str(exc))
        return False


async def propose_diagrams(
    section_drafts: list[SectionDraft],
    llm: BaseChatModel,
) -> list[DiagramSpec]:
    """Ask LLM to propose 0-2 diagram specs from section drafts."""
    sections_text = "\n\n".join(
        f"### {d.title}\n{d.body_markdown}" for d in section_drafts
    )
    prompt = _PROMPT_TEMPLATE.format(sections_text=sections_text)
    try:
        response = await llm.ainvoke(prompt)
        raw = json.loads(response.content)
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        logger.warning("diagram_proposal_parse_failed", error=str(exc))
        return []

    if not isinstance(raw, list):
        logger.warning("diagram_proposal_not_list", type=type(raw).__name__)
        return []

    specs: list[DiagramSpec] = []
    for item in raw[:2]:
        try:
            spec = DiagramSpec.model_validate(item)
            if spec.source_section_index >= len(section_drafts):
                logger.warning(
                    "diagram_spec_section_out_of_range", title=spec.title
                )
                continue
            specs.append(spec)
        except (ValidationError, TypeError) as exc:
            logger.warning("diagram_spec_invalid", error=str(exc))
    return specs
```

- [ ] **Step 4: Run tests**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/unit/agents/content/test_diagram_generator.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-visual-003
git add src/agents/content/diagram_generator.py tests/unit/agents/content/test_diagram_generator.py
git commit -m "feat(visual): add Mermaid rendering and diagram proposal functions"
```

---

## Task 4: Diagram pipeline node

**Files:**
- Modify: `src/agents/content/nodes.py`
- Create: `tests/unit/agents/content/test_diagram_node.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/agents/content/test_diagram_node.py`:

```python
"""Tests for diagram generation pipeline node."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.agents.content.nodes import make_diagram_node
from src.models.content import ImageAsset
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
    "diagram_type": "flowchart",
    "title": "Auth Flow",
    "mermaid_syntax": "graph TD\n    A[Start] --> B[Login] --> C[Dashboard]",
    "caption": "Authentication flow.",
    "source_section_index": 0,
}


class TestDiagramNode:
    @pytest.mark.asyncio
    async def test_produces_diagram_assets(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps([VALID_SPEC]))
        node = make_diagram_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Auth flow: login then dashboard.")],
        }
        with patch(
            "src.agents.content.nodes.render_mermaid",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await node(state)
        assert len(result["visuals"]) == 1
        asset = result["visuals"][0]
        assert isinstance(asset, ImageAsset)
        assert asset.metadata["diagram_type"] == "flowchart"

    @pytest.mark.asyncio
    async def test_preserves_existing_visuals(self, tmp_path) -> None:
        existing = ImageAsset(url="/charts/foo.png", caption="Chart")
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps([VALID_SPEC]))
        node = make_diagram_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Text.")],
            "visuals": [existing],
        }
        with patch(
            "src.agents.content.nodes.render_mermaid",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await node(state)
        assert len(result["visuals"]) == 2
        assert result["visuals"][0] == existing

    @pytest.mark.asyncio
    async def test_returns_existing_on_no_drafts(self, tmp_path) -> None:
        existing = ImageAsset(url="/charts/foo.png", caption="Chart")
        llm = AsyncMock()
        node = make_diagram_node(llm, str(tmp_path))
        state = {"session_id": uuid4(), "visuals": [existing]}
        result = await node(state)
        assert result["visuals"] == [existing]

    @pytest.mark.asyncio
    async def test_skips_failed_renders_keeps_successful(self, tmp_path) -> None:
        specs = [
            VALID_SPEC,
            {**VALID_SPEC, "diagram_type": "sequence", "title": "Good Diagram",
             "mermaid_syntax": "sequenceDiagram\n    A->>B: Request"},
        ]
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps(specs))
        node = make_diagram_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Text.")],
        }
        # First render fails, second succeeds
        with patch(
            "src.agents.content.nodes.render_mermaid",
            new_callable=AsyncMock,
            side_effect=[False, True],
        ):
            result = await node(state)
        assert len(result["visuals"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/unit/agents/content/test_diagram_node.py -v`
Expected: FAIL — `make_diagram_node` not found.

- [ ] **Step 3: Implement make_diagram_node**

In `src/agents/content/nodes.py`, add import at the top:

```python
from src.agents.content.diagram_generator import propose_diagrams, render_mermaid
```

Add the factory after `make_illustration_node`:

```python
def make_diagram_node(
    llm: BaseChatModel,
    output_dir: str,
) -> Any:  # noqa: ANN401
    """Factory for the diagram generation node."""

    async def diagram_node(state: ContentState) -> dict[str, object]:
        existing = list(state.get("visuals", []))
        section_drafts = state.get("section_drafts", [])
        session_id: UUID = state["session_id"]
        if not section_drafts:
            return {"visuals": existing}

        specs = await propose_diagrams(section_drafts, llm)
        new_visuals: list[ImageAsset] = []
        out_path = Path(output_dir) / str(session_id)
        out_path.mkdir(parents=True, exist_ok=True)

        for spec in specs:
            file_path = out_path / f"diagram_{uuid4()}.png"
            success = await render_mermaid(spec.mermaid_syntax, file_path)
            if success:
                new_visuals.append(
                    ImageAsset(
                        url=str(file_path),
                        caption=spec.caption,
                        alt_text=spec.title,
                        metadata={
                            "diagram_type": str(spec.diagram_type),
                            "source_section": spec.source_section_index,
                        },
                    )
                )
            else:
                logger.warning("diagram_render_skipped", title=spec.title)

        logger.info("diagram_generation_complete", count=len(new_visuals))
        return {"visuals": existing + new_visuals}

    return diagram_node
```

Add `from uuid import uuid4` to imports if not already present (it should be — used by `_save_illustration`). Ensure `ImageAsset` import exists.

- [ ] **Step 4: Run tests**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/unit/agents/content/test_diagram_node.py -v`
Expected: All PASS.

- [ ] **Step 5: Run all content tests**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/unit/agents/content/ -v --tb=short`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
cd D:/Workbench/github/cognify-visual-003
git add src/agents/content/nodes.py tests/unit/agents/content/test_diagram_node.py
git commit -m "feat(visual): add diagram pipeline node with visual accumulation"
```

---

## Task 5: Wire diagram node into content pipeline

**Files:**
- Modify: `src/agents/content/pipeline.py`
- Modify: `tests/unit/agents/content/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/agents/content/test_pipeline.py`, add:

```python
class TestDiagramNodeInGraph:
    def test_graph_includes_diagram_node(self) -> None:
        from unittest.mock import AsyncMock
        from src.agents.content.pipeline import build_content_graph
        llm = AsyncMock()
        retriever = AsyncMock()
        graph = build_content_graph(llm, retriever)
        node_names = list(graph.get_graph().nodes.keys())
        assert "generate_diagrams" in node_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/unit/agents/content/test_pipeline.py -k "DiagramNodeInGraph" -v`
Expected: FAIL.

- [ ] **Step 3: Wire diagram node**

In `src/agents/content/pipeline.py`:

Add import:
```python
from src.agents.content.nodes import make_diagram_node
```
(Add to the existing `from src.agents.content.nodes import ...` block.)

In `build_content_graph()`, add the diagram node and update the edges. Replace the section from line 80 onward:

After `graph.add_node("generate_charts", make_chart_node(llm, chart_dir))`, add:

```python
    diagram_dir = settings.diagram_output_dir if settings else "generated_assets/diagrams"
    graph.add_node("generate_diagrams", make_diagram_node(llm, diagram_dir))
```

Then update the edges. The current structure has conditional illustration wiring. Replace the entire conditional block (lines 98-112) with:

```python
    # Illustration node — only if OpenAI key is configured
    if settings and settings.openai_api_key:
        generator = OpenAIDalleGenerator(
            api_key=settings.openai_api_key,
            model=settings.dalle_model,
            timeout=settings.illustration_timeout,
        )
        graph.add_node(
            "generate_illustrations",
            make_illustration_node(llm, generator, settings.illustration_output_dir),
        )
        graph.add_edge("generate_charts", "generate_illustrations")
        graph.add_edge("generate_illustrations", "generate_diagrams")
    else:
        graph.add_edge("generate_charts", "generate_diagrams")

    graph.add_edge("generate_diagrams", END)
```

The diagram node is always the last visual node before END.

- [ ] **Step 4: Run wiring test**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/unit/agents/content/test_pipeline.py -k "DiagramNodeInGraph" -v`
Expected: PASS.

- [ ] **Step 5: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/ -q --tb=no`
Expected: 809+ passed.

- [ ] **Step 6: Commit**

```bash
cd D:/Workbench/github/cognify-visual-003
git add src/agents/content/pipeline.py tests/unit/agents/content/test_pipeline.py
git commit -m "feat(visual): wire diagram node into content pipeline graph"
```

---

## Task 6: Lint, verify, and update PROGRESS.md

- [ ] **Step 1: Run linter**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv tool run ruff check src/agents/content/ src/models/visual.py`
Fix any issues.

- [ ] **Step 2: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-visual-003 && uv run pytest tests/ -q --tb=no`
Expected: 809+ passed.

- [ ] **Step 3: Update PROGRESS.md with plan/spec links**

Update VISUAL-003 row with plan and spec links.

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-visual-003
git add -A
git commit -m "docs: update PROGRESS.md with VISUAL-003 plan and spec links"
```
