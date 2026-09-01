"""Background pipeline runners for the research → content generation flow.

Split out of `research.py` under AUTHOR-002; moved from
`src/api/routers/research_pipeline.py` to the services layer under
INFRA-007 so the Celery worker can import the runners without dragging in
FastAPI router modules. Two entry points:

- `_run_full_pipeline` — research → (outline review gate, if enabled) →
  content drafting. Dispatched by `POST /research/sessions`.
- `_run_drafting_pipeline` — resume drafting from an already-approved
  outline. Dispatched by `POST /research/sessions/{id}/outline/approve`.

The shared cancellation/completion plumbing (`PipelineCancelled`,
`_content_ready`, `_run_outline_gate`, `_drive_to_completion`) lives in
`pipeline_stages.py` (AUTHOR-012 split, to keep both files under the
200-line budget); `PipelineCancelled` is re-exported here for existing
importers.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.agents.prompts import bind_prompt_overrides
from src.services.pipeline_stages import (
    PipelineCancelled,
    _content_ready,
    _drive_to_completion,
    _run_outline_gate,
)

if TYPE_CHECKING:
    from src.models.research import TopicInput
    from src.services.content import ContentService
    from src.services.content.outline_gate import OutlineGateService
    from src.services.research import ResearchService

logger = structlog.get_logger()

PromptOverridesLoader = Callable[[], Awaitable[Mapping[str, str]]]

__all__ = [
    "PipelineCancelled",
    "PipelineDeps",
    "make_cancel_check",
]


def make_cancel_check(
    reader: object, session_id: UUID
) -> Callable[[], Awaitable[None]]:
    """Build an async check that raises PipelineCancelled on cancelled.

    `reader` is anything with `async get(session_id)` returning an object
    with a `status` attribute (ResearchSessionReader / session repo).
    """

    async def check() -> None:
        session = await reader.get(session_id)  # type: ignore[attr-defined]
        if getattr(session, "status", None) == "cancelled":
            raise PipelineCancelled()

    return check


@dataclass(frozen=True)
class PipelineDeps:
    """Bundled dependencies for the background pipeline runners."""

    research_svc: ResearchService
    content_svc: ContentService | None
    outline_gate: OutlineGateService | None
    # AUTHOR-012 — loads the global prompt overrides once per run.
    prompt_overrides: PromptOverridesLoader | None = None


async def _load_prompt_overrides(deps: PipelineDeps) -> Mapping[str, str]:
    """One snapshot per run; a store outage must never block generation."""
    if deps.prompt_overrides is None:
        return {}
    try:
        return dict(await deps.prompt_overrides())
    except Exception as exc:  # noqa: BLE001
        logger.warning("prompt_overrides_unavailable", error=str(exc))
        return {}


async def _run_full_pipeline(
    deps: PipelineDeps,
    session_id: UUID,
    topic: TopicInput,
) -> None:
    """Research → (outline gate) → content generation pipeline.

    One prompt-override snapshot is loaded and bound for the whole run
    (AUTHOR-012) — never re-read mid-run.
    """
    overrides = await _load_prompt_overrides(deps)
    with bind_prompt_overrides(overrides):
        try:
            await _full_pipeline_body(deps, session_id, topic)
        except asyncio.CancelledError:
            await deps.research_svc.update_session_status(session_id, "cancelled")
            raise


async def _full_pipeline_body(
    deps: PipelineDeps,
    session_id: UUID,
    topic: TopicInput,
) -> None:
    await deps.research_svc.run_and_finalize(session_id, topic)
    detail = await deps.research_svc.get_session(session_id)
    if not _content_ready(detail, deps):
        return
    if detail.session.require_outline_approval:
        if deps.outline_gate is not None:
            await _run_outline_gate(deps, session_id)
            return
        _warn_outline_gate_missing(session_id)
    await _drive_to_completion(
        deps.research_svc,
        session_id,
        lambda: deps.content_svc.generate_full_article(session_id),  # type: ignore[union-attr]
    )


def _warn_outline_gate_missing(session_id: UUID) -> None:
    logger.warning(
        "outline_gate_not_configured",
        session_id=str(session_id),
        reason=(
            "require_outline_approval is set but no outline_gate is "
            "configured for this deployment -- falling through to "
            "the full pipeline without an outline review stop."
        ),
    )


async def _run_drafting_pipeline(deps: PipelineDeps, session_id: UUID) -> None:
    """Resume the pipeline from an editor-approved outline.

    One prompt-override snapshot is loaded and bound for the whole run
    (AUTHOR-012).
    """
    overrides = await _load_prompt_overrides(deps)
    with bind_prompt_overrides(overrides):
        try:
            await _drive_to_completion(
                deps.research_svc,
                session_id,
                lambda: deps.outline_gate.generate_from_outline(session_id),  # type: ignore[union-attr]
            )
        except asyncio.CancelledError:
            await deps.research_svc.update_session_status(session_id, "cancelled")
            raise
