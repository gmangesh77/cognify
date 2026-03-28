"""Tests for illustration generation: ImageGenerator protocol and prompt crafting."""

import base64
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.agents.content.illustration_generator import (
    OpenAIDalleGenerator,
    generate_illustration_prompt,
)
from src.models.research import TopicInput


class TestOpenAIDalleGenerator:
    @pytest.mark.asyncio
    async def test_returns_bytes_on_success(self) -> None:
        fake_image = b"fake-png-bytes"
        b64_image = base64.b64encode(fake_image).decode()
        mock_client = AsyncMock()
        mock_client.images.generate.return_value = MagicMock(
            data=[MagicMock(b64_json=b64_image)]
        )
        generator = OpenAIDalleGenerator.__new__(OpenAIDalleGenerator)
        generator._client = mock_client
        generator._model = "dall-e-3"
        result = await generator.generate("a cybersecurity illustration", (1024, 1024))
        assert result == fake_image

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self) -> None:
        mock_client = AsyncMock()
        mock_client.images.generate.side_effect = Exception("API rate limit")
        generator = OpenAIDalleGenerator.__new__(OpenAIDalleGenerator)
        generator._client = mock_client
        generator._model = "dall-e-3"
        result = await generator.generate("test prompt", (1024, 1024))
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_response(self) -> None:
        mock_client = AsyncMock()
        mock_client.images.generate.return_value = MagicMock(data=[])
        generator = OpenAIDalleGenerator.__new__(OpenAIDalleGenerator)
        generator._client = mock_client
        generator._model = "dall-e-3"
        result = await generator.generate("test prompt", (1024, 1024))
        assert result is None


class TestGenerateIllustrationPrompt:
    @pytest.mark.asyncio
    async def test_returns_prompt_string(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content=(
                "A futuristic digital shield protecting a network of connected devices"
            )
        )
        topic = TopicInput(
            id=uuid4(),
            title="AI Security Trends",
            description="Emerging threats",
            domain="cybersecurity",
        )
        result = await generate_illustration_prompt(
            topic, "Summary of AI security trends in 2026", llm
        )
        assert result is not None
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_failure(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.side_effect = Exception("LLM unavailable")
        topic = TopicInput(
            id=uuid4(),
            title="Test",
            description="Desc",
            domain="tech",
        )
        result = await generate_illustration_prompt(topic, "Summary", llm)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_response(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="")
        topic = TopicInput(
            id=uuid4(),
            title="Test",
            description="Desc",
            domain="tech",
        )
        result = await generate_illustration_prompt(topic, "", llm)
        assert result is None

    @pytest.mark.asyncio
    async def test_uses_topic_description_when_no_summary(self) -> None:
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="A prompt about emerging threats")
        topic = TopicInput(
            id=uuid4(),
            title="Test",
            description="Emerging threats in cybersecurity",
            domain="tech",
        )
        result = await generate_illustration_prompt(topic, "", llm)
        assert result is not None
        # Verify the LLM was called with topic.description as fallback
        call_args = str(llm.ainvoke.call_args)
        assert "Emerging threats in cybersecurity" in call_args
