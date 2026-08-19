from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.research_db import AgentStep
from src.services.session_events import (
    TailOptions,
    diff_steps,
    is_terminal,
    tail_session,
)

SID = uuid4()


def _step(name: str, status: str = "running", **out) -> AgentStep:  # type: ignore[no-untyped-def]
    return AgentStep(
        session_id=SID,
        step_name=name,
        status=status,
        output_data=dict(out),
        started_at=datetime.now(UTC),
    )


def test_diff_emits_started_for_new_step() -> None:
    ev = diff_steps([], [_step("plan_research")], SID)
    assert [e.type for e in ev] == ["step_started"]
    assert ev[0].step == "plan_research"


def test_diff_emits_progress_when_running_output_changes() -> None:
    a = _step("content_draft", sections_done=1)
    b = a.model_copy(update={"output_data": {"sections_done": 2}})
    ev = diff_steps([a], [b], SID)
    assert [e.type for e in ev] == ["step_progress"]
    assert ev[0].data == {"step_id": str(b.id), "sections_done": 2}


def test_diff_emits_done_and_failed() -> None:
    a = _step("x")
    b = _step("y")
    ev = diff_steps(
        [a, b],
        [
            a.model_copy(update={"status": "complete"}),
            b.model_copy(update={"status": "failed", "output_data": {"error": "boom"}}),
        ],
        SID,
    )
    assert [e.type for e in ev] == ["step_done", "step_failed"]
    assert ev[1].data == {"step_id": str(b.id), "error": "boom"}


def test_diff_is_keyed_by_step_id_not_name() -> None:
    a = _step("research_facet_1")
    b = _step("research_facet_1")
    assert [e.type for e in diff_steps([a], [a, b], SID)] == ["step_started"]


@pytest.mark.parametrize(
    "s,expected",
    [
        ("article_complete", True),
        ("article_failed", True),
        ("failed", True),
        ("cancelled", True),
        ("completed", True),
        ("complete", False),
        ("planning", False),
    ],
)
def test_is_terminal(s: str, expected: bool) -> None:
    assert is_terminal(s) is expected


class _Svc:
    """Scripted ResearchService double: each get_session pops the next snapshot."""

    def __init__(self, snapshots):  # type: ignore[no-untyped-def]
        self._snaps = list(snapshots)

    async def get_session(self, session_id):  # type: ignore[no-untyped-def]
        from src.models.research_db import ResearchSession
        from src.services.research import SessionDetail

        status, steps = self._snaps.pop(0) if len(self._snaps) > 1 else self._snaps[0]
        session = ResearchSession(
            id=session_id,
            topic_id=uuid4(),
            topic_title="t",
            status=status,
            started_at=datetime.now(UTC),
        )
        return SessionDetail(session=session, steps=steps)


@pytest.mark.asyncio
async def test_tail_emits_snapshot_then_diffs_then_done() -> None:
    s1 = _step("plan_research")
    svc = _Svc(
        [
            ("planning", [s1]),
            (
                "researching",
                [
                    s1.model_copy(update={"status": "complete"}),
                    _step("content_outline"),
                ],
            ),
            (
                "article_complete",
                [
                    s1.model_copy(update={"status": "complete"}),
                    _step("content_outline", "complete"),
                ],
            ),
        ]
    )
    events = [e async for e in tail_session(svc, SID, TailOptions(poll_seconds=0))]
    types = [e.type for e in events]
    assert types[0] == "snapshot"
    assert events[0].data["steps"][0]["step_name"] == "plan_research"
    assert (
        "status_changed" in types and "step_done" in types and "step_started" in types
    )
    assert types[-1] == "done" and events[-1].status == "article_complete"


@pytest.mark.asyncio
async def test_tail_treats_complete_as_terminal_after_grace() -> None:
    svc = _Svc([("complete", [])])
    opts = TailOptions(poll_seconds=0, complete_grace_seconds=0)
    events = [e async for e in tail_session(svc, SID, opts)]
    assert events[-1].type == "done"


@pytest.mark.asyncio
async def test_tail_emits_timeout_reason_when_max_seconds_exceeded() -> None:
    svc = _Svc([("researching", [])])
    opts = TailOptions(poll_seconds=0, max_seconds=0)
    events = [e async for e in tail_session(svc, SID, opts)]
    assert events[-1].type == "done"
    assert events[-1].data["reason"] == "timeout"


@pytest.mark.asyncio
async def test_tail_stops_on_error_when_session_missing() -> None:
    class Missing:
        async def get_session(self, session_id):  # type: ignore[no-untyped-def]
            from src.api.errors import NotFoundError

            raise NotFoundError("nope")

    events = [
        e async for e in tail_session(Missing(), SID, TailOptions(poll_seconds=0))
    ]
    assert [e.type for e in events] == ["error"]
