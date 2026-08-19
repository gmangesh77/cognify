"""Tests for SessionTaskRegistry (AUTHOR-002, Task 4)."""

import asyncio
from uuid import uuid4

import pytest

from src.services.session_tasks import SessionTaskRegistry


async def _noop() -> None:
    return None


async def _wait_forever(event: asyncio.Event) -> None:
    await event.wait()


class TestSpawnAndIsRunning:
    async def test_spawn_marks_session_as_running(self) -> None:
        registry = SessionTaskRegistry()
        session_id = uuid4()
        event = asyncio.Event()
        task = registry.spawn(session_id, _wait_forever(event))
        assert registry.is_running(session_id) is True
        event.set()
        await task

    async def test_is_running_false_for_unknown_session(self) -> None:
        registry = SessionTaskRegistry()
        assert registry.is_running(uuid4()) is False

    async def test_auto_removes_from_registry_on_completion(self) -> None:
        registry = SessionTaskRegistry()
        session_id = uuid4()
        task = registry.spawn(session_id, _noop())
        await task
        await asyncio.sleep(0)  # let the done-callback run
        assert registry.is_running(session_id) is False


class TestCancel:
    async def test_cancel_returns_true_for_running_task(self) -> None:
        registry = SessionTaskRegistry()
        session_id = uuid4()
        event = asyncio.Event()
        task = registry.spawn(session_id, _wait_forever(event))
        cancelled = registry.cancel(session_id)
        assert cancelled is True
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_cancel_returns_false_for_unknown_session(self) -> None:
        registry = SessionTaskRegistry()
        assert registry.cancel(uuid4()) is False

    async def test_cancel_returns_false_for_already_completed_task(self) -> None:
        registry = SessionTaskRegistry()
        session_id = uuid4()
        task = registry.spawn(session_id, _noop())
        await task
        await asyncio.sleep(0)
        assert registry.cancel(session_id) is False
