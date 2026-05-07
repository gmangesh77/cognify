"""Contract tests for `GET /api/v1/visuals/styles`."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from src.api.routers.visuals import visuals_router
from src.config.settings import Settings


@pytest.fixture
def visuals_app() -> FastAPI:
    settings = Settings()
    app = FastAPI()
    app.state.settings = settings
    app.include_router(visuals_router, prefix=settings.api_v1_prefix)
    return app


@pytest.fixture
async def visuals_client(
    visuals_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=visuals_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestVisualStylesEndpoint:
    async def test_returns_200(self, visuals_client: httpx.AsyncClient) -> None:
        response = await visuals_client.get("/api/v1/visuals/styles")
        assert response.status_code == 200

    async def test_returns_twelve_styles(
        self, visuals_client: httpx.AsyncClient
    ) -> None:
        response = await visuals_client.get("/api/v1/visuals/styles")
        body = response.json()
        assert len(body["styles"]) == 12

    async def test_each_style_has_required_fields(
        self, visuals_client: httpx.AsyncClient
    ) -> None:
        response = await visuals_client.get("/api/v1/visuals/styles")
        for entry in response.json()["styles"]:
            assert {
                "key",
                "label",
                "category",
                "default_aspect",
                "short_desc",
                "prompt_fragment",
            }.issubset(entry.keys())

    async def test_role_defaults_present(
        self, visuals_client: httpx.AsyncClient
    ) -> None:
        body = (await visuals_client.get("/api/v1/visuals/styles")).json()
        assert body["role_defaults"]["hero"] == "lifestyle_photo"
        assert body["role_defaults"]["screenshot_mock"] == "blueprint"

    async def test_personas_present(self, visuals_client: httpx.AsyncClient) -> None:
        body = (await visuals_client.get("/api/v1/visuals/styles")).json()
        keys = {entry["key"] for entry in body["personas"]}
        assert "general_business" in keys
        assert "cto" in keys
        assert body["default_persona"] == "general_business"
        # Each persona has a direction string.
        for entry in body["personas"]:
            assert "direction" in entry
            assert len(entry["direction"]) > 50

    async def test_banned_cliches_block_present(
        self, visuals_client: httpx.AsyncClient
    ) -> None:
        body = (await visuals_client.get("/api/v1/visuals/styles")).json()
        assert "BANNED CLICHES" in body["banned_cliches_block"]
        assert "no glowing AI brain" in body["banned_cliches_block"]

    async def test_planner_catalogue_block_lists_keys(
        self, visuals_client: httpx.AsyncClient
    ) -> None:
        body = (await visuals_client.get("/api/v1/visuals/styles")).json()
        block = body["planner_catalogue_block"]
        assert "lifestyle_photo" in block
        assert "blueprint" in block
        assert "isometric_3d" in block
