"""Tests for LinkedIn adapter."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from src.models.publishing import PlatformPayload, PublicationStatus
from src.services.publishing.linkedin.adapter import (
    LinkedInAdapter,
    LinkedInCredentials,
    _build_request_body,
    _parse_response,
)

_CREDS = LinkedInCredentials(
    access_token="test-access-token",
    author_urn="urn:li:organization:12345",
)

_CREDS_WITH_REFRESH = LinkedInCredentials(
    access_token="test-access-token",
    author_urn="urn:li:organization:12345",
    refresh_token="test-refresh-token",
    client_id="test-client-id",
    client_secret="test-client-secret",
)


def _make_payload() -> PlatformPayload:
    return PlatformPayload(
        platform="linkedin",
        article_id=uuid4(),
        content="New article: Zero-Day Exploits\n\n#cybersecurity",
        metadata={
            "title": "Zero-Day Exploits in 2026",
            "description": "An analysis of zero-day exploits.",
            "source_url": "https://cognify.app/articles/zero-day",
            "visibility": "PUBLIC",
        },
    )


class TestLinkedInAdapter:
    async def test_publish_success(self) -> None:
        payload = _make_payload()
        resp = httpx.Response(
            201,
            json={},
            headers={"x-restli-id": "urn:li:share:123456"},
        )
        result = _parse_response(resp, payload.article_id)
        assert result.status == PublicationStatus.SUCCESS
        assert result.external_id == "urn:li:share:123456"

    async def test_sends_bearer_token(self) -> None:
        payload = _make_payload()
        captured: dict[str, str] = {}

        async def handler(req: httpx.Request) -> httpx.Response:
            captured.update(dict(req.headers))
            return httpx.Response(
                201, json={}, headers={"x-restli-id": "urn:li:share:1"},
            )

        adapter = LinkedInAdapter(_CREDS)
        adapter._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        )
        await adapter.publish(payload)
        assert captured["authorization"] == "Bearer test-access-token"

    async def test_sends_version_header(self) -> None:
        payload = _make_payload()
        captured: dict[str, str] = {}

        async def handler(req: httpx.Request) -> httpx.Response:
            captured.update(dict(req.headers))
            return httpx.Response(
                201, json={}, headers={"x-restli-id": "urn:li:share:1"},
            )

        adapter = LinkedInAdapter(_CREDS)
        adapter._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        )
        await adapter.publish(payload)
        assert captured["linkedin-version"] == "202501"

    async def test_schedule_returns_failed(self) -> None:
        payload = _make_payload()
        adapter = LinkedInAdapter(_CREDS)
        future = datetime.now(UTC) + timedelta(hours=24)
        result = await adapter.publish(payload, schedule_at=future)
        assert result.status == PublicationStatus.FAILED
        assert "scheduled" in (result.error_message or "").lower()

    async def test_api_error_returns_failed(self) -> None:
        payload = _make_payload()
        resp = httpx.Response(403, json={"message": "Forbidden"})
        result = _parse_response(resp, payload.article_id)
        assert result.status == PublicationStatus.FAILED
        assert "403" in (result.error_message or "")

    async def test_401_without_refresh_raises(self) -> None:
        async def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"message": "Unauthorized"})

        adapter = LinkedInAdapter(_CREDS)  # no refresh_token
        adapter._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.publish(_make_payload())

    async def test_429_raises_for_retry(self) -> None:
        async def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"message": "Rate limited"})

        adapter = LinkedInAdapter(_CREDS)
        adapter._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.publish(_make_payload())

    async def test_network_error_raises(self) -> None:
        async def handler(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        adapter = LinkedInAdapter(_CREDS)
        adapter._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(httpx.ConnectError):
            await adapter.publish(_make_payload())

    async def test_request_body_structure(self) -> None:
        payload = _make_payload()
        body = _build_request_body(payload, "urn:li:organization:12345")
        assert body["author"] == "urn:li:organization:12345"
        assert body["visibility"] == "PUBLIC"
        assert body["distribution"] == {"feedDistribution": "MAIN_FEED"}
        article = body["content"]["article"]
        assert article["source"] == "https://cognify.app/articles/zero-day"
        assert article["title"] == "Zero-Day Exploits in 2026"

    async def test_401_with_refresh_retries(self) -> None:
        call_count = 0

        async def handler(req: httpx.Request) -> httpx.Response:
            nonlocal call_count
            url = str(req.url)
            if "accessToken" in url:
                return httpx.Response(200, json={
                    "access_token": "new-token",
                    "expires_in": 5184000,
                })
            call_count += 1
            if call_count == 1:
                return httpx.Response(401, json={"message": "Expired"})
            return httpx.Response(
                201, json={}, headers={"x-restli-id": "urn:li:share:99"},
            )

        adapter = LinkedInAdapter(_CREDS_WITH_REFRESH)
        adapter._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        )
        result = await adapter.publish(_make_payload())
        assert result.status == PublicationStatus.SUCCESS
        assert call_count == 2
