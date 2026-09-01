"""AUTHOR-012 — one override snapshot is bound for the whole pipeline run."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.agents.prompts import current_prompt_overrides
from src.services.pipeline_runner import PipelineDeps, _run_drafting_pipeline


def _research_svc(status: str = "awaiting_outline_review") -> MagicMock:
    svc = MagicMock()
    detail = MagicMock()
    detail.session.status = status
    svc.get_session = AsyncMock(return_value=detail)
    svc.update_session_status = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_drafting_run_sees_bound_overrides() -> None:
    seen: dict[str, str] = {}

    async def generate_from_outline(session_id):  # noqa: ANN001, ANN202
        seen.update(current_prompt_overrides.get())

    gate = MagicMock()
    gate.generate_from_outline = generate_from_outline
    deps = PipelineDeps(
        research_svc=_research_svc(),
        content_svc=None,
        outline_gate=gate,
        prompt_overrides=AsyncMock(return_value={"content_draft.system": "X"}),
    )
    await _run_drafting_pipeline(deps, uuid4())
    assert seen == {"content_draft.system": "X"}
    assert current_prompt_overrides.get() == {}  # unbound after the run


@pytest.mark.asyncio
async def test_loader_failure_falls_back_to_defaults() -> None:
    seen: dict[str, str] = {"sentinel": "unset"}

    async def generate_from_outline(session_id):  # noqa: ANN001, ANN202
        seen.clear()
        seen.update(current_prompt_overrides.get())

    gate = MagicMock()
    gate.generate_from_outline = generate_from_outline
    deps = PipelineDeps(
        research_svc=_research_svc(),
        content_svc=None,
        outline_gate=gate,
        prompt_overrides=AsyncMock(side_effect=RuntimeError("db down")),
    )
    await _run_drafting_pipeline(deps, uuid4())
    assert seen == {}
