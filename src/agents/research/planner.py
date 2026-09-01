"""LLM-based research plan generation.

Calls Claude Sonnet to decompose a topic into 3-5 research facets
with search queries per facet.
"""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.agents.prompts import render_prompt
from src.models.research import ResearchPlan, TopicInput
from src.utils.llm_json import parse_llm_json

logger = structlog.get_logger()

_MAX_RETRIES = 2


def _build_context_block(topic: TopicInput) -> str:
    """Assemble audience/tone/angle/keywords hints for the planner."""
    lines: list[str] = []
    if topic.target_audience:
        lines.append(f"Target audience: {topic.target_audience}")
    if topic.content_tone:
        lines.append(f"Content tone: {topic.content_tone}")
    if topic.preferred_angle:
        lines.append(f"Editorial angle: {topic.preferred_angle}")
    if topic.keywords:
        lines.append(f"Key terms the research MUST cover: {', '.join(topic.keywords)}")
    if not lines:
        return ""
    return "Tailor research facets and search queries to this context:\n" + "\n".join(
        lines
    )


def _build_user_message(topic: TopicInput) -> str:
    return render_prompt(
        "plan_research.user",
        title=topic.title,
        description=topic.description,
        domain=topic.domain,
        context_block=_build_context_block(topic),
    )


async def generate_research_plan(topic: TopicInput, llm: BaseChatModel) -> ResearchPlan:
    """Generate a research plan from a topic via LLM."""
    messages = [
        SystemMessage(content=render_prompt("plan_research.system")),
        HumanMessage(content=_build_user_message(topic)),
    ]

    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = parse_llm_json(str(response.content))
            return ResearchPlan.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "plan_parse_failed",
                attempt=attempt + 1,
                error=str(exc),
                raw_content=str(response.content)[:200],
            )

    msg = f"Failed to generate research plan after {_MAX_RETRIES} attempts"
    raise ValueError(msg)
