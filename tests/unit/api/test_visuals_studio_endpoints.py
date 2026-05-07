"""Contract tests for the Studio API endpoints (Phase 4 / VISUAL-007).

Covers:
- POST /api/v1/visuals/plan
- POST /api/v1/visuals/render
- POST /api/v1/visuals/upload
- POST /api/v1/visuals/fetch-from-url
- POST /api/v1/visuals/section-html-refine

Each endpoint asserts: auth required, RBAC enforced (editor or admin),
input validation works, success path returns the expected schema.
LLM and provider calls are mocked via the existing FakeListChatModel
and StubImageProvider patterns from Phase 2.
"""

from __future__ import annotations

import io
import tempfile
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.routers.visuals import visuals_router
from src.config.settings import Settings
from src.services.visuals.object_storage import LocalDiskObjectStorage
from src.services.visuals.registry import ImageProviderRegistry
from src.services.visuals.section_html_refiner import SectionHtmlRefineResult
from tests.fixtures.visual_planner.planner_responses import (
    COVER_HERO_GENERAL_JSON,
    GENERAL_BUSINESS_INTRO_JSON,
)
from tests.stubs.stub_image_provider import StubImageProvider
from tests.unit.api.conftest import make_auth_header

# ---------------------------------------------------------------------------
# App fixtures: build a minimal FastAPI app that mounts visuals_router with
# auth turned ON. We bypass `create_app()` to avoid pulling in Milvus, etc.,
# and instead patch in the auth-dependent middleware via a smaller surface.
# ---------------------------------------------------------------------------


def _generate_rsa_keys() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    pk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = pk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub = (
        pk.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return priv, pub


_PRIV, _PUB = _generate_rsa_keys()


@pytest.fixture
def studio_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIV,
        jwt_public_key=_PUB,
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
        anthropic_api_key="test-anthropic",
        fetch_image_max_size_mb=2,
        fetch_image_allowed_mime=["image/png", "image/jpeg", "image/webp"],
        fetch_image_timeout_s=2.0,
    )


@pytest.fixture
def studio_app(studio_settings: Settings) -> FastAPI:
    from fastapi.responses import JSONResponse

    from src.api.errors import CognifyError, build_error_response
    from src.api.rate_limiter import limiter

    app = FastAPI()
    app.state.settings = studio_settings
    app.state.limiter = limiter

    @app.exception_handler(CognifyError)
    async def _err_handler(_: Any, exc: CognifyError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(code=exc.code, message=exc.message),
        )

    app.include_router(visuals_router, prefix=studio_settings.api_v1_prefix)

    # Pre-populate the studio registry with a stub provider + temp storage so
    # /render and /upload don't hit external APIs.
    registry = ImageProviderRegistry()
    registry.register(StubImageProvider(name="gemini_flash", model="stub"))
    app.state.visual_provider_registry = registry

    tmp = tempfile.mkdtemp()
    app.state.visual_object_storage = LocalDiskObjectStorage(tmp)
    return app


