# VISUAL-012 — Per-article Mermaid vs Diffusion diagram toggle

**Status:** In Progress
**Branch:** `feature/mermaid-diagram-toggle`
**Date:** 2026-05-26

## Goal
Let each article choose how **structural diagrams** are rendered:
- `illustration` (default) — gpt-image-1 diffusion render (current behavior).
- `mermaid` — deterministic Mermaid diagrams (crisp, typo-free text) for
  structural-diagram roles only. Hero / editorial / stat / background stay
  diffusion regardless.

"Structural" roles = `concept`, `process_step`, `comparison_split`
(reuses `prompt_composer.LABELED_ROLE_STYLES` minus `stat_card` /
`screenshot_mock`, which are not graph-shaped).

## Decisions (confirmed with user)
- Toggle lives **per-article in the Generate modal** (not global).
- Mermaid replaces **only structural-diagram roles**.

## Design
The **planner** owns Mermaid generation (it has the LLM + full section
context). The **render node** renders whatever the spec carries.

1. `ImageSpec` gains `mermaid_syntax: str | None` and
   `diagram_type: str | None`.
2. `image_planner_node`, when `structural_diagram_mode == "mermaid"`,
   runs a follow-up LLM call per structural-role spec to fill
   `mermaid_syntax` (+ `diagram_type`). Non-structural specs untouched.
3. `image_render_node._render_one`: if `spec.mermaid_syntax` is set,
   render it to PNG via the existing `render_mermaid` (mermaid-cli) and
   emit an `ImageAsset` with metadata `{mermaid_syntax, diagram_type,
   section_index, placement_anchor, spec_id, caption}`. If the CLI render
   fails, still emit the asset (urlless) so the dashboard client renderer
   (`MermaidDiagram`) shows it from syntax. Otherwise the existing
   provider path runs.
4. Publishing: planner-mermaid assets carry a PNG url + `spec_id`, so
   `inject.py`'s existing planned-bucket path injects them unchanged. No
   inject change required.

## Param threading (mirror `keywords` / `content_tone`)
`structural_diagram_mode: Literal["illustration","mermaid"] = "illustration"`
through every hop:
1. Frontend `generate-article-modal.tsx` — new "Diagram style" select.
2. `ArticleParams` + `createResearchSession` (`lib/api/trends.ts`).
3. `CreateResearchSessionRequest` (api/schemas/research.py).
4. `research.py` router → `ResearchService.start_session`.
5. `ResearchSession` pydantic model (models/research_db.py).
6. `ResearchSessionRow` column + Alembic migration (db/tables.py).
7. `ContentState` (agents/content/pipeline.py) + content/__init__ invoke.
8. `make_image_planner_node` reads it from state.

## Frontend
- Generate modal: `Diagram style: AI illustration | Mermaid` select.
- `article-content.tsx`: diagram bucketing currently keys on
  `source_section`; planner-mermaid assets stamp `section_index`. Fix
  `isDiagramVisual` bucketing to use `section_index ?? source_section`
  (same gap fixed earlier for images). `MermaidDiagram` client renderer
  already exists.

## Tests
- Threading: param flows request → session → state → planner.
- Planner: structural spec gets `mermaid_syntax` in mermaid mode; hero
  does not; illustration mode leaves all specs syntax-free.
- Render node: spec with `mermaid_syntax` → mermaid PNG path + diagram
  metadata; without → provider path.
- Frontend: diagram bucketed by `section_index`.

## Verify
Generate one article in each mode; confirm illustration mode unchanged,
mermaid mode renders crisp Mermaid diagrams in the structural sections.
