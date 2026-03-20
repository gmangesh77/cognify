"""Shared test fixtures for API unit tests.

Provides RSA key pair, auth-configured Settings, FastAPI app, and httpx client
fixtures used by auth, RBAC, and admin endpoint tests.
"""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from src.api.auth.password import hash_password
from src.api.auth.repository import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
from src.api.auth.schemas import Role, UserData
from src.api.auth.tokens import create_access_token
from src.api.main import create_app
from src.config.settings import Settings


@pytest.fixture(autouse=True)
def patch_google_trends_client() -> Generator[None, None, None]:
    """Patch TrendReq so GoogleTrendsClient.__init__ never makes HTTP calls."""
    with patch(
        "src.services.trends.google_trends_client.TrendReq",
        return_value=MagicMock(),
    ):
        yield


def _generate_rsa_keys() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


_PRIVATE_KEY, _PUBLIC_KEY = _generate_rsa_keys()
TEST_PASSWORD = "test-password-123"
TEST_USER = UserData(
    id="user-1",
    email="test@example.com",
    password_hash=hash_password(TEST_PASSWORD),
    role="editor",
)


def make_token(role: Role, settings: Settings) -> str:
    """Create a valid access token for the given role."""
    return create_access_token("user-1", role, settings)


def make_auth_header(role: Role, settings: Settings) -> dict[str, str]:
    """Create an Authorization header dict for the given role."""
    return {"Authorization": f"Bearer {make_token(role, settings)}"}


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Reset the in-memory rate limiter storage before each test."""
    from src.api.rate_limiter import limiter

    limiter.reset()


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
    )


@pytest.fixture
def auth_app(auth_settings: Settings) -> FastAPI:
    app = create_app(auth_settings)
    app.state.user_repo = InMemoryUserRepository([TEST_USER])
    app.state.refresh_repo = InMemoryRefreshTokenRepository()
    return app


@pytest.fixture
async def auth_client(
    auth_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=auth_app),
        base_url="http://test",
    ) as ac:
        yield ac
