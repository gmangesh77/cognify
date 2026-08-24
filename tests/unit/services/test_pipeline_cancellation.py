"""Cooperative cancellation (INFRA-007 Task 4).

In worker mode `asyncio.Task.cancel()` cannot reach the run, so the
pipeline re-reads the session status from the DB and stops on
"cancelled" without overwriting the status.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from src.services.pipeline_runner import (
    PipelineCancelled,
    _drive_to_completion,
    make_cancel_check,
)

SESSION_ID = uuid4()


@dataclass
class _Session:
    status: str


@dataclass
class _Detail:
    session: _Session


class _FakeResearchSvc:
    def __init__(self, status: str) -> None:
        self._status = status
        self.status_writes: list[str] = []

    async def get_session(self, session_id: UUID) -> _Detail:
        return _Detail(_Session(self._status))

    async def update_session_status(self, session_id: UUID, status: str) -> None:
        self.status_writes.append(status)


class _FakeReader:
    def __init__(self, status: str) -> None:
        self._status = status

    async def get(self, session_id: UUID) -> _Session:
        return _Session(self._status)


class TestMakeCancelCheck:
    async def test_raises_on_cancelled_status(self) -> None:
        check = make_cancel_check(_FakeReader("cancelled"), SESSION_ID)
        with pytest.raises(PipelineCancelled):
            await check()

    async def test_passes_on_active_status(self) -> None:
        check = make_cancel_check(_FakeReader("generating_article"), SESSION_ID)
        await check()  # no raise


class TestWrapNodeCancelCheck:
    async def test_cancelled_session_stops_before_node_runs(self) -> None:
        from src.agents.content.pipeline import ContentGraphDeps, _wrap_node

        recorded: list[str] = []

        class _StepRepo:
            async def create(self, step: object) -> object:
                recorded.append("step")
                return None

        node_ran = False

        async def node_fn(state: dict) -> dict:  # type: ignore[type-arg]
            nonlocal node_ran
            node_ran = True
            return {}

        deps = ContentGraphDeps(
            step_repo=_StepRepo(),  # type: ignore[arg-type]
            session_id=SESSION_ID,
            cancel_check=make_cancel_check(_FakeReader("cancelled"), SESSION_ID),
        )
        wrapped = _wrap_node("outline", node_fn, deps)
        with pytest.raises(PipelineCancelled):
            await wrapped({"session_id": SESSION_ID})  # type: ignore[operator]
        assert node_ran is False
        assert recorded == []  # no step row for the aborted node


class TestDriveToCompletion:
    async def test_stops_on_cancelled_status_without_writes(self) -> None:
        svc = _FakeResearchSvc("cancelled")
        called = False

        async def generate() -> object:
            nonlocal called
            called = True
            return object()

        await _drive_to_completion(svc, SESSION_ID, generate)  # type: ignore[arg-type]
        assert called is False
        assert svc.status_writes == []

    async def test_mid_run_cancel_does_not_write_article_failed(self) -> None:
        svc = _FakeResearchSvc("generating_article")

        async def generate() -> object:
            raise PipelineCancelled()

        await _drive_to_completion(svc, SESSION_ID, generate)  # type: ignore[arg-type]
        assert "article_failed" not in svc.status_writes
        assert "article_complete" not in svc.status_writes

    async def test_happy_path_still_completes(self) -> None:
        svc = _FakeResearchSvc("complete")

        async def generate() -> object:
            return object()

        await _drive_to_completion(svc, SESSION_ID, generate)  # type: ignore[arg-type]
        assert svc.status_writes == ["generating_article", "article_complete"]
