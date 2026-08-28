"""Settings router — LLM config, SEO defaults, and general config endpoints."""

import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_admin
from src.api.rate_limiter import limiter
from src.api.schemas.settings import (
    GeneralConfigResponse,
    LlmConfigResponse,
    SeoDefaultsResponse,
    UpdateGeneralConfigRequest,
    UpdateLlmConfigRequest,
    UpdateSeoDefaultsRequest,
)

logger = structlog.get_logger()

settings_config_router = APIRouter()


def _get_repos(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.settings_repos


def _llm_response(request: Request, config: object) -> LlmConfigResponse:
    """AUTHOR-010: DB-stored config + read-only env-driven tiering fields."""
    settings = request.app.state.settings
    return LlmConfigResponse(
        **config.model_dump(),  # type: ignore[attr-defined]
        default_model=settings.anthropic_model,
        model_by_step=dict(settings.llm_model_by_step),
    )


# Route decorator OUTERMOST or slowapi never evaluates the limit (AUTHOR-006).
@settings_config_router.get("/settings/llm", response_model=LlmConfigResponse)
@limiter.limit("30/minute")
async def get_llm_config(
    request: Request,
    user: TokenPayload = Depends(require_admin),
) -> LlmConfigResponse:
    config = await _get_repos(request).llm.get_or_create()
    return _llm_response(request, config)


@settings_config_router.put("/settings/llm", response_model=LlmConfigResponse)
@limiter.limit("30/minute")
async def update_llm_config(
    request: Request,
    body: UpdateLlmConfigRequest,
    user: TokenPayload = Depends(require_admin),
) -> LlmConfigResponse:
    repos = _get_repos(request)
    existing = await repos.llm.get_or_create()
    updated = existing.model_copy(
        update={k: v for k, v in body.model_dump().items() if v is not None}
    )
    saved = await repos.llm.update(updated)
    # Reflect provider/model changes in the live Settings + provider
    # registry so the next render call honors them without a restart.
    _refresh_visual_settings_overlay(request, saved)
    logger.info(
        "llm_config_updated",
        image_provider=saved.image_provider,
        image_model=saved.image_model,
    )
    return _llm_response(request, saved)


def _refresh_visual_settings_overlay(request: Request, llm_cfg) -> None:  # type: ignore[no-untyped-def]
    """Apply persisted LlmConfig values to live Settings + rebuild registry.

    Mirrors the boot-time overlay in `src/api/main.py` so changes made via
    the Settings UI take effect immediately for subsequent /visuals/render
    calls. Falls back silently if state is missing (e.g., in tests that
    spin up a minimal app).
    """
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        return
    updates: dict[str, str | None] = {}
    if llm_cfg.image_provider:
        updates["default_image_provider"] = llm_cfg.image_provider
    if llm_cfg.image_model:
        provider_model_field = {
            "dalle_3": "dalle_model",
            "gemini_flash": "image_model_gemini_flash",
            "gemini_3_pro": "image_model_gemini_3_pro",
            "imagen_4": "image_model_imagen_4",
        }.get(llm_cfg.image_provider)
        if provider_model_field and hasattr(settings, provider_model_field):
            updates[provider_model_field] = llm_cfg.image_model
    if not updates:
        return
    request.app.state.settings = settings.model_copy(update=updates)
    # Rebuild the visuals provider registry so the new model takes
    # effect on the very next render. Lazy import keeps test env light.
    try:
        from src.services.visuals import init_registry as _init_visual_registry

        request.app.state.visual_provider_registry = _init_visual_registry(
            request.app.state.settings
        )
    except Exception as exc:  # pragma: no cover — non-fatal
        logger.warning("visual_registry_rebuild_skipped", error=str(exc))


@limiter.limit("30/minute")
@settings_config_router.get("/settings/seo", response_model=SeoDefaultsResponse)
async def get_seo_defaults(
    request: Request,
    user: TokenPayload = Depends(require_admin),
) -> SeoDefaultsResponse:
    config = await _get_repos(request).seo.get_or_create()
    return SeoDefaultsResponse(**config.model_dump())


@limiter.limit("30/minute")
@settings_config_router.put("/settings/seo", response_model=SeoDefaultsResponse)
async def update_seo_defaults(
    request: Request,
    body: UpdateSeoDefaultsRequest,
    user: TokenPayload = Depends(require_admin),
) -> SeoDefaultsResponse:
    repos = _get_repos(request)
    existing = await repos.seo.get_or_create()
    updated = existing.model_copy(
        update={k: v for k, v in body.model_dump().items() if v is not None}
    )
    saved = await repos.seo.update(updated)
    logger.info("seo_defaults_updated")
    return SeoDefaultsResponse(**saved.model_dump())


@limiter.limit("30/minute")
@settings_config_router.get("/settings/general", response_model=GeneralConfigResponse)
async def get_general_config(
    request: Request,
    user: TokenPayload = Depends(require_admin),
) -> GeneralConfigResponse:
    config = await _get_repos(request).general.get_or_create()
    return GeneralConfigResponse(**config.model_dump())


@limiter.limit("30/minute")
@settings_config_router.put("/settings/general", response_model=GeneralConfigResponse)
async def update_general_config(
    request: Request,
    body: UpdateGeneralConfigRequest,
    user: TokenPayload = Depends(require_admin),
) -> GeneralConfigResponse:
    repos = _get_repos(request)
    existing = await repos.general.get_or_create()
    updated = existing.model_copy(
        update={k: v for k, v in body.model_dump().items() if v is not None}
    )
    saved = await repos.general.update(updated)
    logger.info("general_config_updated")
    return GeneralConfigResponse(**saved.model_dump())
