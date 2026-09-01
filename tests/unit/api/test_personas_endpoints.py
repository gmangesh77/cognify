"""AUTHOR-011 — /personas endpoints (CRUD, samples, fingerprint, score)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from src.config.settings import Settings
from src.db.persona_repository import InMemoryPersonaRepository
from src.services.persona.fingerprint import MIN_SAMPLE_WORDS
from src.services.persona.service import PersonaService

from .conftest import make_auth_header


def _long_sample(seed: int) -> str:
    """~168 words — comfortably over MIN_SAMPLE_WORDS (150)."""
    sentence = (
        f"This is sentence number {seed} that we use to build a long enough "
        "sample for the persona voice engine to accept without any trouble. "
    )
    return (sentence * 8).strip()


def _short_sample() -> str:
    """Well under MIN_SAMPLE_WORDS."""
    return "This sample is far too short for the persona voice engine to accept it."


@pytest.fixture
def personas_app(auth_app):
    repo = InMemoryPersonaRepository()
    auth_app.state.persona_repo = repo
    auth_app.state.persona_service = PersonaService(repo, embed=None)
    auth_app.state.embedding_service = MagicMock(try_embed=lambda texts: None)
    return auth_app


@pytest.fixture
async def client(personas_app) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=personas_app), base_url="http://test"
    ) as ac:
        yield ac


async def _create_persona(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post("/api/v1/personas", json={"name": "Ada"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


class TestList:
    async def test_viewer_sees_empty_list(
        self, client, auth_settings: Settings
    ) -> None:
        resp = await client.get(
            "/api/v1/personas", headers=make_auth_header("viewer", auth_settings)
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    async def test_viewer_cannot_create(self, client, auth_settings: Settings) -> None:
        resp = await client.post(
            "/api/v1/personas",
            json={"name": "Ada"},
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 403


class TestCreate:
    async def test_editor_creates_persona_not_ready(
        self, client, auth_settings: Settings
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await client.post(
            "/api/v1/personas",
            json={"name": "Ada", "description": "Technical, dry wit"},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Ada"
        assert body["ready"] is False
        assert body["sample_count"] == 0


class TestSamples:
    async def test_short_sample_rejected_with_violation_message(
        self, client, auth_settings: Settings
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        persona_id = await _create_persona(client, headers)
        text = _short_sample()
        word_count = len(text.split())
        resp = await client.post(
            f"/api/v1/personas/{persona_id}/samples",
            json={"text": text},
            headers=headers,
        )
        assert resp.status_code == 422
        violations = resp.json()["detail"]["violations"]
        assert violations == [
            f"sample needs at least {MIN_SAMPLE_WORDS} words (has {word_count})"
        ]

    async def test_five_samples_make_persona_ready(
        self, client, auth_settings: Settings
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        persona_id = await _create_persona(client, headers)
        last_resp = None
        for i in range(5):
            last_resp = await client.post(
                f"/api/v1/personas/{persona_id}/samples",
                json={"text": _long_sample(i)},
                headers=headers,
            )
            assert last_resp.status_code == 201
        assert last_resp is not None
        assert last_resp.json()["ready"] is True

        detail_resp = await client.get(
            f"/api/v1/personas/{persona_id}", headers=headers
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["ready"] is True
        assert detail["fingerprint"]["sample_count"] == 5
        assert len(detail["samples"]) == 5
        assert len(detail["samples"][0]["preview"]) <= 300

    async def test_deleting_one_of_five_drops_to_not_ready(
        self, client, auth_settings: Settings
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        persona_id = await _create_persona(client, headers)
        sample_ids = []
        for i in range(5):
            resp = await client.post(
                f"/api/v1/personas/{persona_id}/samples",
                json={"text": _long_sample(i)},
                headers=headers,
            )
            sample_ids.append(resp.json()["samples"][-1]["id"])

        del_resp = await client.delete(
            f"/api/v1/personas/{persona_id}/samples/{sample_ids[0]}",
            headers=headers,
        )
        assert del_resp.status_code == 200
        body = del_resp.json()
        assert body["ready"] is False
        assert body["fingerprint"] is None
        assert len(body["samples"]) == 4

    async def test_embedding_service_returning_vector_is_persisted(
        self, client, auth_settings: Settings, personas_app
    ) -> None:
        vector = [0.1, 0.2, 0.3]
        personas_app.state.persona_service = PersonaService(
            personas_app.state.persona_repo,
            embed=lambda texts: [vector for _ in texts],
        )
        headers = make_auth_header("editor", auth_settings)
        persona_id = await _create_persona(client, headers)
        resp = await client.post(
            f"/api/v1/personas/{persona_id}/samples",
            json={"text": _long_sample(0)},
            headers=headers,
        )
        assert resp.status_code == 201
        sample_id = resp.json()["samples"][0]["id"]
        from uuid import UUID

        stored = await personas_app.state.persona_repo.list_samples(UUID(persona_id))
        stored_sample = next(s for s in stored if str(s.id) == sample_id)
        assert stored_sample.embedding == vector


class TestScore:
    async def test_score_409_before_ready_200_after(
        self, client, auth_settings: Settings
    ) -> None:
        headers_editor = make_auth_header("editor", auth_settings)
        headers_viewer = make_auth_header("viewer", auth_settings)
        persona_id = await _create_persona(client, headers_editor)

        resp = await client.post(
            f"/api/v1/personas/{persona_id}/score",
            json={"text": "Some sample text to score."},
            headers=headers_viewer,
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "persona_not_ready"

        for i in range(5):
            await client.post(
                f"/api/v1/personas/{persona_id}/samples",
                json={"text": _long_sample(i)},
                headers=headers_editor,
            )

        resp = await client.post(
            f"/api/v1/personas/{persona_id}/score",
            json={"text": _long_sample(99)},
            headers=headers_viewer,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "score" in body and "band" in body and "deviations" in body


class TestNotFound:
    async def test_unknown_persona_404s_on_every_route(
        self, client, auth_settings: Settings
    ) -> None:
        headers_editor = make_auth_header("editor", auth_settings)
        headers_viewer = make_auth_header("viewer", auth_settings)
        unknown = "00000000-0000-0000-0000-000000000000"

        assert (
            await client.get(f"/api/v1/personas/{unknown}", headers=headers_viewer)
        ).status_code == 404
        assert (
            await client.patch(
                f"/api/v1/personas/{unknown}",
                json={"name": "X"},
                headers=headers_editor,
            )
        ).status_code == 404
        assert (
            await client.delete(f"/api/v1/personas/{unknown}", headers=headers_editor)
        ).status_code == 404
        assert (
            await client.post(
                f"/api/v1/personas/{unknown}/samples",
                json={"text": _long_sample(0)},
                headers=headers_editor,
            )
        ).status_code == 404
        assert (
            await client.delete(
                f"/api/v1/personas/{unknown}/samples/{unknown}",
                headers=headers_editor,
            )
        ).status_code == 404
        assert (
            await client.post(
                f"/api/v1/personas/{unknown}/score",
                json={"text": "hello"},
                headers=headers_viewer,
            )
        ).status_code == 404


class TestUpdateDelete:
    async def test_patch_renames(self, client, auth_settings: Settings) -> None:
        headers = make_auth_header("editor", auth_settings)
        persona_id = await _create_persona(client, headers)
        resp = await client.patch(
            f"/api/v1/personas/{persona_id}",
            json={"name": "Ada Lovelace"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Ada Lovelace"

    async def test_delete_returns_204(self, client, auth_settings: Settings) -> None:
        headers = make_auth_header("editor", auth_settings)
        persona_id = await _create_persona(client, headers)
        resp = await client.delete(f"/api/v1/personas/{persona_id}", headers=headers)
        assert resp.status_code == 204

        get_resp = await client.get(f"/api/v1/personas/{persona_id}", headers=headers)
        assert get_resp.status_code == 404


class TestRateLimit:
    async def test_31st_list_call_is_429(self, client, auth_settings: Settings) -> None:
        headers = make_auth_header("viewer", auth_settings)
        codes = [
            (await client.get("/api/v1/personas", headers=headers)).status_code
            for _ in range(31)
        ]
        assert codes[-1] == 429
