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


class TestSpawnWhileRunning:
    async def test_spawn_raises_when_task_already_running(self) -> None:
        registry = SessionTaskRegistry()
        session_id = uuid4()
        event = asyncio.Event()
        first = registry.spawn(session_id, _wait_forever(event))
        assert registry.is_running(session_id) is True

        with pytest.raises(RuntimeError):
            registry.spawn(session_id, _noop())

        # The original task is unaffected -- still tracked and running.
        assert registry.is_running(session_id) is True
        event.set()
        await first

    async def test_spawn_raises_closes_the_unused_coroutine(self) -> None:
        registry = SessionTaskRegistry()
        session_id = uuid4()
        event = asyncio.Event()
        first = registry.spawn(session_id, _wait_forever(event))

        second = _noop()
        with pytest.raises(RuntimeError):
            registry.spawn(session_id, second)
        # The coroutine was closed by spawn(), not scheduled -- awaiting a
        # closed coroutine raises, proving it was never left dangling.
        with pytest.raises(RuntimeError, match="cannot reuse"):
            await second

        event.set()
        await first


class TestStaleDoneCallbackRace:
    """A finishing task's done-callback must not evict a *newer* task
    spawned for the same session before that callback gets to run.

    The race: task A finishes, its done-callback (which pops the registry
    entry) is scheduled via `call_soon` but hasn't executed yet, and a
    fresh task B is spawned for the same session in that window. Without
    the `is` identity guard in `_discard_if_current`, A's stale callback
    would blow away B's registry entry once it finally runs.
    """

    async def test_late_done_callback_does_not_evict_newer_task(self) -> None:
        registry = SessionTaskRegistry()
        session_id = uuid4()

        # An already-set Event's `.wait()` returns synchronously (no
        # suspension), so this task completes inside its very first
        # `__step` -- `task_a.done()` becomes True before our own
        # `await asyncio.sleep(0)` regains control, but the done-callback
        # that pops the registry is only *scheduled* (call_soon), not yet
        # invoked.
        already_set = asyncio.Event()
        already_set.set()
        task_a = registry.spawn(session_id, _wait_forever(already_set))
        await asyncio.sleep(0)
        assert task_a.done() is True

        # Spawn B for the same session before A's done-callback has run.
        event_b = asyncio.Event()
        task_b = registry.spawn(session_id, _wait_forever(event_b))

        # Let A's (now-stale) done-callback -- and B's first step -- run.
        await asyncio.sleep(0)

        # B must still be tracked as the running task for this session.
        assert registry.is_running(session_id) is True
        assert registry.cancel(session_id) is True
        with pytest.raises(asyncio.CancelledError):
            await task_b
