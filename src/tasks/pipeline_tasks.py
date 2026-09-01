"""Celery tasks that run the article pipeline on the worker (INFRA-007).

Each task deserializes only primitives (session id string, topic dict) and
builds the service graph INSIDE its own event loop via
`src/services/bootstrap.py` — the async engine's connection pool binds to
the running loop, so construction and pipeline must share one
`asyncio.run` (a pool built in a different/closed loop raises "attached to
a different loop"). Construction costs ~1-2s per task against multi-minute
pipeline runs; the engine is disposed at task end.

Tasks run inside a fresh contextvars context, because the orchestrator's
`_record_step` binds `current_session_id`/`current_step_name` without
resetting them and prefork workers reuse processes between tasks (stale
bindings would mis-attribute `llm_calls` rows).
"""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any
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

logger = structlog.get_logger()


async def _with_services(run: Callable[[PipelineDeps], Awaitable[None]]) -> None:
    """Build the service graph in the CURRENT loop, run, dispose the engine."""
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
    engine = create_async_engine(settings.database_url)
    try:
        sf = get_session_factory(engine)
        resolved = await resolve_runtime_settings(settings, sf)
        services = await build_pipeline_services(resolved, sf)
        deps = PipelineDeps(
            research_svc=services.research_service,
            content_svc=services.content_service,
            outline_gate=services.outline_gate,
            prompt_overrides=services.prompt_override_repo.load_all,
        )
        await run(deps)
    finally:
        await engine.dispose()


def _run_in_fresh_context(
    coro_factory: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    contextvars.copy_context().run(asyncio.run, coro_factory())


def _mark_failed(session_id: str) -> None:
    """Best-effort terminal status so the SSE stream ends (not on cancel)."""

    async def go() -> None:
        from src.config.settings import Settings
        from src.db.engine import create_async_engine, get_session_factory
        from src.db.repositories import PgResearchSessionRepository

        engine = create_async_engine(Settings().database_url)
        try:
            repo = PgResearchSessionRepository(get_session_factory(engine))
            session = await repo.get(UUID(session_id))
            # Never overwrite a user cancel (terminal by intent).
            if session is not None and session.status != "cancelled":
                await repo.update(
                    session.model_copy(update={"status": "article_failed"})
                )
        finally:
            await engine.dispose()

    try:
        asyncio.run(go())
    except Exception as exc:
        logger.error("worker_mark_failed_error", error=str(exc))


@celery_app.task(name="cognify.run_full_pipeline")  # type: ignore[untyped-decorator]
def run_full_pipeline_task(session_id: str, topic_json: dict[str, object]) -> None:
    topic = TopicInput.model_validate(topic_json)
    sid = UUID(session_id)
    try:
        _run_in_fresh_context(
            lambda: _with_services(lambda deps: _run_full_pipeline(deps, sid, topic))
        )
    except PipelineCancelled:
        logger.info("worker_pipeline_cancelled", session_id=session_id)
    except Exception:
        _mark_failed(session_id)
        raise


@celery_app.task(name="cognify.run_drafting_pipeline")  # type: ignore[untyped-decorator]
def run_drafting_pipeline_task(session_id: str) -> None:
    sid = UUID(session_id)
    try:
        _run_in_fresh_context(
            lambda: _with_services(lambda deps: _run_drafting_pipeline(deps, sid))
        )
    except PipelineCancelled:
        logger.info("worker_pipeline_cancelled", session_id=session_id)
    except Exception:
        _mark_failed(session_id)
        raise
