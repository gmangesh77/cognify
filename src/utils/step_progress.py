"""Per-step progress reporting for long-running pipeline nodes.

Nodes call ``report_progress({...})``; the active node wrapper binds a
reporter that merges the dict into the running AgentStep's ``output_data``
so the session-events stream (AUTHOR-001) can surface sub-step progress.
"""

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable
from typing import Protocol

import structlog

from src.models.research_db import AgentStep

logger = structlog.get_logger(__name__)

ProgressReporter = Callable[[dict[str, object]], Awaitable[None]]

current_progress_reporter: contextvars.ContextVar[ProgressReporter | None] = (
    contextvars.ContextVar("current_progress_reporter", default=None)
)


class _StepUpdater(Protocol):
    async def update(self, step: AgentStep) -> AgentStep: ...


async def report_progress(data: dict[str, object]) -> None:
    """Publish progress for the current step; silent no-op when unbound."""
    reporter = current_progress_reporter.get()
    if reporter is None:
        return
    try:
        await reporter(data)
    except Exception as exc:  # progress is telemetry — never break the node
        logger.warning("step_progress_report_failed", error=str(exc))


def make_step_reporter(step_repo: _StepUpdater, step: AgentStep) -> ProgressReporter:
    """Build a reporter that merges progress into ``step.output_data``."""
    merged: dict[str, object] = dict(step.output_data)

    async def _report(data: dict[str, object]) -> None:
        merged.update(data)
        await step_repo.update(step.model_copy(update={"output_data": dict(merged)}))

    return _report
