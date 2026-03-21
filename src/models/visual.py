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
