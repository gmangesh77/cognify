"""Turn persisted agent_steps + session status into a live event stream.

DB-tailing (not pub/sub) so it works identically whether the pipeline runs
in-process or in a worker, and replays current state on connect.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

import structlog

from src.api.errors import NotFoundError
from src.models.research_db import AgentStep
from src.models.session_events import TERMINAL_STATUSES, EventType, SessionEvent
from src.services.research import ResearchService

logger = structlog.get_logger()


@dataclass(frozen=True)
class TailOptions:
    poll_seconds: float = 1.0
    keepalive_seconds: float = 15.0
    complete_grace_seconds: float = 30.0
    max_seconds: float = 1800.0


@dataclass(frozen=True)
class _Ctx:
    svc: ResearchService
    session_id: UUID
    opts: TailOptions


@dataclass
class _State:
    status: str
    steps: list[AgentStep] = field(default_factory=list)
    last_change: float = 0.0
    last_emit: float = 0.0


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def _ev(
    kind: EventType, step: AgentStep, data: dict[str, object] | None = None
) -> SessionEvent:
    return SessionEvent(
        type=kind,
        session_id=step.session_id,
        step=step.step_name,
        status=step.status,
        data={"step_id": str(step.id), **(data or {})},
    )


def diff_steps(
    prev: list[AgentStep], curr: list[AgentStep], session_id: UUID
) -> list[SessionEvent]:
    """Events explaining how ``curr`` differs from ``prev`` (keyed by step id).

    ``session_id`` is accepted (not just derived from ``step.session_id``) to
    keep this a stable, self-describing signature for Task 4's callers; every
    step in ``curr`` is assumed to belong to ``session_id`` already.
    """
    before = {s.id: s for s in prev}
    out: list[SessionEvent] = []
    for s in curr:
        old = before.get(s.id)
        if old is None:
            out.append(_ev("step_started", s))
        elif (
            old.status == "running"
            and s.status == "running"
            and old.output_data != s.output_data
        ):
            out.append(_ev("step_progress", s, s.output_data))
        elif old.status != s.status and s.status == "complete":
            out.append(_ev("step_done", s, {"duration_ms": s.duration_ms}))
        elif old.status != s.status and s.status == "failed":
            out.append(_ev("step_failed", s, s.output_data))
    return out


def _snapshot(sid: UUID, status: str, steps: list[AgentStep]) -> SessionEvent:
    rows = [
        s.model_dump(
            mode="json",
            include={
                "id",
                "step_name",
                "status",
                "started_at",
                "completed_at",
                "duration_ms",
                "output_data",
            },
        )
        for s in steps
    ]
    return SessionEvent(
        type="snapshot", session_id=sid, status=status, data={"steps": rows}
    )


def _status_changed(sid: UUID, status: str) -> SessionEvent:
    return SessionEvent(type="status_changed", session_id=sid, status=status)


async def _poll_once(ctx: _Ctx, state: _State) -> tuple[list[SessionEvent], _State]:
    """Sleep one poll interval, fetch the session, and diff against ``state``."""
    await asyncio.sleep(ctx.opts.poll_seconds)
    detail = await ctx.svc.get_session(ctx.session_id)
    events = diff_steps(state.steps, list(detail.steps), ctx.session_id)
    now = time.monotonic()
    if detail.session.status != state.status:
        events.insert(0, _status_changed(ctx.session_id, detail.session.status))
    new_state = _State(
        detail.session.status, list(detail.steps), state.last_change, state.last_emit
    )
    if events:
        new_state.last_change = new_state.last_emit = now
    elif now - state.last_emit >= ctx.opts.keepalive_seconds:
        events = [SessionEvent(type="keepalive", session_id=ctx.session_id)]
        new_state.last_emit = now
    return events, new_state


def _should_stop(state: _State, opts: TailOptions, started: float) -> bool:
    if is_terminal(state.status) or time.monotonic() - started >= opts.max_seconds:
        return True
    return (
        state.status == "complete"
        and time.monotonic() - state.last_change >= opts.complete_grace_seconds
    )


def _timed_out(state: _State, opts: TailOptions, started: float) -> bool:
    """True when the loop stopped because ``max_seconds`` elapsed.

    Excludes terminal statuses and the "complete + grace expired" path,
    which are expected stops, not safety-valve timeouts.
    """
    if is_terminal(state.status) or state.status == "complete":
        return False
    return time.monotonic() - started >= opts.max_seconds


def _final_done(
    session_id: UUID, state: _State, opts: TailOptions, started: float
) -> SessionEvent:
    if not _timed_out(state, opts, started):
        return SessionEvent(type="done", session_id=session_id, status=state.status)
    logger.warning(
        "session_events_timeout",
        session_id=str(session_id),
        max_seconds=opts.max_seconds,
    )
    return SessionEvent(
        type="done",
        session_id=session_id,
        status=state.status,
        data={"reason": "timeout"},
    )


async def tail_session(
    svc: ResearchService, session_id: UUID, opts: TailOptions
) -> AsyncIterator[SessionEvent]:
    """Yield snapshot, then diffs until the session reaches a terminal state."""
    try:
        detail = await svc.get_session(session_id)
    except NotFoundError as exc:
        yield SessionEvent(
            type="error", session_id=session_id, data={"error": str(exc)}
        )
        return
    now = time.monotonic()
    state = _State(detail.session.status, list(detail.steps), now, now)
    yield _snapshot(session_id, state.status, state.steps)
    ctx, started = _Ctx(svc, session_id, opts), now
    while not _should_stop(state, opts, started):
        events, state = await _poll_once(ctx, state)
        for e in events:
            yield e
    yield _final_done(session_id, state, opts, started)
