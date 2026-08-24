"""Celery pipeline tasks + CeleryDispatcher (INFRA-007 Task 5).

Tasks are exercised as plain functions (`.run(...)`) — no broker needed.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from src.models.research import TopicInput
from src.services.pipeline_dispatch import CeleryDispatcher
from src.services.pipeline_runner import PipelineCancelled
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
class _FakeServices:
    research_service: object = None
    content_service: object = None
    outline_gate: object = None


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

        monkeypatch.setattr(
            "src.tasks.pipeline_tasks._run_full_pipeline", fake_runner
        )
        monkeypatch.setattr(
            "src.tasks.pipeline_tasks._get_services", lambda: _FakeServices()
        )
        sid = uuid4()
        run_full_pipeline_task.run(str(sid), _topic().model_dump(mode="json"))
        assert seen["session_id"] == sid
        assert seen["title"] == "Test topic"
        assert seen["keywords"] == ("a", "b")

    def test_pipeline_cancelled_is_not_a_task_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def cancelled(
            deps: object, session_id: UUID, topic: TopicInput
        ) -> None:
            raise PipelineCancelled()

        monkeypatch.setattr(
            "src.tasks.pipeline_tasks._run_full_pipeline", cancelled
        )
        monkeypatch.setattr(
            "src.tasks.pipeline_tasks._get_services", lambda: _FakeServices()
        )
        run_full_pipeline_task.run(str(uuid4()), _topic().model_dump(mode="json"))


class TestRunDraftingPipelineTask:
    def test_drives_drafting_runner(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, object] = {}

        async def fake_runner(deps: object, session_id: UUID) -> None:
            seen["session_id"] = session_id

        monkeypatch.setattr(
            "src.tasks.pipeline_tasks._run_drafting_pipeline", fake_runner
        )
        monkeypatch.setattr(
            "src.tasks.pipeline_tasks._get_services", lambda: _FakeServices()
        )
        sid = uuid4()
        run_drafting_pipeline_task.run(str(sid))
        assert seen["session_id"] == sid


class TestCeleryDispatcher:
    def test_serializes_and_uses_session_task_id(self) -> None:
        sent: list[tuple[str, list[object], str]] = []

        class _FakeCelery:
            def send_task(
                self, name: str, args: list[object], task_id: str
            ) -> None:
                sent.append((name, args, task_id))

        d = CeleryDispatcher(_FakeCelery())  # type: ignore[arg-type]
        sid = uuid4()
        d.dispatch_full_pipeline(sid, _topic())
        name, args, task_id = sent[0]
        assert name == "cognify.run_full_pipeline"
        assert args[0] == str(sid)
        assert isinstance(args[1], dict)
        assert args[1]["id"] == str(args[1]["id"])  # json-mode: plain strings
        assert task_id == str(sid)

    def test_drafting_uses_prefixed_task_id(self) -> None:
        sent: list[tuple[str, list[object], str]] = []

        class _FakeCelery:
            def send_task(
                self, name: str, args: list[object], task_id: str
            ) -> None:
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
