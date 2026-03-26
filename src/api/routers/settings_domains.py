"""Settings router — domain config and API key endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from starlette.responses import Response
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_admin
from src.api.errors import NotFoundError
from src.api.rate_limiter import limiter
from src.api.schemas.settings import (
    AddApiKeyRequest,
    ApiKeyListResponse,
    ApiKeyResponse,
    CreateDomainRequest,
    DomainListResponse,
    DomainResponse,
    RotateApiKeyRequest,
    UpdateDomainRequest,
)
from src.models.settings import ApiKeyConfig, DomainConfig
from src.utils.encryption import encrypt_value

logger = structlog.get_logger()

settings_domains_router = APIRouter()

_MASK_PREFIX_LEN = 8
_MASK_SUFFIX_LEN = 4


def _mask_key(raw_key: str) -> str:
    """Return a masked API key showing first 8 and last 4 chars."""
    if len(raw_key) <= _MASK_PREFIX_LEN + _MASK_SUFFIX_LEN:
        return raw_key[:2] + "••••••••" + raw_key[-2:]
    return raw_key[:_MASK_PREFIX_LEN] + "••••••••" + raw_key[-_MASK_SUFFIX_LEN:]


def _get_repos(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.settings_repos


def _domain_to_response(d: DomainConfig) -> DomainResponse:
    return DomainResponse(
        id=d.id,
        name=d.name,
        status=d.status,
        trend_sources=d.trend_sources,
        keywords=d.keywords,
        article_count=d.article_count,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


def _key_to_response(k: ApiKeyConfig) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=k.id,
        service=k.service,
        masked_key=k.masked_key,
        status=k.status,
        created_at=k.created_at,
    )


@limiter.limit("30/minute")
@settings_domains_router.get("/settings/domains", response_model=DomainListResponse)
async def list_domains(
    request: Request,
    user: TokenPayload = Depends(require_admin),
) -> DomainListResponse:
    items = await _get_repos(request).domains.list_all()
    return DomainListResponse(items=[_domain_to_response(d) for d in items])


@limiter.limit("30/minute")
@settings_domains_router.post(
    "/settings/domains", response_model=DomainResponse, status_code=HTTP_201_CREATED,
)
async def create_domain(
    request: Request,
    body: CreateDomainRequest,
    user: TokenPayload = Depends(require_admin),
) -> DomainResponse:
    domain = DomainConfig(
        name=body.name,
        status=body.status,
        trend_sources=body.trend_sources,
        keywords=body.keywords,
    )
    created = await _get_repos(request).domains.create(domain)
    logger.info("domain_created", domain_id=str(created.id), name=created.name)
    return _domain_to_response(created)


@limiter.limit("30/minute")
@settings_domains_router.put(
    "/settings/domains/{domain_id}", response_model=DomainResponse,
)
async def update_domain(
    request: Request,
    domain_id: UUID,
    body: UpdateDomainRequest,
    user: TokenPayload = Depends(require_admin),
) -> DomainResponse:
    repos = _get_repos(request)
    existing = await repos.domains.get(domain_id)
    if existing is None:
        raise NotFoundError(message=f"Domain {domain_id} not found")
    updated = existing.model_copy(update={
        k: v for k, v in body.model_dump().items() if v is not None
    })
    saved = await repos.domains.update(updated)
    logger.info("domain_updated", domain_id=str(domain_id))
    return _domain_to_response(saved)


@limiter.limit("30/minute")
@settings_domains_router.delete(
    "/settings/domains/{domain_id}", status_code=HTTP_204_NO_CONTENT,
)
async def delete_domain(
    request: Request,
    domain_id: UUID,
    user: TokenPayload = Depends(require_admin),
) -> Response:
    await _get_repos(request).domains.delete(domain_id)
    logger.info("domain_deleted", domain_id=str(domain_id))
    return Response(status_code=HTTP_204_NO_CONTENT)


@limiter.limit("30/minute")
@settings_domains_router.get("/settings/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    request: Request,
    user: TokenPayload = Depends(require_admin),
) -> ApiKeyListResponse:
    items = await _get_repos(request).api_keys.list_all()
    return ApiKeyListResponse(items=[_key_to_response(k) for k in items])


@limiter.limit("30/minute")
@settings_domains_router.post(
    "/settings/api-keys", response_model=ApiKeyResponse, status_code=HTTP_201_CREATED,
)
async def add_api_key(
    request: Request,
    body: AddApiKeyRequest,
    user: TokenPayload = Depends(require_admin),
) -> ApiKeyResponse:
    masked = _mask_key(body.key)
    key_config = ApiKeyConfig(service=body.service, masked_key=masked)
    created = await _get_repos(request).api_keys.create(
        key_config, encrypted_key=encrypt_value(body.key),
    )
    logger.info("api_key_added", service=body.service, key_id=str(created.id))
    return _key_to_response(created)


@limiter.limit("30/minute")
@settings_domains_router.put(
    "/settings/api-keys/{key_id}/rotate", response_model=ApiKeyResponse,
)
async def rotate_api_key(
    request: Request,
    key_id: UUID,
    body: RotateApiKeyRequest,
    user: TokenPayload = Depends(require_admin),
) -> ApiKeyResponse:
    masked = _mask_key(body.key)
    updated = await _get_repos(request).api_keys.rotate(
        key_id, encrypted_key=encrypt_value(body.key), masked_key=masked,
    )
    logger.info("api_key_rotated", key_id=str(key_id))
    return _key_to_response(updated)


@limiter.limit("30/minute")
@settings_domains_router.delete(
    "/settings/api-keys/{key_id}", status_code=HTTP_204_NO_CONTENT,
)
async def delete_api_key(
    request: Request,
    key_id: UUID,
    user: TokenPayload = Depends(require_admin),
) -> Response:
    await _get_repos(request).api_keys.delete(key_id)
    logger.info("api_key_deleted", key_id=str(key_id))
    return Response(status_code=HTTP_204_NO_CONTENT)
