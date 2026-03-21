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
