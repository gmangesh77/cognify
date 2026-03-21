# VISUAL-001: Data Chart Generation — Design Specification

> **Date**: 2026-03-21
> **Status**: Draft
> **Ticket**: VISUAL-001
> **Depends on**: CONTENT-005 (CanonicalArticle Assembly — Done), CONTENT-002 (Section Drafting — Done)
> **Epic**: 4 — Visual Asset Generation

---

## 1. Overview

Add automatic data chart generation to the content pipeline. An LLM analyzes drafted article sections and proposes 0-3 chart specifications (bar, line, or pie). Matplotlib renders each spec to a PNG file. The resulting `ImageAsset` objects are attached to the `CanonicalArticle.visuals` field, which is already defined but currently empty.

Chart generation is best-effort — if no chartable data is found or rendering fails, the article publishes without visuals. No pipeline failure.

---

## 2. Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Chart data source | LLM reads drafted sections, proposes structured JSON chart specs | Section drafts are richer context than raw claims; LLM has creative freedom to pick best charts |
| Charts per article | 0-3, best-effort | Not every article has chartable data; graceful degradation to zero |
| Charting library | Matplotlib only | Static PNG output for articles; lightweight, no extra export deps. Plotly deferred to VISUAL-003 |
| Chart background | Transparent PNG | Matches backlog AC "Output as PNG with transparent background" |
| Markdown embedding | Deferred — charts referenced via `visuals` list only | Embedding chart images inline in `body_markdown` requires section drafter template changes; deferred to future enhancement. Backlog AC "Embedded in Markdown with caption" partially met via `ImageAsset.caption`. |
| Storage | Local filesystem (`generated_assets/charts/`) | Simple for dev; publishing pipeline (Epic 5) handles S3 upload later |
| Pipeline position | After `seo_optimize`, before `END` | Needs full article context (drafts, SEO metadata) but doesn't modify text |

---

## 3. Data Flow

```
seo_optimize → generate_charts → END

generate_charts:
  1. LLM reads section_drafts → proposes 0-3 ChartSpec as structured JSON
  2. For each valid ChartSpec:
     a. Matplotlib renders chart → saves PNG to {chart_output_dir}/{session_id}/{chart_id}.png
     b. Creates ImageAsset with file path as url, caption, alt_text
  3. Returns {"visuals": list[ImageAsset]}
  4. If LLM returns no specs or all renders fail → returns {"visuals": []}
```

Article assembler reads `visuals` from pipeline state instead of hardcoded `[]`.

---

## 4. New Types

### 4.1 New File: `src/models/visual.py`

```python
from enum import StrEnum
from pydantic import BaseModel, Field


class ChartType(StrEnum):
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

**Validation constraints:**
- `x_labels` and `y_values` must have equal length (validated in `propose_charts`)
- Pie chart `y_values` must all be positive (validated in `render_chart`)
- `source_section_index` must be within range of section_drafts

### 4.2 ContentState Update

Add to `ContentState` TypedDict in `src/agents/content/pipeline.py`:

```python
visuals: NotRequired[list[ImageAsset]]
```

### 4.3 ArticleDraft Update

Add to `ArticleDraft` in `src/models/content_pipeline.py`:

```python
visuals: list[ImageAsset] = Field(default_factory=list)
```

This field stores chart assets produced by the pipeline so they survive through `_store_drafted()` → `finalize_article()` → `assemble_canonical_article()`.

### 4.4 Settings Update

Add to `src/config/settings.py`:

```python
chart_output_dir: str = "generated_assets/charts"
```

---

## 5. Components

### 5.1 New File: `src/agents/content/chart_generator.py` (~120 lines)

Two focused functions:

#### `propose_charts(section_drafts, llm) -> list[ChartSpec]`

- Builds a prompt with all section draft text (titles + body_markdown)
- Asks LLM to return a JSON array of 0-3 chart specs
- Parses response, validates each spec via Pydantic
- **Post-Pydantic validation**: checks `len(x_labels) == len(y_values)` and `source_section_index < len(section_drafts)`. Specs failing these checks are discarded.
- Discards invalid specs with a warning log (structlog)
- Returns valid specs (may be empty list)

**LLM prompt structure:**
```
You are a data visualization expert. Read the article sections below and propose 0-3 data charts.

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
{sections_text}
```

#### `render_chart(spec, output_dir, session_id) -> ImageAsset | None`

- Creates output directory if needed: `{output_dir}/{session_id}/`
- Renders chart based on `spec.chart_type`:
  - **bar**: `plt.bar(x_labels, y_values)` with title, y_label, grid
  - **line**: `plt.plot(x_labels, y_values, marker='o')` with title, y_label, grid
  - **pie**: `plt.pie(y_values, labels=x_labels, autopct='%1.1f%%')` with title
- Styling: transparent background (`savefig(transparent=True)`), readable font sizes, tight layout
- Saves as PNG (150 DPI) to `{output_dir}/{session_id}/{chart_id}.png`
- Returns `ImageAsset(url=file_path, caption=spec.caption, alt_text=spec.title)`
- On any rendering error: logs warning, returns `None`

### 5.2 Modified File: `src/agents/content/nodes.py`

Add `make_chart_node()` factory function following existing pattern:

```python
def make_chart_node(llm: BaseChatModel, output_dir: str) -> Any:
    async def chart_node(state: ContentState) -> dict[str, object]:
        section_drafts = state.get("section_drafts", [])
        session_id = state["session_id"]
        if not section_drafts:
            return {"visuals": []}
        specs = await propose_charts(section_drafts, llm)
        visuals = []
        for spec in specs:
            asset = await asyncio.to_thread(render_chart, spec, output_dir, session_id)
            if asset is not None:
                visuals.append(asset)
        return {"visuals": visuals}
    return chart_node
