# VISUAL-003: Diagram Generation — Design Spec

## Overview

Generate 0-2 Mermaid diagrams per article (flowcharts and sequence diagrams) from article section content. LLM proposes diagram specs, Mermaid CLI renders to PNG. Follows the VISUAL-001 chart generation pattern.

**Scope boundaries:**
- 0-2 diagrams per article (flowcharts and sequence diagrams only)
- Mermaid CLI (`mmdc`) for local rendering — no external API
- PNG output with transparent background
- Best-effort: CLI not installed or render failure → skip, pipeline continues
- No interactive diagrams (static PNG only)

## Acceptance Criteria (from BACKLOG.md)

1. Mermaid diagram syntax generated from article content
2. Rendered to PNG/SVG (PNG chosen for consistency with charts)
3. Supports flowcharts and sequence diagrams

## Section 1: Mermaid Rendering

### Function

`render_mermaid(syntax: str, output_path: Path) -> bool` in `src/agents/content/diagram_generator.py`

- Writes Mermaid syntax to a temporary `.mmd` file
- Calls `mmdc -i input.mmd -o output.png -b transparent` via `asyncio.create_subprocess_exec`
- Returns `True` on success (file exists), `False` on failure
- Timeout: 15 seconds (diagrams render fast)
- On any error (CLI not found, invalid syntax, timeout): logs warning via structlog, returns `False`

### Dependency

Install `@mermaid-js/mermaid-cli` as an npm dev dependency at the project root (not in frontend/):
```bash
npm install --save-dev @mermaid-js/mermaid-cli
```

The `mmdc` binary is at `./node_modules/.bin/mmdc`. The render function should resolve this path relative to the project root.

**Files:**
- `src/agents/content/diagram_generator.py` (new) — `render_mermaid()` function
- `package.json` at project root (new or modified) — mermaid-cli dev dependency

## Section 2: Diagram Proposal via LLM

### Model

`DiagramSpec` Pydantic model in `src/models/visual.py` (alongside existing `ChartSpec`):

```python
class DiagramType(StrEnum):
    FLOWCHART = "flowchart"
    SEQUENCE = "sequence"

class DiagramSpec(BaseModel, frozen=True):
    diagram_type: DiagramType
    title: str = Field(max_length=120)
    mermaid_syntax: str = Field(min_length=10)
    caption: str = Field(max_length=200)
    source_section_index: int = Field(ge=0)
```

### Function

`propose_diagrams(section_drafts: list[SectionDraft], llm: BaseChatModel) -> list[DiagramSpec]` in `src/agents/content/diagram_generator.py`

- Follows the exact `propose_charts` pattern
- Prompt template (`_PROMPT_TEMPLATE`) sends all section text to LLM
- Asks LLM to return JSON array of 0-2 diagram specs
- Post-validation: discard specs where `source_section_index >= len(section_drafts)`
- On JSON parse failure: log warning, return empty list
- Invalid specs (Pydantic validation error): log warning, skip, keep valid ones

**Files:**
- `src/models/visual.py` — add `DiagramType`, `DiagramSpec`
- `src/agents/content/diagram_generator.py` — add `propose_diagrams()` with `_PROMPT_TEMPLATE`

## Section 3: Pipeline Integration

### Node Factory

`make_diagram_node(llm, output_dir)` in `src/agents/content/nodes.py`:

1. Extract `section_drafts` and `session_id` from `ContentState`
2. Read existing visuals: `existing = list(state.get("visuals", []))`
3. If no section_drafts → return `{"visuals": existing}`
4. Call `propose_diagrams(section_drafts, llm)` → get specs
5. For each spec, render via `asyncio.to_thread(render_mermaid, ...)`:
   - Generate unique filename: `{output_dir}/{session_id}/diagram_{uuid}.png`
   - On success: create `ImageAsset(url=path, caption=spec.caption, alt_text=spec.title, metadata={"diagram_type": spec.diagram_type, "source_section": spec.source_section_index})`
   - On failure: skip, log warning
6. Return `{"visuals": existing + new_diagrams}` (accumulate with charts + illustration)

### Pipeline Graph

Add `generate_diagrams` node after the last visual node, before `END`:

When illustration node is present (OpenAI key set):
```
... → generate_charts → generate_illustrations → generate_diagrams → END
```

When illustration node is absent:
```
... → generate_charts → generate_diagrams → END
```

Diagram node is always added (no API key needed — local CLI). If `mmdc` is not installed at runtime, render calls fail gracefully and return no diagrams.

### Visual Accumulation

Same LangGraph TypedDict replacement semantics as VISUAL-002:
- Read `existing = list(state.get("visuals", []))`
- Append new diagram assets
- Return combined list

**Files:**
- `src/agents/content/nodes.py` — add `make_diagram_node()` factory
- `src/agents/content/pipeline.py` — wire diagram node into graph

## Section 4: Testing Strategy

### Unit Tests — DiagramSpec Model
- Valid spec construction with flowchart/sequence types
- Invalid diagram_type rejected by StrEnum
- Title max_length, mermaid_syntax min_length validation

### Unit Tests — propose_diagrams
- Mock LLM returns valid specs → list of DiagramSpec
- Mock LLM returns empty array → empty list
- Malformed JSON → empty list (graceful)
- Invalid specs discarded, valid kept
- source_section_index out of range → discarded

### Unit Tests — render_mermaid
- Mock subprocess success (exit code 0) → returns True
- Mock subprocess failure (non-zero exit) → returns False
- Mock subprocess not found (FileNotFoundError) → returns False

### Unit Tests — Diagram Node
- Full flow: mock LLM specs + mock render → ImageAssets with correct fields
- No drafts → preserves existing visuals
- Render failure → skipped, successful diagrams kept
- Existing visuals (charts + illustration) preserved (accumulation)

### Pipeline Wiring
- Verify `generate_diagrams` node present in graph

**Test files:**
- `tests/unit/models/test_visual_models.py` — add DiagramSpec tests
- `tests/unit/agents/content/test_diagram_generator.py` (new) — propose + render tests
- `tests/unit/agents/content/test_diagram_node.py` (new) — node factory tests
- `tests/unit/agents/content/test_pipeline.py` — add wiring test

## File Change Summary

| File | Change Type | Description |
|------|------------|-------------|
| `src/models/visual.py` | Modified | Add DiagramType, DiagramSpec |
| `src/agents/content/diagram_generator.py` | New | render_mermaid(), propose_diagrams(), prompt template |
| `src/agents/content/nodes.py` | Modified | Add make_diagram_node() factory |
| `src/agents/content/pipeline.py` | Modified | Wire diagram node into graph |
| `package.json` | New/Modified | Add @mermaid-js/mermaid-cli dev dependency |
| `tests/unit/models/test_visual_models.py` | Modified | Add DiagramSpec model tests |
| `tests/unit/agents/content/test_diagram_generator.py` | New | Propose + render unit tests |
| `tests/unit/agents/content/test_diagram_node.py` | New | Node factory tests |
| `tests/unit/agents/content/test_pipeline.py` | Modified | Add diagram wiring test |
