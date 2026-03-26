"""Medium adapter — publishes to Medium API (deprecated)."""

from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog

from src.models.publishing import PlatformPayload, PublicationResult, PublicationStatus

logger = structlog.get_logger()

_MEDIUM_API_BASE = "https://api.medium.com/v1"


class MediumAdapter:
    """I/O adapter: PlatformPayload -> Medium API."""

    def __init__(self, api_token: str, user_id: str) -> None:
        self._api_token = api_token
        self._user_id = user_id

    async def publish(
        self,
        payload: PlatformPayload,
        schedule_at: datetime | None = None,
    ) -> PublicationResult:
        if schedule_at is not None:
            return PublicationResult(
                article_id=payload.article_id,
                platform="medium",
                status=PublicationStatus.FAILED,
                error_message="Medium does not support scheduled publishing",
            )
        url = f"{_MEDIUM_API_BASE}/users/{self._user_id}/posts"
        body = _build_request_body(payload)
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, json=body, headers=headers, timeout=15.0,
            )
        return _parse_response(resp, payload.article_id)


def _build_request_body(payload: PlatformPayload) -> dict:
    """Build the Medium API request body."""
    meta = payload.metadata
    body: dict = {
        "title": meta.get("title", ""),
        "contentFormat": "html",
        "content": payload.content,
        "publishStatus": "public",
    }
    if "tags" in meta:
        tags_str = str(meta["tags"])
        body["tags"] = [t.strip() for t in tags_str.split(",")]
    if "canonicalUrl" in meta:
        body["canonicalUrl"] = meta["canonicalUrl"]
    return body


def _parse_response(
    resp: httpx.Response, article_id: UUID,
) -> PublicationResult:
    """Map Medium API response to PublicationResult."""
    if resp.status_code >= 400:
        error = resp.text[:200]
        logger.warning(
            "medium_publish_failed", status=resp.status_code, error=error,
        )
        return PublicationResult(
            article_id=article_id,
            platform="medium",
            status=PublicationStatus.FAILED,
            error_message=f"Medium API error {resp.status_code}: {error}",
        )
    data = resp.json().get("data", {})
    return PublicationResult(
        article_id=article_id,
        platform="medium",
        status=PublicationStatus.SUCCESS,
        external_id=data.get("id"),
        external_url=data.get("url"),
        published_at=datetime.now(UTC),
    )
