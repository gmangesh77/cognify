"""LLM-based retrieval query generation for article sections.

Generates 1-2 focused semantic search queries per outline section.
Single LLM call for all sections to avoid redundant queries.
"""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.agents.prompts import render_prompt
from src.models.content_pipeline import ArticleOutline, SectionQueries

logger = structlog.get_logger()

_MAX_RETRIES = 2


def _format_sections(outline: ArticleOutline) -> str:
    lines = []
    for s in outline.sections:
        points = ", ".join(s.key_points)
        lines.append(f"Section {s.index}: {s.title} — {s.description} (key: {points})")
    return "\n".join(lines)


def _build_user_message(outline: ArticleOutline) -> str:
    return render_prompt(
        "content_queries.user", sections_text=_format_sections(outline)
    )


async def generate_section_queries(
    outline: ArticleOutline,
    llm: BaseChatModel,
) -> list[SectionQueries]:
    """Generate retrieval queries for all outline sections."""
    messages = [
        SystemMessage(content=render_prompt("content_queries.system")),
        HumanMessage(content=_build_user_message(outline)),
    ]

    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            raw = response.content
            text = raw if isinstance(raw, str) else str(raw)
            from src.utils.llm_json import parse_llm_json

            data = parse_llm_json(text)
            result = [SectionQueries.model_validate(item) for item in data]
            logger.info(
                "section_queries_generated",
                section_count=len(result),
                total_queries=sum(len(sq.queries) for sq in result),
            )
            return result
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "query_generation_parse_failed",
                attempt=attempt + 1,
                error=str(exc),
            )

    msg = f"Failed to generate section queries after {_MAX_RETRIES} attempts"
    raise ValueError(msg)
