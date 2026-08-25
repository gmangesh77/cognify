"""Tests for the SSE session-events stream + session article lookup (AUTHOR-001)."""

import json
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from src.config.settings import Settings
from tests.unit.api.conftest import make_auth_header
from tests.unit.api.test_research_endpoints import (  # noqa: F401
    research_app,
    research_client,
    test_topic_id,
)


@pytest.fixture(autouse=True)
def _fast_events(research_app: FastAPI) -> None:  # noqa: F811
    """Zero out poll/grace so every SSE stream in this module terminates fast.

    httpx's ASGITransport runs the whole ASGI app to completion server-side
    before the client can iterate a streaming response, so without this the
    FakeOrchestrator's immediately-``complete`` session would make each
    streaming test pay the full ``session_events_complete_grace_seconds``
    (default 30s).
    """
    research_app.state.settings.session_events_complete_grace_seconds = 0
    research_app.state.settings.session_events_poll_seconds = 0


async def _create_session(client: httpx.AsyncClient, headers, topic_id):  # type: ignore[no-untyped-def]
    r = await client.post(
        "/api/v1/research/sessions", json={"topic_id": topic_id}, headers=headers
    )
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


@pytest.mark.asyncio
async def test_events_stream_emits_snapshot_first(
    research_client,  # noqa: F811
    auth_settings: Settings,
    test_topic_id: str,  # noqa: F811
):  # type: ignore[no-untyped-def]
    headers = make_auth_header("viewer", auth_settings)
    sid = await _create_session(
        research_client, make_auth_header("editor", auth_settings), test_topic_id
    )
    async with research_client.stream(
        "GET", f"/api/v1/research/sessions/{sid}/events", headers=headers
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        first = ""
        async for line in resp.aiter_lines():
            first += line + "\n"
            if line == "":
                break
    assert first.startswith("event: snapshot\n")
    payload = json.loads(first.split("data: ", 1)[1].strip())
    assert payload["session_id"] == sid and "steps" in payload["data"]


@pytest.mark.asyncio
async def test_events_stream_unknown_session_emits_error(
    research_client,  # noqa: F811
    auth_settings,  # noqa: F811
):  # type: ignore[no-untyped-def]
    headers = make_auth_header("viewer", auth_settings)
    async with research_client.stream(
        "GET", f"/api/v1/research/sessions/{uuid4()}/events", headers=headers
    ) as resp:
        body = ""
        async for line in resp.aiter_lines():
            body += line + "\n"
            if body.count("\n\n") >= 1:
                break
    assert body.startswith("event: error\n")


@pytest.mark.asyncio
async def test_events_requires_auth(research_client):  # noqa: F811 # type: ignore[no-untyped-def]
    r = await research_client.get(f"/api/v1/research/sessions/{uuid4()}/events")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_session_article_404_when_missing(
    research_client,  # noqa: F811
    auth_settings,  # noqa: F811
):  # type: ignore[no-untyped-def]
    r = await research_client.get(
        f"/api/v1/research/sessions/{uuid4()}/article",
        headers=make_auth_header("viewer", auth_settings),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_events_stream_ends_with_done_frame(
    research_client,  # noqa: F811
    auth_settings: Settings,
    test_topic_id: str,  # noqa: F811
):  # type: ignore[no-untyped-def]
    """The ``_fast_events`` autouse fixture zeroes poll/grace, so the
    FakeOrchestrator's immediately-``complete`` session should cause the
    stream to end quickly with a terminal ``done`` frame."""
    headers = make_auth_header("viewer", auth_settings)
    sid = await _create_session(
        research_client, make_auth_header("editor", auth_settings), test_topic_id
    )
    frames: list[str] = []
    async with research_client.stream(
        "GET", f"/api/v1/research/sessions/{sid}/events", headers=headers
    ) as resp:
        assert resp.status_code == 200
        buf = ""
        async for line in resp.aiter_lines():
            buf += line + "\n"
            if line == "":
                frames.append(buf)
                buf = ""
                if any(f.startswith("event: done\n") for f in frames):
                    break
    assert any(f.startswith("event: done\n") for f in frames)


@pytest.mark.asyncio
async def test_session_article_resolves_via_draft_not_provenance(
    research_app: FastAPI,  # noqa: F811
    research_client,  # noqa: F811
    test_topic_id,  # noqa: F811
    auth_settings: Settings,
):
    """L-013: real articles store the TOPIC id in provenance.research_session_id,
    so the lookup must go through article_drafts.session_id (the real session).
    Regression for the dead "View article" button (found live 2026-08-25)."""
    from datetime import UTC, datetime
    from uuid import UUID

    from src.models.content_pipeline import ArticleDraft
    from src.services.content_repositories import (
        ContentRepositories,
        InMemoryArticleDraftRepository,
        InMemoryArticleRepository,
    )
    from tests.unit.api.test_content_endpoints import _build_article

    headers = make_auth_header("editor", auth_settings)
    session_id = await _create_session(research_client, headers, test_topic_id)

    article_id = uuid4()
    articles = InMemoryArticleRepository()
    # Realistic article: provenance.research_session_id is the TOPIC id,
    # never the research session id (_build_article uses a random uuid).
    await articles.create(_build_article(article_id))
    drafts = InMemoryArticleDraftRepository()
    await drafts.create(
        ArticleDraft(
            session_id=UUID(session_id),
            topic_id=UUID(test_topic_id),
            article_id=article_id,
            created_at=datetime.now(UTC),
        )
    )
    research_app.state.article_repo = articles
    research_app.state.content_repos = ContentRepositories(
        drafts=drafts,
        research=None,  # type: ignore[arg-type]
        articles=articles,
    )

    r = await research_client.get(
        f"/api/v1/research/sessions/{session_id}/article", headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["article_id"] == str(article_id)
