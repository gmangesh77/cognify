"""Tests for diagram generation: Mermaid rendering and LLM proposal."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.agents.content.diagram_generator import propose_diagrams, render_mermaid
from src.models.content_pipeline import SectionDraft
from src.models.visual import DiagramSpec, DiagramType


def _make_section(index: int, body: str) -> SectionDraft:
    return SectionDraft(
        section_index=index,
        title=f"Section {index}",
        body_markdown=body,
        word_count=len(body.split()),
        citations_used=[],
    )


VALID_SPEC = {
    "diagram_type": "flowchart",
    "title": "Auth Flow",
    "mermaid_syntax": "graph TD\n    A[Start] --> B[Login] --> C[Dashboard]",
    "caption": "Authentication flow overview.",
    "source_section_index": 0,
}

VALID_SEQUENCE_SPEC = {
    "diagram_type": "sequence",
    "title": "API Call",
    "mermaid_syntax": "sequenceDiagram\n    Client->>Server: GET /api\n    Server-->>Client: 200 OK",
    "caption": "API request sequence.",
    "source_section_index": 0,
}


class TestRenderMermaid:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.png"
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await render_mermaid("graph TD\n    A-->B", output_file)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_nonzero_exit(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.png"
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"parse error"))
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await render_mermaid("invalid syntax", output_file)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_file_not_found(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.png"
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("mmdc not found"),
        ):
            result = await render_mermaid("graph TD\n    A-->B", output_file)
        assert result is False


class TestProposeDiagrams:
    @pytest.mark.asyncio
    async def test_returns_valid_specs(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content=json.dumps([VALID_SPEC])
        )
        sections = [_make_section(0, "The auth flow starts with login.")]
        result = await propose_diagrams(sections, llm)
        assert len(result) == 1
        assert result[0].diagram_type == DiagramType.FLOWCHART

    @pytest.mark.asyncio
    async def test_returns_empty_on_empty_array(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="[]")
        result = await propose_diagrams([_make_section(0, "No diagrams.")], llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_malformed_json(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="not json")
        result = await propose_diagrams([_make_section(0, "Text.")], llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_discards_invalid_keeps_valid(self) -> None:
        bad_spec = {**VALID_SPEC, "title": ""}  # empty title fails min_length=1
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content=json.dumps([bad_spec, VALID_SEQUENCE_SPEC])
        )
        sections = [_make_section(0, "Text.")]
        result = await propose_diagrams(sections, llm)
        assert len(result) == 1
        assert result[0].diagram_type == DiagramType.SEQUENCE

    @pytest.mark.asyncio
    async def test_discards_out_of_range_section_index(self) -> None:
        bad_spec = {**VALID_SPEC, "source_section_index": 5}
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content=json.dumps([bad_spec])
        )
        result = await propose_diagrams([_make_section(0, "Text.")], llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_truncates_to_max_two(self) -> None:
        specs = [VALID_SPEC, VALID_SEQUENCE_SPEC, {**VALID_SPEC, "title": "Third"}]
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps(specs))
        result = await propose_diagrams([_make_section(0, "Text.")], llm)
        assert len(result) <= 2
