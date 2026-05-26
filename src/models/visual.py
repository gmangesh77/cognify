"""Models for visual asset generation (charts, diagrams, planner specs).

`ImageSpec` is the planner output (one entry per planned image). The
companion render output is `src.models.content.ImageAsset`; each rendered
asset carries `metadata["spec_id"]` linking it back to its plan. See
ADR-005 for boundary rationale.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

ImageRoleStyle = Literal[
    "hero",
    "feature_card",
    "concept",
    "process_step",
    "comparison_split",
    "quote_card",
    "stat_card",
    "screenshot_mock",
    "editorial",
    "background",
]

ImageAspectRatio = Literal["16:9", "1:1", "4:3", "3:4", "4:5"]

PlacementAnchor = Literal[
    "cover",
    "top",
    "before_heading",
    "between_paragraphs",
    "bottom_grid",
    "background",
    "column_split",
]

ImageProviderKey = Literal[
    "gemini_flash",
    "gemini_3_pro",
    "imagen_4",
    "dalle_3",
]


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


class DiagramType(StrEnum):
    """Supported diagram types (rendered via mermaid-cli / mermaid.js)."""

    FLOWCHART = "flowchart"
    SEQUENCE = "sequence"
    CLASS = "class"
    STATE = "state"
    ER = "er"
    JOURNEY = "journey"


class DiagramSpec(BaseModel, frozen=True):
    """LLM-proposed diagram specification with Mermaid syntax.

    `source_section_index = -1` marks an article-level overview diagram
    (rendered above the body). Non-negative values index into the section
    drafts list.
    """

    diagram_type: DiagramType
    title: str = Field(min_length=1, max_length=120)
    mermaid_syntax: str = Field(min_length=10)
    caption: str = Field(min_length=1, max_length=200)
    source_section_index: int = Field(ge=-1)


class ImagePlacement(BaseModel):
    """Where an `ImageSpec` should be inserted into the rendered article.

    `section_index = -1` marks an article-level placement (cover, hero,
    background) rather than a section-level one. `heading_text` and
    `paragraph_index` are anchor-specific hints used by the markdown
    injector (see `src/services/visuals/inject.py` — Phase 3).
    """

    anchor: PlacementAnchor = "top"
    heading_text: str | None = None
    paragraph_index: int | None = None
    section_index: int = -1


class ImageSpec(BaseModel):
    """Planner output describing one image to render.

    The renderer turns this into a concrete `ImageAsset` whose
    `metadata["spec_id"]` links back to `ImageSpec.id`. `prompt` is the
    *subject* only; the visual style fragment and page art direction are
    layered in by `prompt_composer.build_prompt` at render time.
    """

    id: str = Field(min_length=1, max_length=64)
    role_style: ImageRoleStyle
    visual_style: str | None = None
    prompt: str = Field(min_length=1, max_length=2000)
    alt_text: str = ""
    # Reader-facing figure caption — a short plain title (e.g. "Pod DNS
    # Query Flow"). Rendered as the article <figcaption>. Must NOT contain
    # planning meta-commentary; `rationale` is the internal field for that.
    caption: str | None = Field(default=None, max_length=120)
    aspect_ratio: ImageAspectRatio = "16:9"
    placement: ImagePlacement = Field(default_factory=ImagePlacement)
    rationale: str | None = None
    provider: ImageProviderKey | None = None
    # VISUAL-012 — set when structural_diagram_mode == "mermaid" for a
    # structural role. When present, the render node renders Mermaid to PNG
    # (via mermaid-cli) instead of calling an image provider.
    mermaid_syntax: str | None = None
    diagram_type: str | None = None
