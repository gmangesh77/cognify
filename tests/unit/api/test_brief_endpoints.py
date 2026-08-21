"""/briefs CRUD endpoints (AUTHOR-003)."""

import httpx
import pytest
from fastapi import FastAPI

from src.config.settings import Settings
from tests.unit.api.conftest import make_auth_header


@pytest.fixture
async def client(auth_app: FastAPI):  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create(
    client: httpx.AsyncClient, headers: dict[str, str], name: str = "A"
) -> dict:
    resp = await client.post(
        "/api/v1/briefs", json={"name": name, "keywords": ["k"]}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()  # type: ignore[no-any-return]


async def test_create_and_list(
    client: httpx.AsyncClient, auth_settings: Settings
) -> None:
    headers = make_auth_header("editor", auth_settings)
    created = await _create(client, headers)
    assert created["content_type"] == "article" and created["length_target"] == "medium"
    listed = await client.get("/api/v1/briefs", headers=headers)
    assert listed.status_code == 200
    assert [b["id"] for b in listed.json()] == [created["id"]]


async def test_viewer_can_read_but_not_write(
    client: httpx.AsyncClient, auth_settings: Settings
) -> None:
    viewer = make_auth_header("viewer", auth_settings)
    assert (await client.get("/api/v1/briefs", headers=viewer)).status_code == 200
    resp = await client.post("/api/v1/briefs", json={"name": "A"}, headers=viewer)
    assert resp.status_code == 403


async def test_unauthenticated_is_401(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/briefs")).status_code == 401


async def test_patch_delete_and_404(
    client: httpx.AsyncClient, auth_settings: Settings
) -> None:
    headers = make_auth_header("editor", auth_settings)
    created = await _create(client, headers)
    patched = await client.patch(
        f"/api/v1/briefs/{created['id']}", json={"name": "Z"}, headers=headers
    )
    assert patched.status_code == 200 and patched.json()["name"] == "Z"
    assert (
        await client.delete(f"/api/v1/briefs/{created['id']}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"/api/v1/briefs/{created['id']}", headers=headers)
    ).status_code == 404


async def test_patch_empty_body_is_422(
    client: httpx.AsyncClient, auth_settings: Settings
) -> None:
    headers = make_auth_header("editor", auth_settings)
    created = await _create(client, headers)
    resp = await client.patch(
        f"/api/v1/briefs/{created['id']}", json={}, headers=headers
    )
    assert resp.status_code == 422


async def test_duplicate(client: httpx.AsyncClient, auth_settings: Settings) -> None:
    headers = make_auth_header("editor", auth_settings)
    created = await _create(client, headers, name="Base")
    resp = await client.post(
        f"/api/v1/briefs/{created['id']}/duplicate", headers=headers
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Base (copy)" and resp.json()["keywords"] == ["k"]


async def test_invalid_tone_is_422(
    client: httpx.AsyncClient, auth_settings: Settings
) -> None:
    headers = make_auth_header("editor", auth_settings)
    resp = await client.post(
        "/api/v1/briefs", json={"name": "A", "content_tone": "nope"}, headers=headers
    )
    assert resp.status_code == 422
