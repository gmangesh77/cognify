"""Tests for chart generation pipeline node."""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agents.content.nodes import make_chart_node
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
    "chart_type": "bar",
    "title": "Test Chart",
    "x_labels": ["A", "B"],
    "y_values": [10.0, 20.0],
    "y_label": "Count",
    "caption": "A test chart.",
    "source_section_index": 0,
}


class TestChartNode:
    @pytest.mark.asyncio
    async def test_produces_visuals_from_llm_specs(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = AsyncMock(content=json.dumps([VALID_SPEC]))
        node = make_chart_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Attacks: A=10, B=20.")],
        }
        result = await node(state)
        assert "visuals" in result
        assert len(result["visuals"]) == 1
        assert result["visuals"][0].caption == "A test chart."

    @pytest.mark.asyncio
    async def test_returns_empty_visuals_for_no_specs(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = AsyncMock(content="[]")
        node = make_chart_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "No data.")],
        }
        result = await node(state)
        assert result["visuals"] == []

    @pytest.mark.asyncio
    async def test_returns_empty_visuals_for_no_drafts(self, tmp_path) -> None:
        llm = AsyncMock()
        node = make_chart_node(llm, str(tmp_path))
        state = {"session_id": uuid4()}
        result = await node(state)
        assert result["visuals"] == []

    @pytest.mark.asyncio
    async def test_skips_failed_renders(self, tmp_path) -> None:
        bad_spec = {
            **VALID_SPEC,
            "y_values": [],  # will fail Pydantic validation (min_length=2)
        }
        good_spec = VALID_SPEC
        llm = AsyncMock()
        llm.ainvoke.return_value = AsyncMock(content=json.dumps([bad_spec, good_spec]))
        node = make_chart_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Data.")],
        }
        result = await node(state)
        # bad_spec is discarded by propose_charts (min_length=2), only good_spec renders
        assert len(result["visuals"]) == 1
