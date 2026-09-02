"""OAuth 2.0 endpoints for platform authorization (LinkedIn)."""

from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse

from src.api.dependencies import require_admin
from src.utils.encryption import encrypt_value

if TYPE_CHECKING:
    from src.api.auth.schemas import TokenPayload

logger = structlog.get_logger()

oauth_router = APIRouter()

_LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
_LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_STATE_TTL = 600  # 10 minutes
_pending_states: dict[str, float] = {}


@oauth_router.get("/oauth/linkedin/authorize")
async def linkedin_authorize(
    request: Request,
    _user: TokenPayload = Depends(require_admin),
) -> dict[str, str]:
    """Generate LinkedIn OAuth authorization URL."""
    _cleanup_expired_states()
    state = secrets.token_urlsafe(32)
    _pending_states[state] = time.time() + _STATE_TTL
    settings = request.app.state.settings
    callback = _build_callback_url(request)
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": callback,
        "state": state,
        "scope": "openid profile w_member_social",
    }
    url = f"{_LINKEDIN_AUTH_URL}?{urlencode(params)}"
    return {"authorization_url": url}


@oauth_router.get("/oauth/linkedin/callback")
async def linkedin_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str = Query(...),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    """Handle LinkedIn OAuth callback — exchange code for tokens."""
    frontend_settings = "http://localhost:3000/settings"
    if error:
        logger.warning(
            "linkedin_oauth_denied",
            error=error,
            description=error_description,
        )
        redirect = f"{frontend_settings}?oauth=error&message={error}"
        return RedirectResponse(redirect)
    if not code:
        redirect = f"{frontend_settings}?oauth=error&message=no_code"
        return RedirectResponse(redirect)
    expiry = _pending_states.pop(state, None)
    if expiry is None or time.time() > expiry:
        return RedirectResponse(f"{frontend_settings}?oauth=error&message=expired")

    settings = request.app.state.settings
    callback = _build_callback_url(request)
    try:
        tokens = await _exchange_code_for_tokens(
            code,
            settings,
            callback,
        )
    except httpx.HTTPError as exc:
        logger.error("linkedin_token_exchange_failed", error=str(exc))
        redirect = f"{frontend_settings}?oauth=error&message=token_exchange_failed"
        return RedirectResponse(redirect)

    try:
        api_keys = request.app.state.settings_repos.api_keys
        await _store_token(api_keys, "linkedin_access_token", tokens["access_token"])
        if tokens.get("refresh_token"):
            await _store_token(
                api_keys,
                "linkedin_refresh_token",
                tokens["refresh_token"],
            )
    except Exception as exc:
        logger.error("linkedin_token_storage_failed", error=str(exc))
        redirect = f"{frontend_settings}?oauth=error&message=storage_failed"
        return RedirectResponse(redirect)

    # Fetch and store the author URN so publishing works without manual config
    author_urn = ""
    try:
        author_urn = await _fetch_author_urn(tokens["access_token"]) or ""
        if author_urn:
            await _store_token(api_keys, "linkedin_author_urn", author_urn)
            logger.info("linkedin_author_urn_stored", urn=author_urn)
    except Exception as exc:
        logger.warning("linkedin_author_urn_fetch_failed", error=str(exc))

    # Register LinkedIn with publishing service immediately (no restart needed)
    _register_linkedin_live(
        request.app,
        tokens["access_token"],
        author_urn,
        tokens.get("refresh_token", ""),
        settings,
    )

    logger.info("linkedin_oauth_complete")
    return RedirectResponse(f"{frontend_settings}?oauth=success&platform=linkedin")


def _build_callback_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    prefix = request.app.state.settings.api_v1_prefix
    return f"{base}{prefix}/oauth/linkedin/callback"


async def _exchange_code_for_tokens(
    code: str,
    settings: object,
    redirect_uri: str,
) -> dict[str, str]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.linkedin_client_id,  # type: ignore[attr-defined]
        "client_secret": settings.linkedin_client_secret,  # type: ignore[attr-defined]
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(_LINKEDIN_TOKEN_URL, data=data, timeout=15.0)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def _store_token(
    api_key_repo: object,
    service: str,
    token: str,
) -> None:
    from src.models.settings import ApiKeyConfig

    encrypted = encrypt_value(token)
    masked = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "****"
    # Delete existing entry for this service to avoid duplicates on re-auth
    await _delete_by_service(api_key_repo, service)
    config = ApiKeyConfig(service=service, masked_key=masked)
    await api_key_repo.create(config, encrypted_key=encrypted)  # type: ignore[attr-defined]


async def _delete_by_service(api_key_repo: object, service: str) -> None:
    """Remove existing keys for a service before storing a new one."""
    all_keys = await api_key_repo.list_all()  # type: ignore[attr-defined]
    for key in all_keys:
        if key.service == service:
            await api_key_repo.delete(key.id)  # type: ignore[attr-defined]


def _register_linkedin_live(
    app: object,
    access_token: str,
    author_urn: str,
    refresh_token: str,
    settings: object,
) -> None:
    """Register LinkedIn with the publishing service without server restart."""
    try:
        from src.services.publishing.linkedin.adapter import (
            LinkedInAdapter,
            LinkedInCredentials,
        )
        from src.services.publishing.linkedin.post_transformer import (
            LinkedInPostTransformer,
        )
        from src.services.publishing.linkedin.transformer import LinkedInTransformer
        from src.services.publishing.service import PlatformPair

        creds = LinkedInCredentials(
            access_token=access_token,
            author_urn=author_urn,
            refresh_token=refresh_token,
            client_id=settings.linkedin_client_id,  # type: ignore[attr-defined]
            client_secret=settings.linkedin_client_secret,  # type: ignore[attr-defined]
        )
        adapter = LinkedInAdapter(creds)
        svc = app.state.publishing_service  # type: ignore[attr-defined]
        svc.register("linkedin", PlatformPair(LinkedInTransformer(), adapter))
        # linkedin_post: repurposed standalone posts (AUTHOR-013), shares
        # the same adapter/credentials as the `linkedin` platform.
        svc.register("linkedin_post", PlatformPair(LinkedInPostTransformer(), adapter))
        logger.info("linkedin_registered_live")
    except Exception as exc:
        logger.warning("linkedin_live_registration_failed", error=str(exc))


async def _fetch_author_urn(access_token: str) -> str | None:
    """Fetch the authenticated user's LinkedIn URN via the /v2/userinfo endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        sub = data.get("sub")
        if sub:
            return f"urn:li:person:{sub}"
    return None


def _cleanup_expired_states() -> None:
    now = time.time()
    expired = [s for s, exp in _pending_states.items() if now > exp]
    for s in expired:
        del _pending_states[s]
