"""AUTHOR-012 — /prompts endpoints."""

from __future__ import annotations

import httpx
import pytest

from src.agents.prompts import DEFAULT_PROMPTS
from src.agents.prompts.validation import MAX_TEMPLATE_CHARS
from src.config.settings import Settings
from src.db.prompt_override_repository import InMemoryPromptOverrideRepository

from .conftest import make_auth_header

KEY = "content_outline.user"
GOOD = (
    "Outline for {title} / {description} / {domain}\n{findings_summary}\n"
    "{requirements}\n{schema_hint}"
)


@pytest.fixture
def prompts_app(auth_app):
    auth_app.state.prompt_override_repo = InMemoryPromptOverrideRepository()
    return auth_app


@pytest.fixture
async def client(prompts_app) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=prompts_app), base_url="http://test"
    ) as ac:
        yield ac


class TestList:
    async def test_editor_sees_every_registered_key(
        self, client, auth_settings: Settings
    ) -> None:
        resp = await client.get(
            "/api/v1/prompts", headers=make_auth_header("editor", auth_settings)
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert {i["key"] for i in items} == set(DEFAULT_PROMPTS)
        row = next(i for i in items if i["key"] == KEY)
        assert row["is_overridden"] is False
        assert (
            row["template"] == row["default_template"] == DEFAULT_PROMPTS[KEY].template
        )
        assert set(row["variables"]) == set(DEFAULT_PROMPTS[KEY].variables)
        assert row["step"] == "content_outline"

    async def test_viewer_forbidden(self, client, auth_settings: Settings) -> None:
        resp = await client.get(
            "/api/v1/prompts", headers=make_auth_header("viewer", auth_settings)
        )
        assert resp.status_code == 403


class TestPut:
    async def test_admin_override_is_returned_and_listed(
        self, client, auth_settings: Settings
    ) -> None:
        resp = await client.put(
            f"/api/v1/prompts/{KEY}",
            json={"template": GOOD},
            headers=make_auth_header("admin", auth_settings),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_overridden"] is True and body["template"] == GOOD
        assert body["updated_by"] == "user-1" and body["updated_at"]
        assert body["default_template"] == DEFAULT_PROMPTS[KEY].template
        single = await client.get(
            f"/api/v1/prompts/{KEY}", headers=make_auth_header("editor", auth_settings)
        )
        assert single.json()["template"] == GOOD

    async def test_editor_cannot_put(self, client, auth_settings: Settings) -> None:
        resp = await client.put(
            f"/api/v1/prompts/{KEY}",
            json={"template": GOOD},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 403

    async def test_invalid_template_is_422_with_violations(
        self, client, auth_settings: Settings
    ) -> None:
        resp = await client.put(
            f"/api/v1/prompts/{KEY}",
            json={"template": "only {title} and {bogus}"},
            headers=make_auth_header("admin", auth_settings),
        )
        assert resp.status_code == 422
        violations = resp.json()["detail"]["violations"]
        assert "unknown variable {bogus}" in violations
        assert "missing required variable {domain}" in violations

    async def test_oversized_template_rejected_by_schema(
        self, client, auth_settings: Settings
    ) -> None:
        resp = await client.put(
            f"/api/v1/prompts/{KEY}",
            json={"template": "x" * (MAX_TEMPLATE_CHARS + 1)},
            headers=make_auth_header("admin", auth_settings),
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    async def test_unknown_key_404(self, client, auth_settings: Settings) -> None:
        resp = await client.put(
            "/api/v1/prompts/nope.system",
            json={"template": "x"},
            headers=make_auth_header("admin", auth_settings),
        )
        assert resp.status_code == 404


class TestDelete:
    async def test_reset_restores_default(
        self, client, auth_settings: Settings
    ) -> None:
        admin = make_auth_header("admin", auth_settings)
        await client.put(
            f"/api/v1/prompts/{KEY}", json={"template": GOOD}, headers=admin
        )
        resp = await client.delete(f"/api/v1/prompts/{KEY}", headers=admin)
        assert resp.status_code == 200
        assert resp.json()["is_overridden"] is False
        assert resp.json()["template"] == DEFAULT_PROMPTS[KEY].template

    async def test_reset_without_override_404(
        self, client, auth_settings: Settings
    ) -> None:
        resp = await client.delete(
            f"/api/v1/prompts/{KEY}", headers=make_auth_header("admin", auth_settings)
        )
        assert resp.status_code == 404


class TestRateLimit:
    async def test_list_is_rate_limited(self, client, auth_settings: Settings) -> None:
        headers = make_auth_header("editor", auth_settings)
        codes = [
            (await client.get("/api/v1/prompts", headers=headers)).status_code
            for _ in range(31)
        ]
        assert codes[-1] == 429
