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
