"""Transparent LLM wrapper that logs all calls to the database.

Uses contextvars so node/step metadata flows into LLM call records
without modifying any of the 13 existing call sites.
"""

from __future__ import annotations

import contextvars
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from src.models.llm_call import LlmCall

if TYPE_CHECKING:
    from src.utils.llm_call_repo import LlmCallRepository

logger = structlog.get_logger()

# Contextvars set by _record_step / _wrap_node before each node runs
current_step_name: contextvars.ContextVar[str] = contextvars.ContextVar(
    "llm_step_name", default="unknown"
)
current_session_id: contextvars.ContextVar[UUID | None] = contextvars.ContextVar(
    "llm_session_id", default=None
)
current_step_id: contextvars.ContextVar[UUID | None] = contextvars.ContextVar(
    "llm_step_id", default=None
)


def _messages_to_dicts(messages: list[BaseMessage]) -> list[dict[str, str]]:
    """Convert LangChain messages to serializable dicts."""
    result = []
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        result.append({"role": msg.type, "content": content})
    return result


class TrackedChatModel(BaseChatModel):
    """Wrapper that records every LLM call to the database."""

    inner: BaseChatModel
    repo: Any  # LlmCallRepository — Any to avoid Pydantic validation issues

    @property
    def _llm_type(self) -> str:
        return f"tracked-{self.inner._llm_type}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self.inner._generate(messages, stop, run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        session_id = current_session_id.get()
        if session_id is None:
            return await self.inner._agenerate(messages, stop, run_manager, **kwargs)

        started = datetime.now(UTC)
        call = LlmCall(
            session_id=session_id,
            step_id=current_step_id.get(),
            call_name=current_step_name.get("unknown"),
            model_name=getattr(self.inner, "model", "unknown"),
            prompt_messages=_messages_to_dicts(messages),
            started_at=started,
        )
        try:
            result = await self.inner._agenerate(messages, stop, run_manager, **kwargs)
            completed = datetime.now(UTC)
            duration = int((completed - started).total_seconds() * 1000)
            content = result.generations[0].text if result.generations else ""
            usage = _extract_usage(result)
            call = call.model_copy(
                update={
                    "response_content": content,
                    "duration_ms": duration,
                    "completed_at": completed,
                    **usage,
                }
            )
        except Exception as exc:
            completed = datetime.now(UTC)
            duration = int((completed - started).total_seconds() * 1000)
            call = call.model_copy(
                update={
                    "error": str(exc),
                    "duration_ms": duration,
                    "completed_at": completed,
                }
            )
            await _save_call(self.repo, call)
            raise
        await _save_call(self.repo, call)
        return result


def _extract_usage(result: ChatResult) -> dict[str, int | None]:
    """Pull token counts from the LLM response metadata."""
    if not result.generations:
        return {}
    gen = result.generations[0]
    msg = getattr(gen, "message", None)
    usage = getattr(msg, "usage_metadata", None) if msg else None
    if usage and isinstance(usage, dict):
        return {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        }
    return {}


async def _save_call(repo: LlmCallRepository, call: LlmCall) -> None:
    """Persist LLM call record, swallowing errors to not break pipelines."""
    try:
        await repo.create(call)
    except Exception as exc:
        logger.warning("llm_call_save_failed", error=str(exc))
