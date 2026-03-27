"""Tests for publication tracking API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app
from src.config.settings import Settings
from src.models.publishing import (
    PlatformSummary,
    Publication,
    PublicationEvent,
    PublicationStatus,
)

_EDITOR_TOKEN = {
    "sub": str(uuid4()),
    "role": "editor",
    "exp": 9999999999,
    "iat": 1000000000,
    "jti": str(uuid4()),
}


def _pub(*, platform: str = "ghost", status: PublicationStatus = PublicationStatus.SUCCESS) -> Publication:
    return Publication(
        id=uuid4(),
        article_id=uuid4(),
        platform=platform,
        status=status,
        external_id="ext-1",
        external_url="https://blog.example.com/post",
        published_at=datetime.now(UTC),
        view_count=42,
        seo_score=80,
        error_message=None if status == PublicationStatus.SUCCESS else "Error",
        event_history=[
            PublicationEvent(timestamp=datetime.now(UTC), status=status),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def pub_app():
    settings = Settings(
        jwt_algorithm="RS256",
    )
    app = create_app(settings)
    app.state.publishing_service = MagicMock()
    pub_repo = AsyncMock()
    app.state.pub_repo = pub_repo
    article_repo = AsyncMock()
    article_mock = MagicMock()
    article_mock.title = "Test Article"
    article_repo.get.return_value = article_mock
    app.state.article_repo = article_repo
    return app


@pytest.fixture
async def pub_client(pub_app):
    transport = ASGITransport(app=pub_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestListPublications:
    @pytest.mark.asyncio
    async def test_requires_auth(self, pub_client) -> None:
        resp = await pub_client.get("/api/v1/publications")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    @patch("src.api.dependencies.decode_access_token")
    async def test_returns_paginated_list(self, mock_decode, pub_client, pub_app) -> None:
        from src.api.auth.schemas import TokenPayload

        mock_decode.return_value = TokenPayload(**_EDITOR_TOKEN)
        pubs = [_pub(), _pub(platform="medium")]
        pub_app.state.pub_repo.list.return_value = (pubs, 2)

        resp = await pub_client.get(
            "/api/v1/publications",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2


class TestGetPublication:
    @pytest.mark.asyncio
    @patch("src.api.dependencies.decode_access_token")
    async def test_not_found(self, mock_decode, pub_client, pub_app) -> None:
        from src.api.auth.schemas import TokenPayload

        mock_decode.return_value = TokenPayload(**_EDITOR_TOKEN)
        pub_app.state.pub_repo.get.return_value = None

        resp = await pub_client.get(
            f"/api/v1/publications/{uuid4()}",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 404


class TestRetryPublication:
    @pytest.mark.asyncio
    async def test_requires_auth(self, pub_client) -> None:
        resp = await pub_client.post(f"/api/v1/publications/{uuid4()}/retry")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    @patch("src.api.dependencies.decode_access_token")
    async def test_retry_success(self, mock_decode, pub_client, pub_app) -> None:
        from src.api.auth.schemas import TokenPayload
        from src.models.publishing import PublicationResult

        mock_decode.return_value = TokenPayload(**_EDITOR_TOKEN)
        pub_id = uuid4()
        failed_pub = _pub(status=PublicationStatus.FAILED)
        pub_app.state.pub_repo.get.return_value = failed_pub

        pub_app.state.publishing_service.retry = AsyncMock(
            return_value=PublicationResult(
                article_id=failed_pub.article_id,
                platform="ghost",
                status=PublicationStatus.SUCCESS,
                external_id="g-retry",
                external_url="https://blog.example.com/retried",
                published_at=datetime.now(UTC),
            ),
        )

        resp = await pub_client.post(
            f"/api/v1/publications/{pub_id}/retry",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200


class TestPlatformSummaries:
    @pytest.mark.asyncio
    @patch("src.api.dependencies.decode_access_token")
    async def test_returns_summaries(self, mock_decode, pub_client, pub_app) -> None:
        from src.api.auth.schemas import TokenPayload

        mock_decode.return_value = TokenPayload(**_EDITOR_TOKEN)
        pub_app.state.pub_repo.get_platform_summaries.return_value = [
            PlatformSummary(platform="ghost", total=10, success=8, failed=1, scheduled=1),
        ]

        resp = await pub_client.get(
            "/api/v1/publications/summaries",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["platform"] == "ghost"
