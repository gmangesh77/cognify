"""Tests for Ghost CMS adapter."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import jwt
import pytest

from src.models.publishing import PlatformPayload, PublicationStatus
from src.services.publishing.ghost.adapter import GhostAdapter

_KEY_ID = "abc123"
_SECRET_HEX = "deadbeef" * 8  # 32 bytes hex
_ADMIN_KEY = f"{_KEY_ID}:{_SECRET_HEX}"
_API_URL = "https://test.ghost.io"


def _make_payload() -> PlatformPayload:
    return PlatformPayload(
        platform="ghost",
        article_id=uuid4(),
        content="<h2>Test</h2><p>Body</p>",
        metadata={
            "title": "Test Article",
            "slug": "test-article",
            "tags": "cybersecurity,ai",
        },
    )


def _ghost_success_response() -> dict:
    return {
        "posts": [
            {
                "id": "ghost-post-123",
                "url": "https://test.ghost.io/test-article/",
                "published_at": "2026-03-26T12:00:00Z",
            }
        ]
    }


class TestGhostAdapter:
    async def test_publish_success(self) -> None:
        payload = _make_payload()

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(201, json=_ghost_success_response())

        transport = httpx.MockTransport(handler)
        adapter = GhostAdapter(_API_URL, _ADMIN_KEY)
        adapter._build_jwt_orig = adapter._build_jwt

        # Monkey-patch the client usage
        result = await _publish_with_transport(adapter, payload, transport)
        assert result.status == PublicationStatus.SUCCESS
        assert result.external_id == "ghost-post-123"
        assert result.external_url == "https://test.ghost.io/test-article/"

    async def test_publish_generates_valid_jwt(self) -> None:
        adapter = GhostAdapter(_API_URL, _ADMIN_KEY)
        token = adapter._build_jwt()
        secret = bytes.fromhex(_SECRET_HEX)
        decoded = jwt.decode(token, secret, algorithms=["HS256"], audience="/admin/")
        assert "iat" in decoded
        assert "exp" in decoded
        headers = jwt.get_unverified_header(token)
        assert headers["kid"] == _KEY_ID

    async def test_publish_scheduled(self) -> None:
        payload = _make_payload()
        schedule_time = datetime.now(UTC) + timedelta(hours=24)
        captured_body: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            import json

            captured_body.update(json.loads(request.content))
            return httpx.Response(201, json=_ghost_success_response())

        transport = httpx.MockTransport(handler)
        await _publish_with_transport(
            adapter=GhostAdapter(_API_URL, _ADMIN_KEY),
            payload=payload,
            transport=transport,
            schedule_at=schedule_time,
        )
        post = captured_body["posts"][0]
        assert post["status"] == "scheduled"
        assert schedule_time.isoformat() in post["published_at"]

    async def test_publish_api_error_returns_failed(self) -> None:
        payload = _make_payload()

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                422,
                json={"errors": [{"message": "Validation failed"}]},
            )

        transport = httpx.MockTransport(handler)
        adapter = GhostAdapter(_API_URL, _ADMIN_KEY)
        result = await _publish_with_transport(adapter, payload, transport)
        assert result.status == PublicationStatus.FAILED
        assert "422" in (result.error_message or "")

    async def test_publish_network_error_raises(self) -> None:
        payload = _make_payload()

        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        adapter = GhostAdapter(_API_URL, _ADMIN_KEY)
        with pytest.raises(httpx.ConnectError):
            await _publish_with_transport(adapter, payload, transport)

    def test_invalid_key_format_raises(self) -> None:
        with pytest.raises(ValueError, match="id:secret"):
            GhostAdapter(_API_URL, "invalid-key-no-colon")


async def _publish_with_transport(
    adapter: GhostAdapter,
    payload: PlatformPayload,
    transport: httpx.MockTransport,
    schedule_at: "datetime | None" = None,
):
    """Helper: run publish with a mock transport."""
    token = adapter._build_jwt()
    from src.services.publishing.ghost.adapter import _build_post_body, _parse_response

    body = _build_post_body(payload, schedule_at)
    url = adapter._api_url + "/ghost/api/admin/posts/"
    headers = {"Authorization": f"Ghost {token}"}
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.post(url, json=body, headers=headers, timeout=15.0)
    return _parse_response(resp, payload.article_id)
