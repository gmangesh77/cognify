"""AUTHOR-010 — per-step model routing via the tracker's step contextvar."""

from __future__ import annotations

from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from src.utils.tiered_llm import KNOWN_LLM_STEPS, TieredChatModel
from src.utils.tracked_llm import (
    TrackedChatModel,
    current_session_id,
    current_step_name,
)


class _NamedFake(FakeListChatModel):
    """FakeListChatModel with a `model` attribute like ChatAnthropic."""

    model: str = "fake"


def _fake(name: str, reply: str) -> _NamedFake:
    return _NamedFake(model=name, responses=[reply, reply, reply])


def _tiered() -> TieredChatModel:
    return TieredChatModel(
        default=_fake("claude-sonnet", "from sonnet"),
        by_step={"content_queries": _fake("claude-haiku", "from haiku")},
    )


class TestTieredChatModel:
    async def test_routes_to_step_model_when_step_is_bound(self) -> None:
        llm = _tiered()
        token = current_step_name.set("content_queries")
        try:
            out = await llm.ainvoke([HumanMessage(content="hi")])
        finally:
            current_step_name.reset(token)
        assert out.content == "from haiku"

    async def test_falls_back_to_default_for_unmapped_step(self) -> None:
        llm = _tiered()
        token = current_step_name.set("content_draft")
        try:
            out = await llm.ainvoke([HumanMessage(content="hi")])
        finally:
            current_step_name.reset(token)
        assert out.content == "from sonnet"

    async def test_falls_back_to_default_when_no_step_bound(self) -> None:
        out = await _tiered().ainvoke([HumanMessage(content="hi")])
        assert out.content == "from sonnet"

    def test_sync_invoke_routes_too(self) -> None:
        llm = _tiered()
        token = current_step_name.set("content_queries")
        try:
            out = llm.invoke([HumanMessage(content="hi")])
        finally:
            current_step_name.reset(token)
        assert out.content == "from haiku"

    def test_model_property_reflects_active_model(self) -> None:
        llm = _tiered()
        assert llm.model == "claude-sonnet"
        token = current_step_name.set("content_queries")
        try:
            assert llm.model == "claude-haiku"
        finally:
            current_step_name.reset(token)

    def test_llm_type(self) -> None:
        assert _tiered()._llm_type == "tiered"

    def test_known_steps_cover_the_content_and_research_graphs(self) -> None:
        for step in (
            "content_outline",
            "content_queries",
            "content_draft",
            "content_validate",
            "content_citations",
            "content_humanize",
            "content_seo",
            "content_charts",
            "content_diagrams",
            "plan_research",
            "evaluate_completeness",
            "section_regenerate",
            "seo_regenerate",
        ):
            assert step in KNOWN_LLM_STEPS


class TestTrackedOverTiered:
    async def test_tracker_records_the_model_that_ran(self) -> None:
        saved: list[object] = []

        class _Repo:
            async def create(self, call: object) -> None:
                saved.append(call)

        tracked = TrackedChatModel(inner=_tiered(), repo=_Repo())
        sid_token = current_session_id.set(uuid4())
        step_token = current_step_name.set("content_queries")
        try:
            await tracked.ainvoke([HumanMessage(content="hi")])
        finally:
            current_step_name.reset(step_token)
            current_session_id.reset(sid_token)
        assert len(saved) == 1
        assert saved[0].model_name == "claude-haiku"
        assert saved[0].call_name == "content_queries"
