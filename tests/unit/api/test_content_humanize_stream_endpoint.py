"""AUTHOR-009 — POST-SSE humanize stream endpoint.

Builds a bare FastAPI app (like the other content endpoint tests) — never
`create_app` with an Anthropic key, which eagerly connects to Milvus and
hangs when the Docker stack is down.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from slowapi.errors import RateLimitExceeded

from src.agents.content import slop_scorer
from src.api.errors import CognifyError, build_error_response
from src.api.rate_limiter import limiter
from src.api.routers.content_humanize_stream import content_humanize_stream_router
from src.config.settings import Settings
from src.models.content_pipeline import SlopScore
from tests.unit.api.conftest import make_auth_header

from .test_content_endpoints import _PRIV, _PUB

SECTION_ID = "11111111-1111-1111-1111-111111111111:0"
URL = "/api/v1/content/humanize-preview/stream"


@pytest.fixture
def stream_settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        jwt_private_key=_PRIV,
        jwt_public_key=_PUB,
        anthropic_api_key="test-anthropic",
        database_url="",
    )


@pytest.fixture
def stream_app(stream_settings: Settings) -> FastAPI:
    app = FastAPI()
    app.state.settings = stream_settings
    app.state.limiter = limiter

    @app.exception_handler(CognifyError)
    async def _err_handler(_: Any, exc: CognifyError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(code=exc.code, message=exc.message),
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc.detail)})

    app.include_router(
        content_humanize_stream_router, prefix=stream_settings.api_v1_prefix
    )
    return app


@pytest.fixture
async def stream_client(
    stream_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=stream_app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    limiter.reset()


def _fake_score(text: str) -> SlopScore:
    score = 85 if text.startswith("Tighter") else 30
    return SlopScore(
        score=score,
        rating="x",
        violations=[],
        phrase_deductions=0,
        pattern_deductions=0,
    )


async def _frames(resp: httpx.Response) -> list[tuple[str, dict[str, object]]]:
    out: list[tuple[str, dict[str, object]]] = []
    event = "message"
    async for line in resp.aiter_lines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            out.append((event, json.loads(line[5:].strip())))
    return out


class TestHumanizeStreamEndpoint:
    async def test_streams_pass_events_then_done(
        self, stream_client: httpx.AsyncClient, stream_settings: Settings
    ) -> None:
        llm = FakeListChatModel(responses=["Tighter rewrite."])
        with (
            patch(
                "src.api.routers.content_humanize_stream._get_content_llm",
                return_value=llm,
            ),
            patch.object(slop_scorer, "score_text", _fake_score),
        ):
            async with stream_client.stream(
                "POST",
                URL,
                json={"section_id": SECTION_ID, "current_markdown": "Delve into it."},
                headers=make_auth_header("editor", stream_settings),
            ) as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("text/event-stream")
                frames = await _frames(resp)
        assert [t for t, _ in frames] == ["pass", "pass", "done"]
        done = frames[-1][1]
        assert str(done["rewritten"]).startswith("Tighter")
        assert done["segments"] and done["diff"]
        assert done["llm_called"] is True

    async def test_requires_editor(
        self, stream_client: httpx.AsyncClient, stream_settings: Settings
    ) -> None:
        resp = await stream_client.post(
            URL,
            json={"section_id": SECTION_ID, "current_markdown": "hi"},
            headers=make_auth_header("viewer", stream_settings),
        )
        assert resp.status_code == 403

    async def test_requires_auth(self, stream_client: httpx.AsyncClient) -> None:
        resp = await stream_client.post(
            URL, json={"section_id": SECTION_ID, "current_markdown": "hi"}
        )
        assert resp.status_code == 401

    async def test_bad_section_id_is_400(
        self, stream_client: httpx.AsyncClient, stream_settings: Settings
    ) -> None:
        resp = await stream_client.post(
            URL,
            json={"section_id": "not-a-section-id", "current_markdown": "hi"},
            headers=make_auth_header("editor", stream_settings),
        )
        assert resp.status_code == 400

    async def test_rate_limited_after_20(
        self, stream_client: httpx.AsyncClient, stream_settings: Settings
    ) -> None:
        headers = make_auth_header("editor", stream_settings)
        body = {"section_id": "not-a-section-id", "current_markdown": "hi"}
        for _ in range(20):
            await stream_client.post(URL, json=body, headers=headers)
        resp = await stream_client.post(URL, json=body, headers=headers)
        assert resp.status_code == 429
