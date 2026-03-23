"""Tests for diagram generation pipeline node."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.agents.content.nodes import make_diagram_node
from src.models.content import ImageAsset
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
    "diagram_type": "flowchart",
    "title": "Auth Flow",
    "mermaid_syntax": "graph TD\n    A[Start] --> B[Login] --> C[Dashboard]",
    "caption": "Authentication flow.",
    "source_section_index": 0,
}


class TestDiagramNode:
    @pytest.mark.asyncio
    async def test_produces_diagram_assets(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps([VALID_SPEC]))
        node = make_diagram_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Auth flow: login then dashboard.")],
        }
        with patch(
            "src.agents.content.nodes.render_mermaid",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await node(state)
        assert len(result["visuals"]) == 1
        asset = result["visuals"][0]
        assert isinstance(asset, ImageAsset)
        assert asset.metadata["diagram_type"] == "flowchart"

    @pytest.mark.asyncio
    async def test_preserves_existing_visuals(self, tmp_path) -> None:
        existing = ImageAsset(url="/charts/foo.png", caption="Chart")
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps([VALID_SPEC]))
        node = make_diagram_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Text.")],
            "visuals": [existing],
        }
        with patch(
            "src.agents.content.nodes.render_mermaid",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await node(state)
        assert len(result["visuals"]) == 2
        assert result["visuals"][0] == existing

    @pytest.mark.asyncio
    async def test_returns_existing_on_no_drafts(self, tmp_path) -> None:
        existing = ImageAsset(url="/charts/foo.png", caption="Chart")
        llm = AsyncMock()
        node = make_diagram_node(llm, str(tmp_path))
        state = {"session_id": uuid4(), "visuals": [existing]}
        result = await node(state)
        assert result["visuals"] == [existing]

    @pytest.mark.asyncio
    async def test_skips_failed_renders_keeps_successful(self, tmp_path) -> None:
        specs = [
            VALID_SPEC,
            {**VALID_SPEC, "diagram_type": "sequence", "title": "Good Diagram",
             "mermaid_syntax": "sequenceDiagram\n    A->>B: Request"},
        ]
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content=json.dumps(specs))
        node = make_diagram_node(llm, str(tmp_path))
        state = {
            "session_id": uuid4(),
            "section_drafts": [_make_section(0, "Text.")],
        }
        # First render fails, second succeeds
        with patch(
            "src.agents.content.nodes.render_mermaid",
            new_callable=AsyncMock,
            side_effect=[False, True],
        ):
            result = await node(state)
        assert len(result["visuals"]) == 1
