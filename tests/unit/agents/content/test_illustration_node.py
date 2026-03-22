"""Tests for illustration generation pipeline node."""

import base64
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.agents.content.nodes import make_illustration_node
from src.models.content import ImageAsset
from src.models.content_pipeline import SEOResult
from src.models.research import TopicInput


def _make_mock_generator(image_bytes: bytes | None = b"fake-png") -> AsyncMock:
    gen = AsyncMock()
    gen.generate.return_value = image_bytes
    return gen


def _make_state(
    topic_title: str = "AI Security",
    summary: str = "Summary of trends",
    existing_visuals: list | None = None,
) -> dict:
    from src.models.content import Provenance, SEOMetadata
    return {
        "topic": TopicInput(
            id=uuid4(), title=topic_title, description="Desc", domain="cybersecurity"
        ),
        "session_id": uuid4(),
        "seo_result": SEOResult(
            seo=SEOMetadata(title="Meta Title for Test", description="A test meta description for the article."),
            summary=summary,
            key_claims=["claim"],
            provenance=Provenance(
                research_session_id=uuid4(),
                primary_model="claude-sonnet-4",
                drafting_model="claude-sonnet-4",
                embedding_model="all-MiniLM-L6-v2",
                embedding_version="v1",
            ),
            ai_disclosure="AI generated",
        ),
        "visuals": existing_visuals or [],
    }


class TestIllustrationNode:
    @pytest.mark.asyncio
    async def test_produces_hero_image(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A glowing digital shield")
        gen = _make_mock_generator()
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = _make_state()
        result = await node(state)
        assert len(result["visuals"]) == 1
        asset = result["visuals"][0]
        assert isinstance(asset, ImageAsset)
        assert asset.metadata["type"] == "hero"
        assert asset.metadata["generator"] == "dall-e-3"
        # Verify file actually written to disk
        assert (tmp_path / str(state["session_id"]) / "hero.png").exists()

    @pytest.mark.asyncio
    async def test_preserves_existing_chart_visuals(self, tmp_path) -> None:
        existing = ImageAsset(url="/charts/foo.png", caption="Chart")
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A prompt")
        gen = _make_mock_generator()
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = _make_state(existing_visuals=[existing])
        result = await node(state)
        assert len(result["visuals"]) == 2
        assert result["visuals"][0] == existing
        assert result["visuals"][1].metadata["type"] == "hero"

    @pytest.mark.asyncio
    async def test_returns_existing_visuals_on_prompt_failure(self, tmp_path) -> None:
        existing = ImageAsset(url="/charts/foo.png", caption="Chart")
        llm = AsyncMock()
        llm.ainvoke.side_effect = Exception("LLM down")
        gen = _make_mock_generator()
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = _make_state(existing_visuals=[existing])
        result = await node(state)
        assert result["visuals"] == [existing]

    @pytest.mark.asyncio
    async def test_returns_existing_visuals_on_generator_failure(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A prompt")
        gen = _make_mock_generator(image_bytes=None)
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = _make_state()
        result = await node(state)
        assert result["visuals"] == []

    @pytest.mark.asyncio
    async def test_falls_back_to_topic_description_when_no_seo(self, tmp_path) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A prompt")
        gen = _make_mock_generator()
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = {
            "topic": TopicInput(
                id=uuid4(), title="Test", description="Topic description", domain="tech"
            ),
            "session_id": uuid4(),
        }
        result = await node(state)
        assert len(result["visuals"]) == 1