```

Note: `render_chart` is synchronous (Matplotlib is not async-safe). Wrapped in `asyncio.to_thread()` to avoid blocking the event loop.

### 5.3 Modified File: `src/agents/content/pipeline.py`

Add chart node to the content graph:

```python
# After seo_optimize node
graph.add_node("generate_charts", make_chart_node(llm, settings.chart_output_dir))
graph.add_edge("seo_optimize", "generate_charts")
graph.add_edge("generate_charts", END)
# Remove existing: graph.add_edge("seo_optimize", END)
```

### 5.4 Modified File: `src/agents/content/article_assembler.py`

Change line 45 from:
```python
visuals=[],
```
To:
```python
visuals=visuals,
```

And accept visuals as a parameter:
```python
def assemble_canonical_article(
    draft: ArticleDraft,
    topic: TopicInput,
    visuals: list[ImageAsset] | None = None,
) -> CanonicalArticle:
```

Default `None` → `[]` inside the function to maintain backward compatibility.

### 5.5 Modified File: `src/services/content.py`

Update `_store_drafted()` to extract `visuals` from pipeline result and persist on the draft:

```python
# In _store_drafted(), after existing field assignments:
draft.visuals = result.get("visuals", [])
```

This ensures visuals flow from `ContentState` → `ArticleDraft` → `assemble_canonical_article`.

### 5.6 Modified File: `src/services/content_finalize.py`

Update `build_article` to pass visuals from the draft:

```python
def build_article(draft: ArticleDraft, topic: TopicInput) -> CanonicalArticle:
    return assemble_canonical_article(draft, topic, visuals=draft.visuals)
```

### 5.7 Modified File: `src/models/content_pipeline.py`

Add `visuals` field to `ArticleDraft` (see §4.3).

### 5.8 Modified File: `pyproject.toml`

Add dependency:
```
"matplotlib>=3.8.0",
```

---

## 6. Testing

### 6.1 `tests/unit/models/test_visual_models.py`

- ChartSpec validates valid bar/line/pie specs
- ChartSpec rejects empty title, empty labels, negative pie values
- ChartSpec rejects mismatched x_labels/y_values lengths (tested in propose_charts)
- ChartType enum contains exactly bar, line, pie

### 6.2 `tests/unit/agents/content/test_chart_generator.py`

**propose_charts tests:**
- LLM returns valid 2-chart JSON → returns 2 ChartSpec objects
- LLM returns empty array → returns empty list
- LLM returns malformed JSON → returns empty list (graceful)
- LLM returns mix of valid and invalid specs → returns only valid ones
- Mismatched x_labels/y_values length → spec discarded

**render_chart tests:**
- Bar chart renders to PNG file, file exists, is valid PNG
- Line chart renders to PNG file
- Pie chart renders to PNG file
- Returns ImageAsset with correct url, caption, alt_text
- Output directory created if missing
- Invalid spec (e.g., empty y_values after validation) → returns None

### 6.3 `tests/unit/agents/content/test_chart_node.py`

- Chart node with mocked LLM returning 2 specs → state has 2 ImageAsset visuals
- Chart node with mocked LLM returning empty → state has empty visuals list
- Chart node with no section_drafts → state has empty visuals list
- Chart node with one render failure → state has only successful charts

### 6.4 Existing Test Updates

- `test_article_assembler.py` — add test: visuals parameter populates CanonicalArticle.visuals
- `test_pipeline.py` — verify `generate_charts` node exists in graph and is wired after `seo_optimize`

### 6.5 Coverage Target

≥80% on all new files.

---

## 7. File Summary

| File | Type | ~Lines |
|------|------|--------|
| `src/models/visual.py` | New — models | ~30 |
| `src/agents/content/chart_generator.py` | New — core logic | ~120 |
| `src/agents/content/nodes.py` | Modified — add chart node | +15 |
| `src/agents/content/pipeline.py` | Modified — wire chart node | +5 |
| `src/agents/content/article_assembler.py` | Modified — accept visuals param | +5 |
| `src/models/content_pipeline.py` | Modified — add visuals to ArticleDraft | +1 |
| `src/services/content.py` | Modified — persist visuals in _store_drafted | +1 |
| `src/services/content_finalize.py` | Modified — pass draft.visuals through | +3 |
| `src/config/settings.py` | Modified — add chart_output_dir | +1 |
| `pyproject.toml` | Modified — add matplotlib | +1 |
| `tests/unit/models/test_visual_models.py` | New — tests | ~40 |
| `tests/unit/agents/content/test_chart_generator.py` | New — tests | ~120 |
| `tests/unit/agents/content/test_chart_node.py` | New — tests | ~60 |
| Existing test updates | Modified | +20 |
| **Total new/changed** | | **~420** |

---

## 8. Deferred Items

| Item | Reason | Future Ticket |
|------|--------|---------------|
| Plotly integration | Not needed for static PNG; add for interactive charts later | VISUAL-003 or future |
| S3 upload for chart PNGs | Publishing pipeline handles asset upload | PUBLISH-001+ |
| Markdown embedding of charts in body_markdown | Requires template changes in section drafter; charts referenced via visuals list for now | Future enhancement |
| Chart style customization per domain | YAGNI for initial implementation | Future enhancement |
| AI illustration generation | Separate ticket with Stable Diffusion | VISUAL-002 |
