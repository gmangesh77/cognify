"""Tests for the three Google AI image providers (Flash, 3 Pro, Imagen 4).

Mocks `google.generativeai` via `sys.modules` injection so tests don't
require the real SDK to be installed. Validates the lazy-import error
path, the aspect-instruction injection, the Imagen aspect snap map,
and the Pydantic result shape.
"""

from __future__ import annotations

import sys
import types
from typing import cast

import pytest

from src.services.visuals.providers._google_base import (
    IMAGEN_ASPECT_MAP,
    aspect_instruction,
)
from src.services.visuals.providers.base import ImageProviderError
from src.services.visuals.providers.gemini_3_pro import Gemini3ProProvider
from src.services.visuals.providers.gemini_flash import GeminiFlashProvider
from src.services.visuals.providers.imagen_4 import Imagen4Provider


def _install_fake_genai(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: object,
    is_imagen: bool = False,
) -> list[str]:
    """Create a fake `google.generativeai` module and install in sys.modules.

    Returns a list captured by the fake `configure()` so tests can assert
    that the API key was forwarded.
    """
    captured_keys: list[str] = []

    def configure(api_key: str = "") -> None:
        captured_keys.append(api_key)

    class FakeModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def generate_content(self, prompt: str) -> object:
            self.last_prompt = prompt
            return response

    fake = types.ModuleType("google.generativeai")
    fake.configure = configure  # type: ignore[attr-defined]
    fake.GenerativeModel = FakeModel  # type: ignore[attr-defined]
    if is_imagen:

        def generate_image(model: str, prompt: str, aspect_ratio: str) -> object:
            return response

        fake.generate_image = generate_image  # type: ignore[attr-defined]
    parent = types.ModuleType("google")
    parent.generativeai = fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", parent)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    return captured_keys


class _Inline:
    def __init__(self, data: bytes) -> None:
        self.data = data


class _Part:
    def __init__(self, data: bytes) -> None:
        self.inline_data = _Inline(data)


class _Content:
    def __init__(self, parts: list[_Part]) -> None:
        self.parts = parts


class _Candidate:
    def __init__(self, parts: list[_Part]) -> None:
        self.content = _Content(parts)


class _GeminiResponse:
    def __init__(self, data: bytes) -> None:
        self.candidates = [_Candidate([_Part(data)])]


class _GeminiEmptyResponse:
    candidates: list[object] = []


class _ImagenImage:
    def __init__(self, data: bytes) -> None:
        self.image_bytes = data


class _ImagenResponse:
    def __init__(self, data: bytes) -> None:
        self.images = [_ImagenImage(data)]


# -------- Helpers ---------


def test_aspect_instruction_includes_value() -> None:
    sentence = aspect_instruction("16:9")
    assert "16:9" in sentence


def test_imagen_aspect_map_snaps_4x5_to_3x4() -> None:
    assert IMAGEN_ASPECT_MAP["4:5"] == "3:4"
    assert IMAGEN_ASPECT_MAP["16:9"] == "16:9"


# -------- GeminiFlash ---------


@pytest.mark.asyncio
async def test_gemini_flash_render_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = _install_fake_genai(monkeypatch, response=_GeminiResponse(b"\x89PNG-flash"))
    provider = GeminiFlashProvider(api_key="key-flash")
    result = await provider.render(prompt="cover", aspect_ratio="16:9")
    assert result.image_bytes == b"\x89PNG-flash"
    assert result.provider == "gemini_flash"
    assert "16:9" in result.prompt_used  # injected aspect sentence
    assert keys == ["key-flash"]


@pytest.mark.asyncio
async def test_gemini_flash_empty_response_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_genai(monkeypatch, response=_GeminiEmptyResponse())
    provider = GeminiFlashProvider(api_key="key-flash")
    with pytest.raises(ImageProviderError):
        await provider.render(prompt="x", aspect_ratio="1:1")


def test_gemini_flash_constructor_rejects_empty_key() -> None:
    with pytest.raises(ImageProviderError):
        GeminiFlashProvider(api_key="")


@pytest.mark.asyncio
async def test_gemini_flash_lazy_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the SDK is missing, render() raises ImageProviderError with a clear msg."""
    monkeypatch.setitem(sys.modules, "google.generativeai", None)  # type: ignore[arg-type]
    # Also remove cached import.
    sys.modules.pop("google.generativeai", None)
    import builtins

    real = builtins.__import__

    def fake(name: str, *a: object, **kw: object) -> object:
        if name == "google.generativeai":
            raise ImportError("simulated missing")
        return real(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake)
    provider = GeminiFlashProvider(api_key="k")
    with pytest.raises(ImageProviderError) as ei:
        await provider.render(prompt="x", aspect_ratio="16:9")
    assert "google-generativeai" in str(ei.value)


# -------- Gemini3Pro ---------


@pytest.mark.asyncio
async def test_gemini_3_pro_render_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_genai(monkeypatch, response=_GeminiResponse(b"\x89PNG-pro"))
    provider = Gemini3ProProvider(api_key="key-pro")
    result = await provider.render(prompt="hero", aspect_ratio="16:9")
    assert result.image_bytes == b"\x89PNG-pro"
    assert result.provider == "gemini_3_pro"
    assert result.cost_usd == 0.01


def test_gemini_3_pro_constructor_rejects_empty_key() -> None:
    with pytest.raises(ImageProviderError):
        Gemini3ProProvider(api_key="")


# -------- Imagen 4 ---------


@pytest.mark.asyncio
async def test_imagen_4_render_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_genai(
        monkeypatch, response=_ImagenResponse(b"\x89PNG-imagen"), is_imagen=True
    )
    provider = Imagen4Provider(api_key="key-imagen")
    result = await provider.render(prompt="hero", aspect_ratio="4:5")
    assert result.image_bytes == b"\x89PNG-imagen"
    assert result.provider == "imagen_4"
    assert result.cost_usd == 0.04
    # 4:5 should snap to 3:4 dims (896x1280).
    assert (result.width, result.height) == (896, 1280)


@pytest.mark.asyncio
async def test_imagen_4_missing_generate_image_attr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the SDK lacks generate_image, raise a clear error."""
    fake = types.ModuleType("google.generativeai")
    fake.configure = lambda api_key="": None  # type: ignore[attr-defined]
    parent = types.ModuleType("google")
    parent.generativeai = fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", parent)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    provider = Imagen4Provider(api_key="key")
    with pytest.raises(ImageProviderError) as ei:
        await provider.render(prompt="x", aspect_ratio="16:9")
    assert "generate_image" in str(ei.value)


def test_imagen_4_constructor_rejects_empty_key() -> None:
    with pytest.raises(ImageProviderError):
        Imagen4Provider(api_key="")


def test_module_capture_for_lint() -> None:
    """Suppresses the unused-import warning for `cast`."""
    _ = cast(object, None)
