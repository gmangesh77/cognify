"""Tests for visual asset models."""

import pytest
from pydantic import ValidationError

from src.models.visual import ChartSpec, ChartType, DiagramSpec, DiagramType


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
