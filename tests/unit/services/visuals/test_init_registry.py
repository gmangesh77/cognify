"""Tests for `init_registry()` — provider auto-registration from settings."""

from __future__ import annotations

from src.config.settings import Settings
from src.services.visuals import init_registry


def test_no_credentials_registers_nothing() -> None:
    settings = Settings(
        openai_api_key="",
        google_ai_api_key="",
        gemini_3_pro_enabled=True,
        imagen_4_enabled=True,
    )
    registry = init_registry(settings)
    assert registry.available_providers() == []


def test_only_openai_registers_dalle_3() -> None:
    settings = Settings(
        openai_api_key="sk-test",
        google_ai_api_key="",
        gemini_3_pro_enabled=True,
        imagen_4_enabled=True,
    )
    registry = init_registry(settings)
    assert "dalle_3" in registry.available_providers()
    assert "gemini_flash" not in registry.available_providers()


def test_only_google_registers_flash_and_pro_when_enabled() -> None:
    settings = Settings(
        openai_api_key="",
        google_ai_api_key="g-test",
        gemini_3_pro_enabled=True,
        imagen_4_enabled=False,
    )
    registry = init_registry(settings)
    assert set(registry.available_providers()) == {"gemini_flash", "gemini_3_pro"}


def test_all_credentials_and_flags_register_all_four() -> None:
    settings = Settings(
        openai_api_key="sk-test",
        google_ai_api_key="g-test",
        gemini_3_pro_enabled=True,
        imagen_4_enabled=True,
    )
    registry = init_registry(settings)
    assert set(registry.available_providers()) == {
        "dalle_3",
        "gemini_flash",
        "gemini_3_pro",
        "imagen_4",
    }


def test_imagen_4_disabled_flag_excludes_provider() -> None:
    settings = Settings(
        openai_api_key="",
        google_ai_api_key="g-test",
        gemini_3_pro_enabled=True,
        imagen_4_enabled=False,
    )
    registry = init_registry(settings)
    assert "imagen_4" not in registry.available_providers()


def test_gemini_3_pro_disabled_flag_excludes_provider() -> None:
    settings = Settings(
        openai_api_key="",
        google_ai_api_key="g-test",
        gemini_3_pro_enabled=False,
        imagen_4_enabled=True,
    )
    registry = init_registry(settings)
    assert "gemini_3_pro" not in registry.available_providers()
    assert "gemini_flash" in registry.available_providers()
    assert "imagen_4" in registry.available_providers()
