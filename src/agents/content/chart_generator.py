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
            if spec.source_section_index >= len(section_drafts):
                logger.warning("chart_spec_section_out_of_range", title=spec.title)
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
            metadata={"chart_type": str(spec.chart_type), "source_section": spec.source_section_index},
        )
    except Exception as exc:
        logger.warning("chart_render_failed", error=str(exc), title=spec.title)
        plt.close("all")
        return None
