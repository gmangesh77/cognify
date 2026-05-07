"""Tests for ImageRenderResult schema + provider error hierarchy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.services.visuals.providers.base import (
    ImageProviderError,
    ImageProviderInvalidRequestError,
    ImageProviderQuotaError,
    ImageProviderTimeoutError,
    ImageRenderResult,
)


def test_image_render_result_valid_minimum() -> None:
    result = ImageRenderResult(
        image_bytes=b"\x89PNG",
        width=1600,
        height=900,
        prompt_used="a researcher at a desk",
        model="imagen-4.0-generate-001",
        provider="imagen_4",
        cost_usd=0.04,
        latency_ms=2400,
    )
    assert result.mime_type == "image/png"
    assert result.width == 1600
    assert result.height == 900


def test_image_render_result_rejects_zero_dimensions() -> None:
    with pytest.raises(ValidationError):
        ImageRenderResult(
            image_bytes=b"x",
            width=0,
            height=900,
            prompt_used="p",
            model="m",
            provider="p",
            latency_ms=0,
        )


def test_image_render_result_rejects_negative_cost() -> None:
    with pytest.raises(ValidationError):
        ImageRenderResult(
            image_bytes=b"x",
            width=100,
            height=100,
            prompt_used="p",
            model="m",
            provider="p",
            cost_usd=-0.01,
            latency_ms=0,
        )


def test_cost_usd_optional() -> None:
    """Some providers may not report cost (free tier, local model)."""
    result = ImageRenderResult(
        image_bytes=b"x",
        width=1,
        height=1,
        prompt_used="p",
        model="m",
        provider="p",
        latency_ms=10,
    )
    assert result.cost_usd is None


def test_image_provider_error_includes_provider_in_str() -> None:
    err = ImageProviderError("imagen_4", "billing not enabled")
    assert "imagen_4" in str(err)
    assert "billing not enabled" in str(err)
    assert err.provider == "imagen_4"


def test_subclass_errors_inherit_provider_attr() -> None:
    quota = ImageProviderQuotaError("gemini_flash", "rate exceeded")
    timeout = ImageProviderTimeoutError("dalle_3", "30s budget")
    invalid = ImageProviderInvalidRequestError("gemini_3_pro", "prompt too long")
    assert quota.provider == "gemini_flash"
    assert timeout.provider == "dalle_3"
    assert invalid.provider == "gemini_3_pro"
    # All subclass the base for catch-all handling.
    assert isinstance(quota, ImageProviderError)
    assert isinstance(timeout, ImageProviderError)
    assert isinstance(invalid, ImageProviderError)
