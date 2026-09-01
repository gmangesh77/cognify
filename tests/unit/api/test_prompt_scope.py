"""AUTHOR-012 — request-scoped override loading never blocks the request."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.prompt_scope import load_prompt_overrides


@pytest.mark.asyncio
async def test_returns_repo_snapshot() -> None:
    request = MagicMock()
    request.app.state.prompt_override_repo = MagicMock(
        load_all=AsyncMock(return_value={"k": "v"})
    )
    assert await load_prompt_overrides(request) == {"k": "v"}


@pytest.mark.asyncio
async def test_missing_repo_returns_empty() -> None:
    request = MagicMock()
    request.app.state = MagicMock(spec=[])  # no prompt_override_repo attribute
    assert await load_prompt_overrides(request) == {}


@pytest.mark.asyncio
async def test_repo_error_returns_empty() -> None:
    request = MagicMock()
    request.app.state.prompt_override_repo = MagicMock(
        load_all=AsyncMock(side_effect=RuntimeError("x"))
    )
    assert await load_prompt_overrides(request) == {}
