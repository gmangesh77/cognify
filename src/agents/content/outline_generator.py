"""LLM-based article outline generation.

Takes research findings and generates a structured 4-8 section outline
with narrative flow, target word counts, and key points per section.
Follows the same pattern as planner.py.
"""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.content_pipeline import ArticleOutline
from src.models.research import FacetFindings, TopicInput

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You are an expert content strategist. Generate a structured "
    "article outline from research findings. The outline should have "
    "4-8 sections with narrative flow: introduction, findings, "
    "analysis, and conclusion. Respond with valid JSON only."
)

_USER_TEMPLATE = (
    "Generate an article outline for this topic:\n\n"
    "Title: {title}\n"
    "Description: {description}\n"
    "Domain: {domain}\n\n"
    "Research findings:\n{findings_summary}\n\n"
    "Requirements:\n"
    "- 4-8 sections ordered for narrative flow\n"
    "- Each section: 200-500 target words\n"
    "- Total: 1500-3000 words\n"
    "- Map each section to relevant facet indices\n\n"
    "Return JSON: {schema_hint}"
)

_SCHEMA_HINT = (
    '{{"title": "...", "subtitle": "...", "content_type": "article", '
    '"sections": [{{"index": 0, "title": "...", "description": "...", '
    '"key_points": ["..."], "target_word_count": 300, '
    '"relevant_facets": [0]}}], '
    '"total_target_words": 1500, "reasoning": "..."}}'
)

_MAX_RETRIES = 2


def _summarize_findings(findings: list[FacetFindings]) -> str:
    """Build a concise summary of findings for the LLM prompt."""
    lines = []
    for f in findings:
        lines.append(
            f"Facet {f.facet_index}: {f.summary} "
            f"({len(f.sources)} sources, {len(f.claims)} claims)"
        )
    return "\n".join(lines)


async def generate_outline(
    topic: TopicInput,
    findings: list[FacetFindings],
    llm: BaseChatModel,
) -> ArticleOutline:
    """Generate an article outline from topic and findings."""
    logger.info("outline_generation_started", topic_title=topic.title)
    user_msg = _USER_TEMPLATE.format(
        title=topic.title,
        description=topic.description,
        domain=topic.domain,
        findings_summary=_summarize_findings(findings),
        schema_hint=_SCHEMA_HINT,
    )
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = json.loads(str(response.content))
            return ArticleOutline.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "outline_parse_failed",
                attempt=attempt + 1,
                error=str(exc),
            )

    msg = f"Failed to generate outline after {_MAX_RETRIES} attempts"
    raise ValueError(msg)
