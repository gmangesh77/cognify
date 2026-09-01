"""AUTHOR-010 — route each pipeline step to its own model.

`TieredChatModel` reads the step name the tracker already binds
(`src.utils.tracked_llm.current_step_name`) and delegates to the model
configured for it, falling back to `default`. Wrap it *inside*
`TrackedChatModel` so `llm_calls.model_name` (and the usage badge) reflect
the model that actually served the call.
"""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from pydantic import ConfigDict

from src.utils.tracked_llm import current_step_name

KNOWN_LLM_STEPS: frozenset[str] = frozenset(
    {
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
        "linkedin_repurpose",
    }
)


class TieredChatModel(BaseChatModel):
    """Delegates to `by_step[current_step]` when configured, else `default`."""

    model_config = ConfigDict(protected_namespaces=())

    default: BaseChatModel
    by_step: dict[str, BaseChatModel]

    @property
    def _llm_type(self) -> str:
        return "tiered"

    @property
    def model(self) -> str:
        """Model name of the model serving the current step (for tracking)."""
        return str(getattr(self.active(), "model", "unknown"))

    def active(self) -> BaseChatModel:
        return self.by_step.get(current_step_name.get(), self.default)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self.active()._generate(messages, stop, run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return await self.active()._agenerate(messages, stop, run_manager, **kwargs)


__all__ = ["KNOWN_LLM_STEPS", "TieredChatModel"]
