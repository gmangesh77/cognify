"""Background pipeline runners for the research → content generation flow.

Split out of `research.py` under AUTHOR-002; moved from
`src/api/routers/research_pipeline.py` to the services layer under
INFRA-007 so the Celery worker can import the runners without dragging in
FastAPI router modules. Two entry points:

- `_run_full_pipeline` — research → (outline review gate, if enabled) →
  content drafting. Dispatched by `POST /research/sessions`.
- `_run_drafting_pipeline` — resume drafting from an already-approved
  outline. Dispatched by `POST /research/sessions/{id}/outline/approve`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.agents.prompts import bind_prompt_overrides

if TYPE_CHECKING:
    from src.models.research import TopicInput
    from src.services.content import ContentService
    from src.services.content.outline_gate import OutlineGateService
    from src.services.research import ResearchService, SessionDetail

logger = structlog.get_logger()

PromptOverridesLoader = Callable[[], Awaitable[Mapping[str, str]]]


class PipelineCancelled(Exception):
    """Raised by cooperative cancel checks when the session was cancelled.

    In worker mode (INFRA-007) `asyncio.Task.cancel()` cannot reach the
    run, so the pipeline re-reads the session status and stops. The cancel
    endpoint already wrote `"cancelled"` — handlers must NOT overwrite it.
    """


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


async def _is_cancelled(research_svc: ResearchService, session_id: UUID) -> bool:
    detail = await research_svc.get_session(session_id)
    return detail.session.status == "cancelled"


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
        logger.warning(
            "outline_gate_not_configured",
            session_id=str(session_id),
            reason=(
                "require_outline_approval is set but no outline_gate is "
                "configured for this deployment -- falling through to "
                "the full pipeline without an outline review stop."
            ),
        )
    await _drive_to_completion(
        deps.research_svc,
        session_id,
        lambda: deps.content_svc.generate_full_article(session_id),  # type: ignore[union-attr]
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


def _content_ready(detail: SessionDetail, deps: PipelineDeps) -> bool:
    if detail.session.status != "complete":
        logger.warning(
            "skipping_content_pipeline",
            session_id=str(detail.session.id),
            reason=f"research status={detail.session.status}",
        )
        return False
    if deps.content_svc is None or not hasattr(
        deps.content_svc, "generate_full_article"
    ):
        logger.warning(
            "skipping_content_pipeline",
            session_id=str(detail.session.id),
            reason="content_service not available",
        )
        return False
    return True


async def _run_outline_gate(deps: PipelineDeps, session_id: UUID) -> None:
    try:
        await deps.outline_gate.generate_outline_only(session_id)  # type: ignore[union-attr]
        await deps.research_svc.update_session_status(
            session_id, "awaiting_outline_review"
        )
        logger.info("outline_awaiting_review", session_id=str(session_id))
    except PipelineCancelled:
        logger.info("outline_cancelled_mid_run", session_id=str(session_id))
    except Exception as exc:
        logger.error(
            "outline_generation_failed",
            session_id=str(session_id),
            error=str(exc),
            exc_info=True,
        )
        await deps.research_svc.update_session_status(session_id, "article_failed")


async def _drive_to_completion(
    research_svc: ResearchService,
    session_id: UUID,
    generate: Callable[[], Awaitable[object]],
) -> None:
    """Set `generating_article`, run `generate`, land on complete/failed."""
    if await _is_cancelled(research_svc, session_id):
        logger.info("pipeline_cancelled_before_start", session_id=str(session_id))
        return
    await research_svc.update_session_status(session_id, "generating_article")
    try:
        await generate()
        await research_svc.update_session_status(session_id, "article_complete")
    except PipelineCancelled:
        # The cancel endpoint already wrote "cancelled" — leave it.
        logger.info("pipeline_cancelled_mid_run", session_id=str(session_id))
    except Exception as exc:
        logger.error(
            "content_pipeline_failed",
            session_id=str(session_id),
            error=str(exc),
            exc_info=True,
        )
        await research_svc.update_session_status(session_id, "article_failed")
