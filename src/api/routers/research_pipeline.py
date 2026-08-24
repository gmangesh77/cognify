"""Router-side access to the PipelineDispatcher (INFRA-007).

The runners themselves live in `src/services/pipeline_runner.py`; the
dispatcher implementations in `src/services/pipeline_dispatch.py`. This
module owns the lazy, per-app construction: the dispatcher is built on
first use from `app.state` (after the lifespan finished rebuilding
services with resolved API keys), and cached on `app.state`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.services.pipeline_dispatch import (
    InProcessDispatcher,
    PipelineDeps,
    PipelineDispatcher,
)
from src.services.session_tasks import SessionTaskRegistry

if TYPE_CHECKING:
    from fastapi import Request

__all__ = ["PipelineDeps", "get_pipeline_dispatcher", "get_session_tasks"]


def get_session_tasks(request: Request) -> SessionTaskRegistry:
    """Fetch (or lazily create) the app's SessionTaskRegistry."""
    if not hasattr(request.app.state, "session_tasks"):
        request.app.state.session_tasks = SessionTaskRegistry()
    return request.app.state.session_tasks  # type: ignore[no-any-return]


def _build_dispatcher(request: Request) -> PipelineDispatcher:
    deps = PipelineDeps(
        research_svc=request.app.state.research_service,
        content_svc=getattr(request.app.state, "content_service", None),
        outline_gate=getattr(request.app.state, "outline_gate", None),
    )
    return InProcessDispatcher(deps, get_session_tasks(request))


def get_pipeline_dispatcher(request: Request) -> PipelineDispatcher:
    """Fetch (or lazily build) the app's PipelineDispatcher."""
    if not hasattr(request.app.state, "pipeline_dispatcher"):
        request.app.state.pipeline_dispatcher = _build_dispatcher(request)
    return request.app.state.pipeline_dispatcher  # type: ignore[no-any-return]
