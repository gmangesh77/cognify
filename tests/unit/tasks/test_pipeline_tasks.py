"""Celery pipeline tasks + CeleryDispatcher (INFRA-007 Task 5).

Tasks are exercised as plain functions (`.run(...)`) — no broker needed.
`_with_services` is patched so no DB/engine is touched; the fake still
invokes the runner callback in-loop, mirroring the real control flow.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from src.models.research import TopicInput
from src.services.pipeline_dispatch import CeleryDispatcher
from src.services.pipeline_runner import PipelineCancelled, PipelineDeps
from src.tasks.pipeline_tasks import (
    run_drafting_pipeline_task,
    run_full_pipeline_task,
)


def _topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="Test topic",
        description="d",
        domain="testing",
        keywords=("a", "b"),
    )


@dataclass
class _FakeDeps:
    research_svc: object = None
    content_svc: object = None
    outline_gate: object = None


def _fake_with_services(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(run: Callable[[PipelineDeps], Awaitable[None]]) -> None:
        await run(_FakeDeps())  # type: ignore[arg-type]

    monkeypatch.setattr("src.tasks.pipeline_tasks._with_services", fake)


class TestRunFullPipelineTask:
    def test_drives_runner_with_deserialized_args(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: dict[str, object] = {}

        async def fake_runner(
            deps: object, session_id: UUID, topic: TopicInput
        ) -> None:
            seen["session_id"] = session_id
            seen["title"] = topic.title
            seen["keywords"] = topic.keywords

        monkeypatch.setattr("src.tasks.pipeline_tasks._run_full_pipeline", fake_runner)
        _fake_with_services(monkeypatch)
        sid = uuid4()
        run_full_pipeline_task.run(str(sid), _topic().model_dump(mode="json"))
        assert seen["session_id"] == sid
        assert seen["title"] == "Test topic"
        assert seen["keywords"] == ("a", "b")

    def test_pipeline_cancelled_is_not_a_task_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def cancelled(deps: object, session_id: UUID, topic: TopicInput) -> None:
            raise PipelineCancelled()

        monkeypatch.setattr("src.tasks.pipeline_tasks._run_full_pipeline", cancelled)
        _fake_with_services(monkeypatch)
        run_full_pipeline_task.run(str(uuid4()), _topic().model_dump(mode="json"))

    def test_unexpected_error_marks_failed_and_reraises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def boom(deps: object, session_id: UUID, topic: TopicInput) -> None:
            raise ValueError("boom")

        marked: list[str] = []
        monkeypatch.setattr("src.tasks.pipeline_tasks._run_full_pipeline", boom)
        monkeypatch.setattr(
            "src.tasks.pipeline_tasks._mark_failed", lambda sid: marked.append(sid)
        )
        _fake_with_services(monkeypatch)
        sid = uuid4()
        with pytest.raises(ValueError):
            run_full_pipeline_task.run(str(sid), _topic().model_dump(mode="json"))
        assert marked == [str(sid)]


class TestRunDraftingPipelineTask:
    def test_drives_drafting_runner(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, object] = {}

        async def fake_runner(deps: object, session_id: UUID) -> None:
            seen["session_id"] = session_id

        monkeypatch.setattr(
            "src.tasks.pipeline_tasks._run_drafting_pipeline", fake_runner
        )
        _fake_with_services(monkeypatch)
        sid = uuid4()
        run_drafting_pipeline_task.run(str(sid))
        assert seen["session_id"] == sid


class TestCeleryDispatcher:
    def test_serializes_and_uses_session_task_id(self) -> None:
        sent: list[tuple[str, list[object], str]] = []

        class _FakeCelery:
            def send_task(self, name: str, args: list[object], task_id: str) -> None:
                sent.append((name, args, task_id))

        d = CeleryDispatcher(_FakeCelery())  # type: ignore[arg-type]
        sid = uuid4()
        d.dispatch_full_pipeline(sid, _topic())
        name, args, task_id = sent[0]
        assert name == "cognify.run_full_pipeline"
        assert args[0] == str(sid)
        assert isinstance(args[1], dict)
        assert isinstance(args[1]["id"], str)  # json-mode dump: plain strings
        assert task_id == str(sid)

    def test_drafting_uses_prefixed_task_id(self) -> None:
        sent: list[tuple[str, list[object], str]] = []

        class _FakeCelery:
            def send_task(self, name: str, args: list[object], task_id: str) -> None:
                sent.append((name, args, task_id))

        d = CeleryDispatcher(_FakeCelery())  # type: ignore[arg-type]
        sid = uuid4()
        d.dispatch_drafting(sid)
        name, args, task_id = sent[0]
        assert name == "cognify.run_drafting_pipeline"
        assert args == [str(sid)]
        assert task_id == f"draft-{sid}"

    def test_cancel_revokes_both_task_ids(self) -> None:
        revoked: list[str] = []

        class _Control:
            def revoke(self, task_id: str) -> None:
                revoked.append(task_id)

        class _FakeCelery:
            control = _Control()

        d = CeleryDispatcher(_FakeCelery())  # type: ignore[arg-type]
        sid = uuid4()
        assert d.cancel(sid) is True
        assert revoked == [str(sid), f"draft-{sid}"]
