"""Visual generation service module.

Owns the catalogue, persona register, banned-cliché block, prompt
provider abstractions, registry, object storage, and SSRF guard.
Importing this package gives access to the public API; the registry
is built lazily via `init_registry(settings)` to avoid eager imports
of provider SDKs that may not be installed in every environment.

Boundary invariants (see ADR-005):
- No imports from `src/services/publishing/`. The content engine
  never knows about platform-specific transformers.
- The catalogue, persona register, and banned-cliché block are the
  single source of truth — exposed via `GET /api/v1/visuals/styles`.
"""

from __future__ import annotations

import structlog

from src.config.settings import Settings
from src.services.visuals.banned_cliches import (
    BANNED_CLICHES_BLOCK,
    cliche_block_for_style,
)
from src.services.visuals.object_storage import (
    LocalDiskObjectStorage,
    MinioObjectStorage,
    ObjectStorage,
    ObjectStorageError,
    StoredObject,
    make_object_key,
    select_object_storage,
)
from src.services.visuals.persona_directions import (
    DEFAULT_PERSONA,
    PERSONA_VISUAL_DIRECTIONS,
    available_personas,
    get_persona_register,
)
from src.services.visuals.providers.base import (
    ImageProvider,
    ImageProviderError,
    ImageProviderInvalidRequestError,
    ImageProviderQuotaError,
    ImageProviderTimeoutError,
    ImageRenderResult,
)
from src.services.visuals.registry import ImageProviderRegistry
from src.services.visuals.safe_http import (
    FetchedImage,
    FetchFailed,
    HostBlocked,
    MimeRejected,
    SafeHttpError,
    SafeHttpFetcher,
    SchemeRejected,
    SizeExceeded,
)
from src.services.visuals.visual_styles import (
    ROLE_STYLE_DEFAULTS,
    VISUAL_STYLES,
    compose_style_override,
    default_visual_style_for_role,
    get_style,
    planner_catalogue_block,
    style_prompt_fragment,
)

__all__ = [
    "BANNED_CLICHES_BLOCK",
    "DEFAULT_PERSONA",
    "FetchFailed",
    "FetchedImage",
    "HostBlocked",
    "ImageProvider",
    "ImageProviderError",
    "ImageProviderInvalidRequestError",
    "ImageProviderQuotaError",
    "ImageProviderRegistry",
    "ImageProviderTimeoutError",
    "ImageRenderResult",
    "LocalDiskObjectStorage",
    "MimeRejected",
    "MinioObjectStorage",
    "ObjectStorage",
    "ObjectStorageError",
    "PERSONA_VISUAL_DIRECTIONS",
    "ROLE_STYLE_DEFAULTS",
    "SafeHttpError",
    "SafeHttpFetcher",
    "SchemeRejected",
    "SizeExceeded",
    "StoredObject",
    "VISUAL_STYLES",
    "available_personas",
    "cliche_block_for_style",
    "compose_style_override",
    "default_visual_style_for_role",
    "get_persona_register",
    "get_style",
    "init_registry",
    "make_object_key",
    "planner_catalogue_block",
    "select_object_storage",
    "style_prompt_fragment",
]

logger = structlog.get_logger()


def init_registry(settings: Settings) -> ImageProviderRegistry:
    """Build the `ImageProviderRegistry` populated from `settings`.

    Each provider is registered only when its required credentials are
    present. Providers can be force-disabled via `imagen_4_enabled` /
    `gemini_3_pro_enabled` flags. Missing credentials are logged at
    INFO so operators can spot misconfiguration without crashing boot.
    """
    registry = ImageProviderRegistry()
    _register_dalle_3(registry, settings)
    _register_gemini_flash(registry, settings)
    _register_gemini_3_pro(registry, settings)
    _register_imagen_4(registry, settings)
    return registry


def _register_dalle_3(registry: ImageProviderRegistry, settings: Settings) -> None:
    if not settings.openai_api_key:
        logger.info("visual_provider_skipped", provider="dalle_3", reason="no_api_key")
        return
    from src.services.visuals.providers.dalle_3 import DalleThreeProvider

    registry.register(
        DalleThreeProvider(
            api_key=settings.openai_api_key,
            model=settings.dalle_model,
            timeout=settings.illustration_timeout,
        )
    )


def _register_gemini_flash(registry: ImageProviderRegistry, settings: Settings) -> None:
    if not settings.google_ai_api_key:
        logger.info(
            "visual_provider_skipped", provider="gemini_flash", reason="no_api_key"
        )
        return
    from src.services.visuals.providers.gemini_flash import GeminiFlashProvider

    registry.register(
        GeminiFlashProvider(
            api_key=settings.google_ai_api_key,
            model=settings.image_model_gemini_flash,
            timeout=settings.image_provider_timeout,
        )
    )


def _register_gemini_3_pro(registry: ImageProviderRegistry, settings: Settings) -> None:
    if not settings.gemini_3_pro_enabled:
        logger.info(
            "visual_provider_skipped", provider="gemini_3_pro", reason="disabled"
        )
        return
    if not settings.google_ai_api_key:
        logger.info(
            "visual_provider_skipped", provider="gemini_3_pro", reason="no_api_key"
        )
        return
    from src.services.visuals.providers.gemini_3_pro import Gemini3ProProvider

    registry.register(
        Gemini3ProProvider(
            api_key=settings.google_ai_api_key,
            model=settings.image_model_gemini_3_pro,
            timeout=settings.image_provider_timeout,
        )
    )


def _register_imagen_4(registry: ImageProviderRegistry, settings: Settings) -> None:
    if not settings.imagen_4_enabled:
        logger.info("visual_provider_skipped", provider="imagen_4", reason="disabled")
        return
    if not settings.google_ai_api_key:
        logger.info("visual_provider_skipped", provider="imagen_4", reason="no_api_key")
        return
    from src.services.visuals.providers.imagen_4 import Imagen4Provider

    registry.register(
        Imagen4Provider(
            api_key=settings.google_ai_api_key,
            model=settings.image_model_imagen_4,
            timeout=settings.image_provider_timeout,
        )
    )
