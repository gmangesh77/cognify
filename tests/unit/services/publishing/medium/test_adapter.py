"""Tests for Medium adapter (mock-only, API deprecated)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from src.models.publishing import PlatformPayload, PublicationResult, PublicationStatus
from src.services.publishing.medium.adapter import (
    MediumAdapter,
    _build_request_body,
    _parse_response,
)

_TOKEN = "test-medium-token"
_USER_ID = "user-12345"


def _make_payload() -> PlatformPayload:
    return PlatformPayload(
        platform="medium",
        article_id=uuid4(),
        content="<h2>Test</h2><p>Body</p>",
        metadata={
            "title": "Test Article",
            "contentFormat": "html",
            "tags": "cybersecurity,ai,testing",
            "canonicalUrl": "https://cognify.app/articles/test",
        },
    )


def _medium_success_response() -> dict:
    return {
        "data": {
            "id": "medium-post-abc",
            "url": "https://medium.com/@user/test-article-abc",
            "publishStatus": "public",
        }
    }


class TestMediumAdapter:
    async def test_publish_success(self) -> None:
        payload = _make_payload()
        result = await _publish_with_mock(payload, 201, _medium_success_response())
        assert result.status == PublicationStatus.SUCCESS
        assert result.external_id == "medium-post-abc"

    async def test_publish_sends_bearer_token(self) -> None:
        payload = _make_payload()
        captured_headers: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(201, json=_medium_success_response())

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            url = f"https://api.medium.com/v1/users/{_USER_ID}/posts"
            body = _build_request_body(payload)
            headers = {"Authorization": f"Bearer {_TOKEN}"}
            await client.post(url, json=body, headers=headers)
        assert captured_headers["authorization"] == f"Bearer {_TOKEN}"

    async def test_schedule_returns_failed(self) -> None:
        payload = _make_payload()
        adapter = MediumAdapter(_TOKEN, _USER_ID)
        future = datetime.now(UTC) + timedelta(hours=24)
        result = await adapter.publish(payload, schedule_at=future)
        assert result.status == PublicationStatus.FAILED
        assert "scheduled" in (result.error_message or "").lower()

    async def test_api_error_returns_failed(self) -> None:
        payload = _make_payload()
        error_body = {"errors": [{"message": "Unauthorized"}]}
        result = await _publish_with_mock(payload, 401, error_body)
        assert result.status == PublicationStatus.FAILED
        assert "401" in (result.error_message or "")

    async def test_network_error_raises(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        with pytest.raises(httpx.ConnectError):
            async with httpx.AsyncClient(transport=transport) as client:
                url = f"https://api.medium.com/v1/users/{_USER_ID}/posts"
                await client.post(url, json={}, timeout=15.0)


async def _publish_with_mock(
    payload: PlatformPayload, status_code: int, response_json: dict,
) -> PublicationResult:
    """Helper: mock HTTP response and parse."""
    resp = httpx.Response(status_code, json=response_json)
    return _parse_response(resp, payload.article_id)
