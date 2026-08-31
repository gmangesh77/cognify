"""SEO metadata and AI discoverability generation.

Generates platform-neutral SEO metadata and AI-optimised summaries/claims
from drafted article sections. Follows the same LLM calling pattern as
outline_generator.py and query_generator.py.
"""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.agents.prompts import render_prompt
from src.models.content import SEOMetadata, StructuredDataLD
from src.models.content_pipeline import (
    AIDiscoverabilityResult,
    CitationRef,
    SectionDraft,
)
from src.utils.llm_json import parse_llm_json

logger = structlog.get_logger()

AI_DISCLOSURE_TEXT = (
    "This article was generated with the assistance of artificial intelligence. "
    "All factual claims are supported by cited sources."
)

_MAX_RETRIES = 2


def _seo_messages(
    title: str, body_text: str, extras: str
) -> list[SystemMessage | HumanMessage]:
    return [
        SystemMessage(content=render_prompt("content_seo.system")),
        HumanMessage(
            content=render_prompt(
                "content_seo.user", title=title, body_excerpt=body_text[:2000]
            )
            + extras
        ),
    ]


async def _parse_seo_response(
    llm: BaseChatModel,
    messages: list[SystemMessage | HumanMessage],
) -> SEOMetadata:
    """Call LLM and parse response as SEOMetadata."""
    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = parse_llm_json(str(response.content))
            if isinstance(data, dict):
                if (
                    isinstance(data.get("description"), str)
                    and len(data["description"]) > 170
                ):
                    data["description"] = data["description"][:167] + "..."
                if isinstance(data.get("title"), str) and len(data["title"]) > 70:
                    data["title"] = data["title"][:67] + "..."
            return SEOMetadata.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "seo_parse_failed",
                attempt=attempt + 1,
                error=str(exc),
            )
    msg = f"Failed to generate SEO metadata after {_MAX_RETRIES} attempts"
    raise ValueError(msg)


def _maybe_truncate_summary(
    data: dict[str, object],
) -> dict[str, object]:
    """Truncate summary at sentence boundary if over 500 chars."""
    summary = str(data.get("summary", ""))
    if len(summary) <= 500:
        return data
    truncated = summary[:500]
    last_dot = truncated.rfind(".")
    if last_dot > 0:
        truncated = truncated[: last_dot + 1]
    data["summary"] = truncated
    return data


async def _parse_discoverability_response(
    llm: BaseChatModel,
    messages: list[SystemMessage | HumanMessage],
) -> AIDiscoverabilityResult:
    """Call LLM and parse response as AIDiscoverabilityResult."""
    for attempt in range(_MAX_RETRIES):
        response = await llm.ainvoke(messages)
        try:
            data = parse_llm_json(str(response.content))
            data = _maybe_truncate_summary(data)
            return AIDiscoverabilityResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "discoverability_parse_failed",
                attempt=attempt + 1,
                error=str(exc),
            )
    msg = f"Failed to generate discoverability after {_MAX_RETRIES} attempts"
    raise ValueError(msg)


async def generate_seo_metadata(
    article_title: str,
    body_text: str,
    llm: BaseChatModel,
    target_audience: str | None = None,
    seed_keywords: list[str] | None = None,
    content_tone: str | None = None,
) -> SEOMetadata:
    """Generate SEO metadata from article title and body."""
    logger.info("seo_metadata_generation_started", title=article_title)
    extras = ""
    if target_audience:
        extras += (
            f"\nTarget audience: {target_audience}. "
            "Optimize keywords for what this audience searches."
        )
    if seed_keywords:
        extras += (
            f"\nMust include these seed keywords in the keyword list: "
            f"{', '.join(seed_keywords)}."
        )
    if content_tone:
        extras += f"\nContent tone: {content_tone}."
    messages = _seo_messages(article_title, body_text, extras)
    return await _parse_seo_response(llm, messages)


def _format_sections(drafts: list[SectionDraft]) -> str:
    """Format section drafts for the LLM prompt."""
    lines = []
    for d in drafts:
        lines.append(f"## {d.title}\n{d.body_markdown[:500]}")
    return "\n\n".join(lines)


def _format_citations(citations: list[CitationRef]) -> str:
    """Format citation refs for the LLM prompt."""
    if not citations:
        return "None"
    return ", ".join(f"[{c.index}] {c.source_title}" for c in citations)


async def generate_ai_discoverability(
    drafts: list[SectionDraft],
    citations: list[CitationRef],
    llm: BaseChatModel,
) -> AIDiscoverabilityResult:
    """Generate AI discoverability summary and key claims."""
    logger.info("ai_discoverability_generation_started")
    messages: list[SystemMessage | HumanMessage] = [
        SystemMessage(content=render_prompt("content_discover.system")),
        HumanMessage(
            content=render_prompt(
                "content_discover.user",
                sections_text=_format_sections(drafts),
                citations_text=_format_citations(citations),
            )
        ),
    ]
    return await _parse_discoverability_response(llm, messages)


def build_structured_data(
    seo: SEOMetadata,
    article_title: str,
    generated_at: str,
) -> StructuredDataLD:
    """Build Schema.org JSON-LD structured data from SEO metadata."""
    return StructuredDataLD.model_validate(
        {
            "headline": article_title,
            "description": seo.description,
            "keywords": seo.keywords,
            "datePublished": generated_at,
            "dateModified": generated_at,
        }
    )
