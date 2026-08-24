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


__all__ = ["InProcessDispatcher", "PipelineDeps", "PipelineDispatcher"]
