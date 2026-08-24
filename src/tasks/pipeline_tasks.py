"""Celery tasks that run the article pipeline on the worker (INFRA-007).

Each task deserializes only primitives (session id string, topic dict),
rebuilds the service graph once per worker process via
`src/services/bootstrap.py`, and runs the same runners the API uses —
inside a fresh contextvars context, because the orchestrator's
`_record_step` binds `current_session_id`/`current_step_name` without
resetting them and prefork workers reuse processes between tasks (stale
bindings would mis-attribute `llm_calls` rows).
"""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

from src.models.research import TopicInput
from src.services.pipeline_runner import (
    PipelineCancelled,
    PipelineDeps,
    _run_drafting_pipeline,
    _run_full_pipeline,
)
from src.tasks.celery_app import celery_app

if TYPE_CHECKING:
    from src.services.bootstrap import PipelineServices

logger = structlog.get_logger()

_services: PipelineServices | None = None


def _get_services() -> PipelineServices:
    """Build (once per worker process) the pipeline service graph."""
    global _services
    if _services is None:
        from src.config.settings import Settings
        from src.db.engine import create_async_engine, get_session_factory
        from src.services.bootstrap import (
            build_pipeline_services,
            resolve_runtime_settings,
        )

        settings = Settings()
        if not settings.database_url:
            msg = "COGNIFY_DATABASE_URL is required for the Celery worker"
            raise RuntimeError(msg)
        sf = get_session_factory(create_async_engine(settings.database_url))
        resolved = asyncio.run(resolve_runtime_settings(settings, sf))
        _services = asyncio.run(build_pipeline_services(resolved, sf))
        logger.info("worker_services_initialized")
    return _services


def _deps(services: PipelineServices) -> PipelineDeps:
    return PipelineDeps(
        research_svc=services.research_service,
        content_svc=services.content_service,
        outline_gate=services.outline_gate,
    )


def _run_in_fresh_context(
    coro_factory: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    contextvars.copy_context().run(asyncio.run, coro_factory())


def _mark_failed(session_id: str) -> None:
    """Best-effort terminal status so the SSE stream ends (not on cancel)."""
    try:
        services = _get_services()
        asyncio.run(
            services.research_service.update_session_status(
                UUID(session_id), "article_failed"
            )
        )
    except Exception as exc:
        logger.error("worker_mark_failed_error", error=str(exc))


@celery_app.task(name="cognify.run_full_pipeline")  # type: ignore[untyped-decorator]
def run_full_pipeline_task(session_id: str, topic_json: dict[str, object]) -> None:
    deps = _deps(_get_services())
    topic = TopicInput.model_validate(topic_json)
    sid = UUID(session_id)
    try:
        _run_in_fresh_context(lambda: _run_full_pipeline(deps, sid, topic))
    except PipelineCancelled:
        logger.info("worker_pipeline_cancelled", session_id=session_id)
    except Exception:
        _mark_failed(session_id)
        raise


@celery_app.task(name="cognify.run_drafting_pipeline")  # type: ignore[untyped-decorator]
def run_drafting_pipeline_task(session_id: str) -> None:
    deps = _deps(_get_services())
    sid = UUID(session_id)
    try:
        _run_in_fresh_context(lambda: _run_drafting_pipeline(deps, sid))
    except PipelineCancelled:
        logger.info("worker_pipeline_cancelled", session_id=session_id)
    except Exception:
        _mark_failed(session_id)
        raise
