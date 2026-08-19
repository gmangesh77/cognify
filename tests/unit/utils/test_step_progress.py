from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.research_db import AgentStep
from src.utils.step_progress import (
    current_progress_reporter,
    make_step_reporter,
    report_progress,
)


class _Repo:
    def __init__(self) -> None:
        self.updates: list[AgentStep] = []

    async def update(self, step: AgentStep) -> AgentStep:
        self.updates.append(step)
        return step


def _step() -> AgentStep:
    return AgentStep(
        session_id=uuid4(), step_name="content_draft", started_at=datetime.now(UTC)
    )


@pytest.mark.asyncio
async def test_report_progress_noop_without_reporter() -> None:
    current_progress_reporter.set(None)
    await report_progress({"sections_done": 1})  # must not raise


@pytest.mark.asyncio
async def test_step_reporter_merges_output_data() -> None:
    repo = _Repo()
    reporter = make_step_reporter(repo, _step())
    token = current_progress_reporter.set(reporter)
    try:
        await report_progress({"sections_done": 1, "sections_total": 3})
        await report_progress({"sections_done": 2})
    finally:
        current_progress_reporter.reset(token)
    assert repo.updates[-1].output_data == {"sections_done": 2, "sections_total": 3}
    assert repo.updates[-1].status == "running"


@pytest.mark.asyncio
async def test_reporter_swallows_repo_errors() -> None:
    class Boom:
        async def update(self, step: AgentStep) -> AgentStep:
            raise RuntimeError("db down")

    token = current_progress_reporter.set(make_step_reporter(Boom(), _step()))
    try:
        await report_progress({"x": 1})  # must not raise
    finally:
        current_progress_reporter.reset(token)
