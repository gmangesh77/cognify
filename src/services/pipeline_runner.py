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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from src.models.research import TopicInput
    from src.services.content import ContentService
    from src.services.content.outline_gate import OutlineGateService
    from src.services.research import ResearchService, SessionDetail

logger = structlog.get_logger()


@dataclass(frozen=True)
class PipelineDeps:
    """Bundled dependencies for the background pipeline runners."""

    research_svc: ResearchService
    content_svc: ContentService | None
    outline_gate: OutlineGateService | None


async def _run_full_pipeline(
    deps: PipelineDeps,
    session_id: UUID,
    topic: TopicInput,
) -> None:
    """Research → (outline gate) → content generation pipeline."""
    try:
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
    except asyncio.CancelledError:
        await deps.research_svc.update_session_status(session_id, "cancelled")
        raise


async def _run_drafting_pipeline(deps: PipelineDeps, session_id: UUID) -> None:
    """Resume the pipeline from an editor-approved outline."""
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
    await research_svc.update_session_status(session_id, "generating_article")
    try:
        await generate()
        await research_svc.update_session_status(session_id, "article_complete")
    except Exception as exc:
        logger.error(
            "content_pipeline_failed",
            session_id=str(session_id),
            error=str(exc),
            exc_info=True,
        )
        await research_svc.update_session_status(session_id, "article_failed")
