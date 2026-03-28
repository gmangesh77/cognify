"""Endpoint tests for publishing routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from src.config.settings import Settings
from src.models.publishing import PublicationResult, PublicationStatus

from .conftest import make_auth_header


@pytest.fixture
def pub_app(auth_app):
    svc = AsyncMock()
    auth_app.state.publishing_service = svc
    return auth_app


@pytest.fixture
async def pub_client(pub_app) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=pub_app),
        base_url="http://test",
    ) as ac:
        yield ac


def _success_result(article_id=None):
    return PublicationResult(
        article_id=article_id or uuid4(),
        platform="ghost",
        status=PublicationStatus.SUCCESS,
        external_id="ext-1",
        external_url="https://blog.example.com/post",
        published_at=datetime.now(UTC),
    )


class TestPublishEndpoint:
    async def test_requires_auth(
        self,
        pub_client: httpx.AsyncClient,
    ) -> None:
        resp = await pub_client.post(
            f"/api/v1/articles/{uuid4()}/publish",
            json={"platform": "ghost"},
        )
        assert resp.status_code == 401

    async def test_viewer_denied(
        self,
        pub_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await pub_client.post(
            f"/api/v1/articles/{uuid4()}/publish",
            json={"platform": "ghost"},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_publish_success_returns_201(
        self,
        pub_client: httpx.AsyncClient,
        pub_app,
        auth_settings: Settings,
    ) -> None:
        aid = uuid4()
        pub_app.state.publishing_service.publish.return_value = _success_result(aid)
        headers = make_auth_header("editor", auth_settings)
        resp = await pub_client.post(
            f"/api/v1/articles/{aid}/publish",
            json={"platform": "ghost"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["platform"] == "ghost"
        assert data["status"] == "success"
        assert data["external_id"] == "ext-1"

    async def test_publish_with_schedule(
        self,
        pub_client: httpx.AsyncClient,
        pub_app,
        auth_settings: Settings,
    ) -> None:
        aid = uuid4()
        pub_app.state.publishing_service.publish.return_value = _success_result(aid)
        headers = make_auth_header("admin", auth_settings)
        resp = await pub_client.post(
            f"/api/v1/articles/{aid}/publish",
            json={"platform": "ghost", "schedule_at": "2026-04-01T12:00:00Z"},
            headers=headers,
        )
        assert resp.status_code == 201
        call_args = pub_app.state.publishing_service.publish.call_args
        assert call_args[0][1] == "ghost"  # platform arg

    async def test_empty_platform_returns_422(
        self,
        pub_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await pub_client.post(
            f"/api/v1/articles/{uuid4()}/publish",
            json={"platform": ""},
            headers=headers,
        )
        assert resp.status_code == 422
