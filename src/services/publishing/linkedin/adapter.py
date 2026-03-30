"""LinkedIn adapter: PlatformPayload -> LinkedIn Posts API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
import structlog

from src.models.publishing import PublicationResult, PublicationStatus

if TYPE_CHECKING:
    from src.models.publishing import PlatformPayload

logger = structlog.get_logger()

_API_BASE = "https://api.linkedin.com/rest/posts"
_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_API_VERSION = "202603"
_TIMEOUT = 15.0


@dataclass(frozen=True)
class LinkedInCredentials:
    """Bundle of LinkedIn OAuth credentials."""

    access_token: str
    author_urn: str = ""
    refresh_token: str = ""
    client_id: str = ""
    client_secret: str = ""


class LinkedInAdapter:
    """Publish link-share posts to LinkedIn via Posts API."""

    def __init__(self, credentials: LinkedInCredentials) -> None:
        self._creds = credentials
        self._access_token = credentials.access_token
        self._client: httpx.AsyncClient | None = None

    async def publish(
        self,
        payload: PlatformPayload,
        schedule_at: datetime | None = None,
    ) -> PublicationResult:
        if schedule_at is not None:
            return _failed(
                payload.article_id,
                "LinkedIn does not support scheduled publishing",
            )
        author_urn = self._creds.author_urn
        if not author_urn:
            author_urn = await self._resolve_author_urn()
        if not author_urn:
            return _failed(
                payload.article_id,
                "LinkedIn author URN not configured. Set COGNIFY_LINKEDIN_AUTHOR_URN in .env "
                "(e.g. urn:li:person:YOUR_MEMBER_ID or urn:li:organization:YOUR_ORG_ID)",
            )
        body = _build_request_body(payload, author_urn)
        resp = await self._post(body)
        if resp.status_code == 401:
            return await self._handle_401(payload, body, resp)
        if resp.status_code == 429:
            resp.raise_for_status()
        return _parse_response(resp, payload.article_id)

    async def _post(self, body: dict[str, object]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "LinkedIn-Version": _API_VERSION,
            "Content-Type": "application/json",
        }
        client = self._client or httpx.AsyncClient()
        try:
            return await client.post(
                _API_BASE,
                json=body,
                headers=headers,
                timeout=_TIMEOUT,
            )
        finally:
            if self._client is None:
                await client.aclose()

    async def _resolve_author_urn(self) -> str | None:
        """Try to fetch author URN via /v2/me or /userinfo."""
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with httpx.AsyncClient() as client:
            for url in [
                "https://api.linkedin.com/v2/userinfo",
                "https://api.linkedin.com/v2/me",
            ]:
                try:
                    resp = await client.get(url, headers=headers, timeout=10.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        member_id = data.get("sub") or data.get("id")
                        if member_id:
                            urn = f"urn:li:person:{member_id}"
                            logger.info("linkedin_author_urn_resolved", urn=urn)
                            return urn
                except Exception:
                    continue
        logger.warning("linkedin_author_urn_not_resolved")
        return None

    async def _handle_401(
        self,
        payload: PlatformPayload,
        body: dict[str, object],
        resp: httpx.Response,
    ) -> PublicationResult:
        if not self._creds.refresh_token:
            resp.raise_for_status()
            return _failed(payload.article_id, "Unreachable")  # pragma: no cover
        new_token = await _refresh_access_token(self._creds, self._client)
        self._access_token = new_token
        retry_resp = await self._post(body)
        return _parse_response(retry_resp, payload.article_id)


def _build_request_body(payload: PlatformPayload, author_urn: str) -> dict[str, object]:
    meta = payload.metadata
    body: dict[str, object] = {
        "author": author_urn,
        "commentary": payload.content,
        "visibility": str(meta.get("visibility", "PUBLIC")),
        "distribution": {"feedDistribution": "MAIN_FEED"},
        "lifecycleState": "PUBLISHED",
    }
    source_url = str(meta.get("source_url", ""))
    if source_url:
        body["content"] = {
            "article": {
                "source": source_url,
                "title": str(meta.get("title", "")),
                "description": str(meta.get("description", "")),
            }
        }
    return body


def _parse_response(resp: httpx.Response, article_id: UUID) -> PublicationResult:
    if resp.status_code >= 400:
        error = resp.text[:200]
        logger.warning("linkedin_publish_failed", status=resp.status_code)
        return PublicationResult(
            article_id=article_id,
            platform="linkedin",
            status=PublicationStatus.FAILED,
            error_message=f"LinkedIn API error {resp.status_code}: {error}",
        )
    ext_id = resp.headers.get("x-restli-id", "")
    url = f"https://www.linkedin.com/feed/update/{ext_id}" if ext_id else None
    return PublicationResult(
        article_id=article_id,
        platform="linkedin",
        status=PublicationStatus.SUCCESS,
        external_id=ext_id or None,
        external_url=url,
        published_at=datetime.now(UTC),
    )


def _failed(article_id: UUID, message: str) -> PublicationResult:
    return PublicationResult(
        article_id=article_id,
        platform="linkedin",
        status=PublicationStatus.FAILED,
        error_message=message,
    )


async def _refresh_access_token(
    creds: LinkedInCredentials,
    client: httpx.AsyncClient | None = None,
) -> str:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": creds.refresh_token,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
    }
    c = client or httpx.AsyncClient()
    try:
        resp = await c.post(_TOKEN_URL, data=data, timeout=_TIMEOUT)
        resp.raise_for_status()
        return str(resp.json()["access_token"])
    finally:
        if client is None:
            await c.aclose()
