"""Tests for TrackedChatModel wrapper and LLM call recording."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from src.models.llm_call import LlmCall
from src.utils.llm_call_repo import InMemoryLlmCallRepository
from src.utils.tracked_llm import (
    TrackedChatModel,
    _messages_to_dicts,
    current_session_id,
    current_step_id,
    current_step_name,
)


class FakeInnerLlm(BaseChatModel):
    """Minimal fake LLM that extends BaseChatModel for Pydantic compat."""

    response: str = "Hello!"
    raise_error: bool = False
    model: str = "fake-model-v1"

    @property
    def _llm_type(self) -> str:
        return "fake"

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.raise_error:
            raise ValueError("LLM exploded")
        msg = AIMessage(content=self.response)
        gen = ChatGeneration(message=msg, text=self.response)
        return ChatResult(generations=[gen])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        msg = AIMessage(content=self.response)
        gen = ChatGeneration(message=msg, text=self.response)
        return ChatResult(generations=[gen])


class TestMessagesToDicts:
    def test_converts_system_and_human_messages(self) -> None:
        messages = [
            SystemMessage(content="Be helpful"),
            HumanMessage(content="Tell me about X"),
        ]
        result = _messages_to_dicts(messages)
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "Be helpful"}
        assert result[1] == {"role": "human", "content": "Tell me about X"}

    def test_handles_empty_list(self) -> None:
        assert _messages_to_dicts([]) == []


class TestTrackedChatModel:
    @pytest.mark.asyncio
    async def test_records_successful_call(self) -> None:
        repo = InMemoryLlmCallRepository()
        inner = FakeInnerLlm(response="Generated text", model="fake-model-v1")
        wrapper = TrackedChatModel(inner=inner, repo=repo)

        session_id = uuid4()
        step_id = uuid4()
        current_session_id.set(session_id)
        current_step_id.set(step_id)
        current_step_name.set("plan_research")

        messages = [SystemMessage(content="sys"), HumanMessage(content="user")]
        result = await wrapper._agenerate(messages)

        assert result.generations[0].text == "Generated text"
        calls = await repo.list_by_session(session_id)
        assert len(calls) == 1
        call = calls[0]
        assert call.call_name == "plan_research"
        assert call.model_name == "fake-model-v1"
        assert call.session_id == session_id
        assert call.step_id == step_id
        assert call.response_content == "Generated text"
        assert call.error is None
        assert call.duration_ms is not None
        assert call.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_records_failed_call(self) -> None:
        repo = InMemoryLlmCallRepository()
        inner = FakeInnerLlm(raise_error=True, model="fake-model-v1")
        wrapper = TrackedChatModel(inner=inner, repo=repo)

        session_id = uuid4()
        current_session_id.set(session_id)
        current_step_id.set(None)
        current_step_name.set("outline")

        with pytest.raises(ValueError, match="LLM exploded"):
            await wrapper._agenerate([HumanMessage(content="hi")])

        calls = await repo.list_by_session(session_id)
        assert len(calls) == 1
        assert calls[0].error == "LLM exploded"
        assert calls[0].response_content == ""

    @pytest.mark.asyncio
    async def test_skips_recording_when_no_session(self) -> None:
        repo = InMemoryLlmCallRepository()
        inner = FakeInnerLlm(response="ok", model="fake-model-v1")
        wrapper = TrackedChatModel(inner=inner, repo=repo)

        current_session_id.set(None)

        result = await wrapper._agenerate([HumanMessage(content="hi")])
        assert result.generations[0].text == "ok"
        calls = await repo.list_by_session(uuid4())
        assert len(calls) == 0

    @pytest.mark.asyncio
    async def test_prompt_messages_are_serialized(self) -> None:
        repo = InMemoryLlmCallRepository()
        inner = FakeInnerLlm(model="fake-model-v1")
        wrapper = TrackedChatModel(inner=inner, repo=repo)

        session_id = uuid4()
        current_session_id.set(session_id)
        current_step_id.set(None)
        current_step_name.set("test_step")

        await wrapper._agenerate(
            [
                SystemMessage(content="system prompt"),
                HumanMessage(content="user input"),
            ]
        )

        calls = await repo.list_by_session(session_id)
        msgs = calls[0].prompt_messages
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["content"] == "user input"


class TestInMemoryLlmCallRepository:
    @pytest.mark.asyncio
    async def test_create_and_list_by_session(self) -> None:
        repo = InMemoryLlmCallRepository()
        sid = uuid4()
        call = LlmCall(
            session_id=sid,
            call_name="test",
            model_name="m",
            started_at=datetime.now(UTC),
        )
        await repo.create(call)
        result = await repo.list_by_session(sid)
        assert len(result) == 1
        assert result[0].call_name == "test"

    @pytest.mark.asyncio
    async def test_list_by_step(self) -> None:
        repo = InMemoryLlmCallRepository()
        sid = uuid4()
        step_id = uuid4()
        call = LlmCall(
            session_id=sid,
            step_id=step_id,
            call_name="test",
            model_name="m",
            started_at=datetime.now(UTC),
        )
        await repo.create(call)
        result = await repo.list_by_step(step_id)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_by_step_no_match(self) -> None:
        repo = InMemoryLlmCallRepository()
        result = await repo.list_by_step(uuid4())
        assert result == []