@pytest.fixture
async def studio_client(
    studio_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=studio_app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_studio_rate_limit() -> None:
    from src.api.rate_limiter import limiter

    limiter.reset()


def _editor_headers(settings: Settings) -> dict[str, str]:
    return make_auth_header("editor", settings)


# ---------------------------------------------------------------------------
# /visuals/plan
# ---------------------------------------------------------------------------


class TestPlanEndpoint:
    @pytest.fixture
    def fake_llm(self) -> FakeListChatModel:
        return FakeListChatModel(
            responses=[COVER_HERO_GENERAL_JSON, GENERAL_BUSINESS_INTRO_JSON]
        )

    async def test_requires_auth(self, studio_client: httpx.AsyncClient) -> None:
        body = {
            "topic": {
                "title": "T",
                "description": "D",
                "domain": "engineering",
            },
            "article_summary": "Summary text.",
        }
        resp = await studio_client.post("/api/v1/visuals/plan", json=body)
        assert resp.status_code in {401, 403}

    async def test_viewer_role_rejected(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        body = {
            "topic": {
                "title": "T",
                "description": "D",
                "domain": "engineering",
            },
            "article_summary": "Summary text.",
        }
        resp = await studio_client.post(
            "/api/v1/visuals/plan",
            json=body,
            headers=make_auth_header("viewer", studio_settings),
        )
        assert resp.status_code == 403

    async def test_validates_request_body(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        # Empty body fails validation.
        resp = await studio_client.post(
            "/api/v1/visuals/plan",
            json={},
            headers=_editor_headers(studio_settings),
        )
        assert resp.status_code == 422

    async def test_plans_cover_only(
        self,
        studio_client: httpx.AsyncClient,
        studio_settings: Settings,
        fake_llm: FakeListChatModel,
    ) -> None:
        with patch("src.api.routers.visuals._get_studio_llm", return_value=fake_llm):
            body = {
                "topic": {
                    "title": "Quiet refactor",
                    "description": "Steady cleanups beat rewrites.",
                    "domain": "engineering",
                },
                "article_summary": "Small steps compound.",
                "plan_cover": True,
                "max_images_per_section": 0,
            }
            resp = await studio_client.post(
                "/api/v1/visuals/plan",
                json=body,
                headers=_editor_headers(studio_settings),
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["cover"] is not None
        assert data["cover"]["role_style"] == "hero"
        assert data["section_specs"] == []

    async def test_plans_cover_and_section(
        self,
        studio_client: httpx.AsyncClient,
        studio_settings: Settings,
        fake_llm: FakeListChatModel,
    ) -> None:
        with patch("src.api.routers.visuals._get_studio_llm", return_value=fake_llm):
            body = {
                "topic": {
                    "title": "Quiet refactor",
                    "description": "Steady cleanups.",
                    "domain": "engineering",
                },
                "article_summary": "Small steps compound.",
                "section": {
                    "section_index": 0,
                    "title": "Why small steps matter",
                    "body_markdown": "First. Second.",
                },
                "max_images_per_section": 4,
            }
            resp = await studio_client.post(
                "/api/v1/visuals/plan",
                json=body,
                headers=_editor_headers(studio_settings),
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["cover"] is not None
        assert len(data["section_specs"]) == 1


# ---------------------------------------------------------------------------
# /visuals/render
# ---------------------------------------------------------------------------


class TestRenderEndpoint:
    def _spec_payload(self) -> dict[str, Any]:
        return {
            "id": "spec_1",
            "role_style": "hero",
            "visual_style": "lifestyle_photo",
            "prompt": "A founder reviewing dashboards.",
            "alt_text": "Founder",
            "aspect_ratio": "16:9",
            "placement": {"anchor": "cover", "section_index": -1},
        }

    async def test_requires_auth(self, studio_client: httpx.AsyncClient) -> None:
        resp = await studio_client.post(
            "/api/v1/visuals/render", json={"spec": self._spec_payload()}
        )
        assert resp.status_code in {401, 403}

    async def test_renders_via_stub_provider(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        body = {"spec": self._spec_payload()}
        resp = await studio_client.post(
            "/api/v1/visuals/render",
            json=body,
            headers=_editor_headers(studio_settings),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["spec_id"] == "spec_1"
        assert data["provider"] == "gemini_flash"
        # LocalDisk storage emits no URL → falls back to base64.
        assert data["image_base64"] is not None
        assert data["image_url"] is None
        assert data["mime_type"] == "image/png"

    async def test_returns_503_when_provider_missing(
        self,
        studio_app: FastAPI,
        studio_client: httpx.AsyncClient,
        studio_settings: Settings,
    ) -> None:
        # Empty registry → no providers available.
        studio_app.state.visual_provider_registry = ImageProviderRegistry()
        body = {"spec": self._spec_payload()}
        resp = await studio_client.post(
            "/api/v1/visuals/render",
            json=body,
            headers=_editor_headers(studio_settings),
        )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# /visuals/upload
# ---------------------------------------------------------------------------


_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xfc\xcf\xc0P\x0f\x00\x05\x00\x01\xe2&\x05[\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestUploadEndpoint:
    async def test_requires_auth(self, studio_client: httpx.AsyncClient) -> None:
        files = {"file": ("a.png", io.BytesIO(_PNG_1X1), "image/png")}
        resp = await studio_client.post("/api/v1/visuals/upload", files=files)
        assert resp.status_code in {401, 403}

    async def test_rejects_unsupported_mime(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        files = {"file": ("a.gif", io.BytesIO(b"GIF89a..."), "image/gif")}
        resp = await studio_client.post(
            "/api/v1/visuals/upload",
            files=files,
            headers=_editor_headers(studio_settings),
        )
        assert resp.status_code == 415

    async def test_rejects_oversized_upload(
        self,
        studio_client: httpx.AsyncClient,
        studio_settings: Settings,
    ) -> None:
        # 3MB body when the limit is 2MB.
        big = _PNG_1X1 + b"\x00" * (3 * 1024 * 1024)
        files = {"file": ("big.png", io.BytesIO(big), "image/png")}
        resp = await studio_client.post(
            "/api/v1/visuals/upload",
            files=files,
            headers=_editor_headers(studio_settings),
        )
        assert resp.status_code == 413

    async def test_rejects_mime_sniff_mismatch(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        # Claims PNG but body is plain text.
        files = {"file": ("fake.png", io.BytesIO(b"hello world"), "image/png")}
        resp = await studio_client.post(
            "/api/v1/visuals/upload",
            files=files,
            headers=_editor_headers(studio_settings),
        )
        assert resp.status_code == 415

    async def test_uploads_png_successfully(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        files = {"file": ("logo.png", io.BytesIO(_PNG_1X1), "image/png")}
        resp = await studio_client.post(
            "/api/v1/visuals/upload",
            files=files,
            headers=_editor_headers(studio_settings),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["mime_type"] == "image/png"
        assert data["size_bytes"] == len(_PNG_1X1)
        assert "object_key" in data


# ---------------------------------------------------------------------------
# /visuals/fetch-from-url
# ---------------------------------------------------------------------------


class TestFetchFromUrlEndpoint:
    async def test_requires_auth(self, studio_client: httpx.AsyncClient) -> None:
        resp = await studio_client.post(
            "/api/v1/visuals/fetch-from-url",
            json={"url": "https://example.com/x.png"},
        )
        assert resp.status_code in {401, 403}

    async def test_rejects_private_address(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        # The SafeHttpFetcher rejects 127.0.0.1 before any network I/O.
        resp = await studio_client.post(
            "/api/v1/visuals/fetch-from-url",
            json={"url": "http://127.0.0.1/secret"},
            headers=_editor_headers(studio_settings),
        )
        assert resp.status_code == 400

    async def test_rejects_non_http_scheme(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        resp = await studio_client.post(
            "/api/v1/visuals/fetch-from-url",
            json={"url": "file:///etc/passwd"},
            headers=_editor_headers(studio_settings),
        )
        assert resp.status_code == 400

    async def test_success_path_with_mocked_fetcher(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        from src.services.visuals.safe_http import FetchedImage

        fake_fetcher = MagicMock()
        fake_fetcher.fetch_image = AsyncMock(
            return_value=FetchedImage(
                url="https://example.com/cdn/img.png",
                bytes=_PNG_1X1,
                mime_type="image/png",
                size_bytes=len(_PNG_1X1),
            )
        )
        with patch(
            "src.api.routers.visuals.SafeHttpFetcher", return_value=fake_fetcher
        ):
            resp = await studio_client.post(
                "/api/v1/visuals/fetch-from-url",
                json={"url": "https://example.com/cdn/img.png"},
                headers=_editor_headers(studio_settings),
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["mime_type"] == "image/png"
        assert data["final_url"] == "https://example.com/cdn/img.png"


# ---------------------------------------------------------------------------
# /visuals/section-html-refine
# ---------------------------------------------------------------------------


class TestSectionHtmlRefineEndpoint:
    async def test_requires_auth(self, studio_client: httpx.AsyncClient) -> None:
        resp = await studio_client.post(
            "/api/v1/visuals/section-html-refine",
            json={
                "section_id": "s1",
                "instruction": "make it tighter",
                "current_html": "<p>x</p>",
            },
        )
        assert resp.status_code in {401, 403}

    async def test_returns_refined_html(
        self, studio_client: httpx.AsyncClient, studio_settings: Settings
    ) -> None:
        async def _fake_refine(**_: object) -> SectionHtmlRefineResult:
            return SectionHtmlRefineResult(
                html_fragment="<p>tighter copy</p>",
                model="claude-sonnet-4",
                prompt_used="system prompt",
            )

        with patch(
            "src.api.routers.visuals.refine_section_html", side_effect=_fake_refine
        ):
            resp = await studio_client.post(
                "/api/v1/visuals/section-html-refine",
                json={
                    "section_id": "s1",
                    "instruction": "tighten this paragraph",
                    "current_html": "<p>old text</p>",
                },
                headers=_editor_headers(studio_settings),
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["section_id"] == "s1"
        assert data["html_fragment"] == "<p>tighter copy</p>"
