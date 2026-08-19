"""SessionTaskRegistry — tracks the in-flight background pipeline task
per research session (AUTHOR-002, Task 4).

Lets the outline-review endpoints (`approve`, `cancel`) spawn and, on a
best-effort basis, cancel the asyncio.Task driving a session's
research/content pipeline.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any
from uuid import UUID


class SessionTaskRegistry:
    """Tracks one in-flight asyncio.Task per research session id."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def spawn(
        self, session_id: UUID, coro: Coroutine[Any, Any, None]
    ) -> asyncio.Task[None]:
        """Create and track a background task for `session_id`.

        Raises `RuntimeError` if a task for this session is already
        running — callers (e.g. the outline `approve` endpoint) should
        map that to a 409, since it means a concurrent request is
        already driving this session's pipeline forward. The given
        `coro` is closed (never scheduled) in that case, to avoid a
        "coroutine was never awaited" warning.

        The task auto-removes itself from the registry once it finishes
        (success, failure, or cancellation).
        """
        if self.is_running(session_id):
            coro.close()
            msg = f"A pipeline task is already running for session {session_id}"
            raise RuntimeError(msg)
        task = asyncio.create_task(coro)
        self._tasks[session_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(session_id, None))
        return task

    def cancel(self, session_id: UUID) -> bool:
        """Cancel the running task for `session_id`, if any.

        Returns True only if a running (not-yet-done) task was found and
        a cancellation request was issued.
        """
        task = self._tasks.get(session_id)
        if task is None or task.done():
            return False
        return task.cancel()

    def is_running(self, session_id: UUID) -> bool:
        """True if a task for `session_id` is tracked and not yet done."""
        task = self._tasks.get(session_id)
        return task is not None and not task.done()
