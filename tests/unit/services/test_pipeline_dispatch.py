"""PipelineDispatcher seam (INFRA-007) — in-process implementation."""

import asyncio
from uuid import uuid4

import pytest

from src.services.pipeline_dispatch import InProcessDispatcher
from src.services.session_tasks import SessionTaskRegistry


class _RecordingDeps:
    """Stands in for PipelineDeps — the dispatcher never introspects it."""


async def test_dispatch_full_pipeline_spawns_the_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran = asyncio.Event()

    async def fake_runner(deps: object, session_id: object, topic: object) -> None:
        ran.set()

    monkeypatch.setattr(
        "src.services.pipeline_dispatch._run_full_pipeline", fake_runner
    )
    registry = SessionTaskRegistry()
    d = InProcessDispatcher(_RecordingDeps(), registry)  # type: ignore[arg-type]
    d.dispatch_full_pipeline(uuid4(), topic=None)  # type: ignore[arg-type]
    await asyncio.wait_for(ran.wait(), timeout=2)


async def test_cancel_delegates_to_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def hang(deps: object, session_id: object) -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr("src.services.pipeline_dispatch._run_drafting_pipeline", hang)
    registry = SessionTaskRegistry()
    d = InProcessDispatcher(_RecordingDeps(), registry)  # type: ignore[arg-type]
    sid = uuid4()
    d.dispatch_drafting(sid)
    await asyncio.sleep(0.05)
    assert d.cancel(sid) is True
    await asyncio.sleep(0.05)
    assert registry.is_running(sid) is False


async def test_duplicate_dispatch_raises_like_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def hang(deps: object, session_id: object) -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr("src.services.pipeline_dispatch._run_drafting_pipeline", hang)
    registry = SessionTaskRegistry()
    d = InProcessDispatcher(_RecordingDeps(), registry)  # type: ignore[arg-type]
    sid = uuid4()
    d.dispatch_drafting(sid)
    await asyncio.sleep(0.05)
    with pytest.raises(RuntimeError):
        d.dispatch_drafting(sid)
    d.cancel(sid)
