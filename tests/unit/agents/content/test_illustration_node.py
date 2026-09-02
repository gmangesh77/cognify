"""Tests for illustration generation pipeline node."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from PIL import Image

from src.agents.content.illustration_generator import (
    HERO_CANONICAL_HEIGHT,
    HERO_CANONICAL_WIDTH,
    normalize_hero_image,
)
from src.agents.content.nodes import make_illustration_node
from src.models.content import ImageAsset
from src.models.content_pipeline import SEOResult
from src.models.research import TopicInput


def _make_png_bytes(width: int = 1792, height: int = 1024) -> bytes:
    """Create a real PNG with the given dimensions for test fixtures."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


_DEFAULT = object()


def _make_mock_generator(image_bytes: bytes | None = _DEFAULT) -> AsyncMock:  # type: ignore[assignment]
    gen = AsyncMock()
    if image_bytes is _DEFAULT:
        gen.generate.return_value = _make_png_bytes()
    else:
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
            seo=SEOMetadata(
                title="Meta Title for Test",
                description="A test meta description for the article.",
            ),
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
        # Hero illustration is prepended (so it appears first in published
        # articles); original chart is preserved at index 1.
        assert result["visuals"][0].metadata["type"] == "hero"
        assert result["visuals"][1].url == existing.url
        assert result["visuals"][1].caption == existing.caption

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
    async def test_returns_existing_visuals_on_generator_failure(
        self, tmp_path
    ) -> None:
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

    @pytest.mark.asyncio
    async def test_saved_hero_has_canonical_dimensions(self, tmp_path) -> None:
        """Whatever DALL-E returns, the saved hero.png is always 1600x900."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A prompt")
        # Simulate DALL-E returning its standard 1792x1024 landscape
        gen = _make_mock_generator(image_bytes=_make_png_bytes(1792, 1024))
        node = make_illustration_node(llm, gen, str(tmp_path))
        state = _make_state()
        result = await node(state)
        assert len(result["visuals"]) == 1
        hero = result["visuals"][0]
        # Metadata reflects the canonical size
        assert hero.metadata["width"] == HERO_CANONICAL_WIDTH
        assert hero.metadata["height"] == HERO_CANONICAL_HEIGHT
        # The saved PNG is actually 1600x900 on disk
        with Image.open(hero.url) as img:
            assert img.size == (HERO_CANONICAL_WIDTH, HERO_CANONICAL_HEIGHT)


class TestNormalizeHeroImage:
    def test_resizes_widescreen_source_to_canonical(self) -> None:
        """1792x1024 input -> exact 1600x900 output."""
        src = _make_png_bytes(1792, 1024)
        result = normalize_hero_image(src)
        with Image.open(BytesIO(result)) as img:
            assert img.size == (HERO_CANONICAL_WIDTH, HERO_CANONICAL_HEIGHT)

    def test_crops_square_source_to_canonical(self) -> None:
        """1024x1024 square input -> exact 1600x900 output (upscaled + cropped)."""
        src = _make_png_bytes(1024, 1024)
        result = normalize_hero_image(src)
        with Image.open(BytesIO(result)) as img:
            assert img.size == (HERO_CANONICAL_WIDTH, HERO_CANONICAL_HEIGHT)

    def test_handles_ultra_wide_source(self) -> None:
        """3000x800 ultra-wide input is still normalized to 1600x900."""
        src = _make_png_bytes(3000, 800)
        result = normalize_hero_image(src)
        with Image.open(BytesIO(result)) as img:
            assert img.size == (HERO_CANONICAL_WIDTH, HERO_CANONICAL_HEIGHT)

    def test_handles_tall_source(self) -> None:
        """Tall 800x1600 input is still normalized to 1600x900."""
        src = _make_png_bytes(800, 1600)
        result = normalize_hero_image(src)
        with Image.open(BytesIO(result)) as img:
            assert img.size == (HERO_CANONICAL_WIDTH, HERO_CANONICAL_HEIGHT)
