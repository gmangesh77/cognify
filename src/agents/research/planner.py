"""LLM-based research plan generation.

Calls Claude Sonnet to decompose a topic into 3-5 research facets
with search queries per facet.
"""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.research import ResearchPlan, TopicInput

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You are a research planning assistant. Given a topic, generate a "
    "research plan with 3-5 facets. Each facet should cover a distinct "
    "angle of the topic. Respond with valid JSON only."
)

_USER_TEMPLATE = (
    "Plan research for this topic:\n"
    "Title: {title}\n"
    "Description: {description}\n"
    "Domain: {domain}\n\n"
    'Return JSON: {{"facets": [{{"index": 0, "title": "...", '
    '"description": "...", "search_queries": ["..."]}}], '
    '"reasoning": "..."}}'
)

_MAX_RETRIES = 2


async def generate_research_plan(topic: TopicInput, llm: BaseChatModel) -> ResearchPlan:
    """Generate a research plan from a topic via LLM."""
    user_msg = _USER_TEMPLATE.format(
        title=topic.title,
        description=topic.description,
        domain=topic.domain,
    )
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_msg)]

    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = json.loads(response.content)
            return ResearchPlan.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "plan_parse_failed",
                attempt=attempt + 1,
                error=str(exc),
            )

    msg = f"Failed to generate research plan after {_MAX_RETRIES} attempts"
    raise ValueError(msg)
