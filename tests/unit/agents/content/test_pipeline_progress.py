from uuid import uuid4

import pytest

from src.agents.content.pipeline import ContentGraphDeps, _wrap_node
from src.models.research_db import AgentStep
from src.utils.step_progress import report_progress


class _StepRepo:
    def __init__(self) -> None:
        self.rows: list[AgentStep] = []

    async def create(self, step: AgentStep) -> AgentStep:
        self.rows.append(step)
        return step

    async def update(self, step: AgentStep) -> AgentStep:
        self.rows.append(step)
        return step

    async def list_by_session(self, session_id):  # type: ignore[no-untyped-def]
        return [r for r in self.rows if r.session_id == session_id]


@pytest.mark.asyncio
async def test_wrap_node_binds_progress_reporter() -> None:
    repo = _StepRepo()
    sid = uuid4()
    deps = ContentGraphDeps(step_repo=repo, session_id=sid)  # type: ignore[arg-type]

    async def node(state):  # type: ignore[no-untyped-def]
        await report_progress({"sections_done": 1, "sections_total": 2})
        return {"status": "draft_complete"}

    wrapped = _wrap_node("draft", node, deps)
    await wrapped({"session_id": sid})
    running = [r for r in repo.rows if r.status == "running" and r.output_data]
    assert running and running[-1].output_data["sections_done"] == 1
    assert repo.rows[-1].status == "complete"


@pytest.mark.asyncio
async def test_wrap_node_unbinds_reporter_after_node() -> None:
    from src.utils.step_progress import current_progress_reporter

    repo = _StepRepo()
    deps = ContentGraphDeps(step_repo=repo, session_id=uuid4())  # type: ignore[arg-type]

    async def node(state):  # type: ignore[no-untyped-def]
        return {}

    await _wrap_node("x", node, deps)({"session_id": deps.session_id})
    assert current_progress_reporter.get() is None


async def test_wrap_node_binds_step_name_without_step_repo() -> None:
    """AUTHOR-010: tiering keys on the step name even with no step repo."""
    from src.utils.tracked_llm import current_step_name

    seen: list[str] = []

    async def node(state):  # type: ignore[no-untyped-def]
        seen.append(current_step_name.get())
        return {}

    wrapped = _wrap_node("draft", node, None)
    await wrapped({})  # type: ignore[misc]
    assert seen == ["content_draft"]
    assert current_step_name.get() == "unknown"
