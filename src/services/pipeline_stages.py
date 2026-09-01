"""Pipeline stage helpers shared by the two runners (AUTHOR-012 split).

Split out of `pipeline_runner.py` to keep both files under the repo's
200-line budget — behaviour and public names are unchanged, only the
module boundary moved. `PipelineCancelled` lives here (rather than in
`pipeline_runner`) because the cooperative-cancellation check
(`_is_cancelled`) and the terminal-status bookkeeping
(`_drive_to_completion`, `_run_outline_gate`) all revolve around it, and
keeping it here avoids a circular import between the two modules.
`pipeline_runner` re-imports and re-exports it (and `make_cancel_check`
stays there) so existing `from src.services.pipeline_runner import
PipelineCancelled` call sites are unaffected.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from src.services.pipeline_runner import PipelineDeps
    from src.services.research import ResearchService, SessionDetail

logger = structlog.get_logger()


class PipelineCancelled(Exception):
    """Raised by cooperative cancel checks when the session was cancelled.

    In worker mode (INFRA-007) `asyncio.Task.cancel()` cannot reach the
    run, so the pipeline re-reads the session status and stops. The cancel
    endpoint already wrote `"cancelled"` — handlers must NOT overwrite it.
    """


async def _is_cancelled(research_svc: ResearchService, session_id: UUID) -> bool:
    detail = await research_svc.get_session(session_id)
    return detail.session.status == "cancelled"


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
