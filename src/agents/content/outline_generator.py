"""LLM-based article outline generation.

Takes research findings and generates a structured 4-8 section outline
with narrative flow, target word counts, and key points per section.
Follows the same pattern as planner.py.
"""

import json
from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.content_pipeline import ArticleOutline
from src.models.research import FacetFindings, TopicInput
from src.utils.llm_json import parse_llm_json

logger = structlog.get_logger()


@dataclass(frozen=True)
class OutlineContext:
    """Optional editorial steering for outline generation.

    `instruction` carries a free-text editor note used when regenerating
    an outline (e.g. "make it punchier"); it is rendered as an extra
    context line in the outline prompt.
    """

    target_audience: str | None = None
    preferred_angle: str | None = None
    content_tone: str | None = None
    keywords: list[str] | None = None
    instruction: str | None = None


_SYSTEM_PROMPT = (
    "You are an expert content strategist. Generate a structured "
    "article outline from research findings. The outline should have "
    "4-8 sections with narrative flow: introduction, findings, "
    "analysis, and conclusion. "
    "Do not use em-dashes. Use periods or commas instead. "
    "Avoid formal transitions like moreover, furthermore, in conclusion. "
    "Write in a natural conversational tone. Vary sentence length. "
    "Be specific and concrete, not abstract. "
    "Respond with valid JSON only."
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


def _build_context_lines(ctx: OutlineContext) -> list[str]:
    """Render optional editorial context as prompt lines."""
    context_lines = []
    if ctx.target_audience:
        context_lines.append(f"Target audience: {ctx.target_audience}")
    if ctx.content_tone:
        context_lines.append(f"Tone: {ctx.content_tone}")
    if ctx.preferred_angle:
        context_lines.append(f"Editorial angle: {ctx.preferred_angle}")
    if ctx.keywords:
        context_lines.append(
            f"Key topics that must be covered: {', '.join(ctx.keywords)}"
        )
    if ctx.instruction:
        context_lines.append(
            f"Editor instructions for this revision: {ctx.instruction}"
        )
    return context_lines


async def generate_outline(
    topic: TopicInput,
    findings: list[FacetFindings],
    llm: BaseChatModel,
    ctx: OutlineContext | None = None,
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
    context_lines = _build_context_lines(ctx) if ctx is not None else []
    if context_lines:
        user_msg = user_msg.replace(
            "Requirements:\n",
            "\n".join(context_lines) + "\n\nRequirements:\n",
        )
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = parse_llm_json(str(response.content))
            return ArticleOutline.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "outline_parse_failed",
                attempt=attempt + 1,
                error=str(exc),
            )

    msg = f"Failed to generate outline after {_MAX_RETRIES} attempts"
    raise ValueError(msg)
