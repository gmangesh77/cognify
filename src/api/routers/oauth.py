"""OAuth 2.0 endpoints for platform authorization (LinkedIn)."""

from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request

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
        "scope": "w_member_social",
    }
    url = f"{_LINKEDIN_AUTH_URL}?{urlencode(params)}"
    return {"authorization_url": url}


@oauth_router.get("/oauth/linkedin/callback")
async def linkedin_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
) -> dict[str, str]:
    """Handle LinkedIn OAuth callback — exchange code for tokens."""
    expiry = _pending_states.pop(state, None)
    if expiry is None or time.time() > expiry:
        raise HTTPException(400, "Invalid or expired OAuth state")

    settings = request.app.state.settings
    callback = _build_callback_url(request)
    try:
        tokens = await _exchange_code_for_tokens(
            code,
            settings,
            callback,
        )
    except (httpx.HTTPStatusError, httpx.ConnectError) as exc:
        logger.error("linkedin_token_exchange_failed", error=str(exc))
        raise HTTPException(502, "Failed to exchange code with LinkedIn") from exc

    api_keys = request.app.state.settings_repos.api_keys
    await _store_token(api_keys, "linkedin_access_token", tokens["access_token"])
    if tokens.get("refresh_token"):
        await _store_token(
            api_keys,
            "linkedin_refresh_token",
            tokens["refresh_token"],
        )
    logger.info("linkedin_oauth_complete")
    return {"status": "connected", "platform": "linkedin"}


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
    config = ApiKeyConfig(service=service, masked_key=masked)
    await api_key_repo.create(config, encrypted_key=encrypted)  # type: ignore[attr-defined]


def _cleanup_expired_states() -> None:
    now = time.time()
    expired = [s for s, exp in _pending_states.items() if now > exp]
    for s in expired:
        del _pending_states[s]
