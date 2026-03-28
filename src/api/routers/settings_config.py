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


@limiter.limit("30/minute")
@settings_config_router.get("/settings/llm", response_model=LlmConfigResponse)
async def get_llm_config(
    request: Request,
    user: TokenPayload = Depends(require_admin),
) -> LlmConfigResponse:
    config = await _get_repos(request).llm.get_or_create()
    return LlmConfigResponse(**config.model_dump())


@limiter.limit("30/minute")
@settings_config_router.put("/settings/llm", response_model=LlmConfigResponse)
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
    logger.info("llm_config_updated")
    return LlmConfigResponse(**saved.model_dump())


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
