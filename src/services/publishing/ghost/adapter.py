"""Ghost CMS adapter — publishes to Ghost Admin API."""

import json
import time
from datetime import UTC, datetime
from uuid import UUID

import httpx
import jwt
import structlog

from src.models.publishing import PlatformPayload, PublicationResult, PublicationStatus

logger = structlog.get_logger()

_GHOST_API_PATH = "/ghost/api/admin/posts/"
_JWT_EXPIRY_SECONDS = 300


class GhostAdapter:
    """I/O adapter: PlatformPayload -> Ghost Admin API."""

    def __init__(self, api_url: str, admin_api_key: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._key_id, self._secret = _parse_admin_key(admin_api_key)

    async def publish(
        self,
        payload: PlatformPayload,
        schedule_at: datetime | None = None,
    ) -> PublicationResult:
        token = self._build_jwt()
        body = _build_post_body(payload, schedule_at)
        url = self._api_url + _GHOST_API_PATH
        headers = {"Authorization": f"Ghost {token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, json=body, headers=headers, timeout=15.0,
            )
        return _parse_response(resp, payload.article_id)

    def _build_jwt(self) -> str:
        now = int(time.time())
        return jwt.encode(
            {"iat": now, "exp": now + _JWT_EXPIRY_SECONDS, "aud": "/admin/"},
            self._secret,
            algorithm="HS256",
            headers={"kid": self._key_id},
        )


def _parse_admin_key(admin_api_key: str) -> tuple[str, bytes]:
    """Split 'id:secret' and hex-decode the secret."""
    parts = admin_api_key.split(":")
    if len(parts) != 2:
        raise ValueError("Ghost admin API key must be in 'id:secret' format")
    return parts[0], bytes.fromhex(parts[1])


def _build_post_body(
    payload: PlatformPayload, schedule_at: datetime | None,
) -> dict:
    """Build the Ghost API request body from payload metadata."""
    meta = payload.metadata
    lexical = _html_to_lexical(payload.content)
    post: dict = {
        "posts": [{
            "title": meta.get("title", ""),
            "lexical": lexical,
            "status": "published",
        }]
    }
    p = post["posts"][0]
    if schedule_at:
        p["status"] = "scheduled"
        p["published_at"] = schedule_at.isoformat()
    if "tags" in meta:
        tag_names = str(meta["tags"]).split(",")
        p["tags"] = [{"name": t.strip()} for t in tag_names]
    _COPY_FIELDS = (
        "slug", "custom_excerpt", "meta_title",
        "meta_description", "canonical_url", "feature_image",
    )
    for key in _COPY_FIELDS:
        if key in meta:
            p[key] = meta[key]
    return post


def _html_to_lexical(html: str) -> str:
    """Wrap HTML content in a Ghost Lexical HTML card."""
    doc = {
        "root": {
            "children": [
                {"type": "html", "version": 1, "html": html},
            ],
            "direction": None,
            "format": "",
            "indent": 0,
            "type": "root",
            "version": 1,
        },
    }
    return json.dumps(doc)


def _parse_response(
    resp: httpx.Response, article_id: UUID,
) -> PublicationResult:
    """Map Ghost API response to PublicationResult."""
    if resp.status_code >= 400:
        error = resp.text[:200]
        logger.warning(
            "ghost_publish_failed", status=resp.status_code, error=error,
        )
        return PublicationResult(
            article_id=article_id,
            platform="ghost",
            status=PublicationStatus.FAILED,
            error_message=f"Ghost API error {resp.status_code}: {error}",
        )
    data = resp.json()
    post = data.get("posts", [{}])[0]
    return PublicationResult(
        article_id=article_id,
        platform="ghost",
        status=PublicationStatus.SUCCESS,
        external_id=post.get("id"),
        external_url=post.get("url"),
        published_at=datetime.now(UTC),
    )
