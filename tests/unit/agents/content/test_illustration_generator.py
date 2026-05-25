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

    @pytest.mark.asyncio
    async def test_falls_back_to_url_when_b64_absent(self) -> None:
        """Legacy dall-e-3 returns url; gpt-image-1 returns b64_json. Handle both."""
        import httpx

        fake_image = b"\x89PNG-from-url"
        mock_client = AsyncMock()
        mock_client.images.generate.return_value = MagicMock(
            data=[MagicMock(b64_json=None, url="https://example.invalid/img.png")]
        )
        generator = OpenAIDalleGenerator.__new__(OpenAIDalleGenerator)
        generator._client = mock_client
        generator._model = "dall-e-3"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=fake_image)

        transport = httpx.MockTransport(handler)
        original_init = httpx.AsyncClient.__init__

        def patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        httpx.AsyncClient.__init__ = patched_init  # type: ignore[method-assign]
        try:
            result = await generator.generate("prompt", (1024, 1024))
        finally:
            httpx.AsyncClient.__init__ = original_init  # type: ignore[method-assign]
        assert result == fake_image

    @pytest.mark.asyncio
    async def test_does_not_send_response_format_param(self) -> None:
        """OpenAI rejects response_format with HTTP 400 on unified Images API."""
        fake_image = b"x"
        b64_image = base64.b64encode(fake_image).decode()
        mock_client = AsyncMock()
        mock_client.images.generate.return_value = MagicMock(
            data=[MagicMock(b64_json=b64_image)]
        )
        generator = OpenAIDalleGenerator.__new__(OpenAIDalleGenerator)
        generator._client = mock_client
        generator._model = "gpt-image-1"
        await generator.generate("p", (1024, 1024))
        kwargs = mock_client.images.generate.await_args.kwargs
        assert "response_format" not in kwargs


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
