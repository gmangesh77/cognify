"""Tests for diagram generation: Mermaid rendering and LLM proposal."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.content.diagram_generator import (
    MERMAID_RENDER_TIMEOUT_SECONDS,
    propose_diagrams,
    render_mermaid,
)
from src.models.content_pipeline import SectionDraft
from src.models.visual import DiagramType


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
    "mermaid_syntax": (
        "sequenceDiagram\n    Client->>Server: GET /api\n    Server-->>Client: 200 OK"
    ),
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

    def test_render_timeout_allows_cold_concurrent_chromium_launches(self) -> None:
        # Two concurrent first-run mmdc renders measured 13.1s on an idle
        # loop; the old 15s ceiling timed out under real generation load
        # (2026-09-01 regression — three articles published without PNGs).
        assert MERMAID_RENDER_TIMEOUT_SECONDS >= 60

    @pytest.mark.asyncio
    async def test_render_passes_configured_timeout_to_wait_for(
        self, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "test.png"
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        captured: dict[str, float] = {}

        async def _fake_wait_for(
            awaitable: object, timeout: float
        ) -> tuple[bytes, bytes]:
            captured["timeout"] = timeout
            return await awaitable  # type: ignore[misc]

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", new=_fake_wait_for),
        ):
            await render_mermaid("graph TD\n    A-->B", output_file)
        assert captured["timeout"] == MERMAID_RENDER_TIMEOUT_SECONDS

    @pytest.mark.asyncio
    async def test_timeout_kills_the_subprocess(self, tmp_path: Path) -> None:
        # wait_for only cancels our await — the wedged mmdc/Chromium must be
        # killed explicitly or it leaks (one orphan per timed-out render).
        output_file = tmp_path / "test.png"
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.kill = MagicMock()

        async def _timeout(awaitable: object, timeout: float) -> None:
            close = getattr(awaitable, "close", None)
            if callable(close):
                close()  # avoid "coroutine never awaited" warnings
            raise TimeoutError

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", new=_timeout),
        ):
            result = await render_mermaid("graph TD\n    A-->B", output_file)
        assert result is False
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_explicit_timeout_argument_wins(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test.png"
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        captured: dict[str, float] = {}

        async def _fake_wait_for(
            awaitable: object, timeout: float
        ) -> tuple[bytes, bytes]:
            captured["timeout"] = timeout
            return await awaitable  # type: ignore[misc]

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", new=_fake_wait_for),
        ):
            await render_mermaid("graph TD\n    A-->B", output_file, 42.0)
        assert captured["timeout"] == 42.0

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
        llm.ainvoke.return_value = MagicMock(content=json.dumps([VALID_SPEC]))
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
        llm.ainvoke.return_value = MagicMock(content=json.dumps([bad_spec]))
        result = await propose_diagrams([_make_section(0, "Text.")], llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_truncates_to_max_five(self) -> None:
        specs = [{**VALID_SPEC, "title": f"Diagram {i}"} for i in range(7)]
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps(specs))
        result = await propose_diagrams([_make_section(0, "Text.")], llm)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_accepts_overview_diagram_section_index(self) -> None:
        overview = {**VALID_SPEC, "source_section_index": -1, "title": "Overview"}
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps([overview]))
        sections = [_make_section(0, "Body.")]
        result = await propose_diagrams(sections, llm)
        assert len(result) == 1
        assert result[0].source_section_index == -1

    @pytest.mark.asyncio
    async def test_accepts_extended_diagram_types(self) -> None:
        class_spec = {
            "diagram_type": "class",
            "title": "Entity Classes",
            "mermaid_syntax": "classDiagram\n    class Foo {\n      +bar()\n    }",
            "caption": "Core entities.",
            "source_section_index": 0,
        }
        state_spec = {
            "diagram_type": "state",
            "title": "Lifecycle",
            "mermaid_syntax": "stateDiagram-v2\n    [*] --> Idle\n    Idle --> Done",
            "caption": "Request lifecycle.",
            "source_section_index": 0,
        }
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content=json.dumps([class_spec, state_spec])
        )
        result = await propose_diagrams([_make_section(0, "Text.")], llm)
        assert len(result) == 2
        assert {r.diagram_type for r in result} == {
            DiagramType.CLASS,
            DiagramType.STATE,
        }
