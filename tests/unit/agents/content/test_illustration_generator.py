"""Tests for illustration generation: ImageGenerator protocol and prompt crafting."""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.content.illustration_generator import (
    OpenAIDalleGenerator,
)


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
