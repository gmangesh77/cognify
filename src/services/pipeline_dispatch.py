"""Pipeline dispatch seam (INFRA-007).

The routers schedule background pipeline runs through a `PipelineDispatcher`
instead of touching `SessionTaskRegistry` directly. `InProcessDispatcher`
preserves today's behaviour exactly (asyncio task per session on the API
event loop). `CeleryDispatcher` (Task 5) enqueues to the worker.

Not to be confused with `src/services/task_dispatch.py`, which fans out
research *facets* to agent callables inside one process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from src.services.pipeline_runner import (
    PipelineDeps,
    _run_drafting_pipeline,
    _run_full_pipeline,
)

if TYPE_CHECKING:
    from uuid import UUID

    from celery import Celery

    from src.models.research import TopicInput
    from src.services.session_tasks import SessionTaskRegistry


class PipelineDispatcher(Protocol):
    """Schedules pipeline runs and supports best-effort cancellation."""

    def dispatch_full_pipeline(self, session_id: UUID, topic: TopicInput) -> None: ...
    def dispatch_drafting(self, session_id: UUID) -> None: ...
    def cancel(self, session_id: UUID) -> bool: ...


class InProcessDispatcher:
    """Today's behaviour: one asyncio task per session via the registry.

    `dispatch_*` re-raises the registry's ``RuntimeError`` on a duplicate
    spawn so the approve endpoint's 409 mapping keeps working.
    """

    def __init__(self, deps: PipelineDeps, registry: SessionTaskRegistry) -> None:
        self._deps = deps
        self._registry = registry

    def dispatch_full_pipeline(self, session_id: UUID, topic: TopicInput) -> None:
        self._registry.spawn(
            session_id, _run_full_pipeline(self._deps, session_id, topic)
        )

    def dispatch_drafting(self, session_id: UUID) -> None:
        self._registry.spawn(
            session_id, _run_drafting_pipeline(self._deps, session_id)
        )

    def cancel(self, session_id: UUID) -> bool:
        return self._registry.cancel(session_id)


class CeleryDispatcher:
    """Enqueues pipeline runs to the Celery worker (INFRA-007).

    Task ids are derived from the session id (`{sid}` for the full run,
    `draft-{sid}` for outline-approved drafting) so cancel can revoke by
    session. Revoke is best-effort — the reliable stop is the cooperative
    DB-status check inside the pipeline.
    """

    def __init__(self, celery: Celery) -> None:
        self._celery = celery

    def dispatch_full_pipeline(self, session_id: UUID, topic: TopicInput) -> None:
        self._celery.send_task(
            "cognify.run_full_pipeline",
            args=[str(session_id), topic.model_dump(mode="json")],  # L-001
            task_id=str(session_id),
        )

    def dispatch_drafting(self, session_id: UUID) -> None:
        self._celery.send_task(
            "cognify.run_drafting_pipeline",
            args=[str(session_id)],
            task_id=f"draft-{session_id}",
        )

    def cancel(self, session_id: UUID) -> bool:
        self._celery.control.revoke(str(session_id))
        self._celery.control.revoke(f"draft-{session_id}")
        return True


__all__ = [
    "CeleryDispatcher",
    "InProcessDispatcher",
    "PipelineDeps",
    "PipelineDispatcher",
]
