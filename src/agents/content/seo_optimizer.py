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

from src.models.content import SEOMetadata, StructuredDataLD
from src.utils.llm_json import parse_llm_json
from src.models.content_pipeline import (
    AIDiscoverabilityResult,
    CitationRef,
    SectionDraft,
)

logger = structlog.get_logger()

AI_DISCLOSURE_TEXT = (
    "This article was generated with the assistance of artificial intelligence. "
    "All factual claims are supported by cited sources."
)

_MAX_RETRIES = 2

_SEO_SYSTEM = (
    "You are an SEO specialist. Generate SEO metadata for an article. "
    "Respond with valid JSON only: "
    '{"title": "50-60 char", "description": "150-160 char", '
    '"keywords": ["keyword1", "keyword2"]}'
)

_SEO_USER = (
    "Generate SEO metadata for this article:\n\n"
    "Title: {title}\n"
    "Body (excerpt): {body_excerpt}\n\n"
    "Requirements: title 50-60 chars, description 150-160 chars, "
    "5-10 keywords. Return JSON only."
)

_DISCOVER_SYSTEM = (
    "You are a content analyst. Extract a concise summary (1-2 sentences, "
    "under 500 chars) and 3-5 key factual claims with citation references. "
    "Respond with valid JSON only: "
    '{"summary": "...", "key_claims": ["claim [1]", "claim [2]"]}'
)

_DISCOVER_USER = (
    "Extract summary and key claims from this article:\n\n"
    "{sections_text}\n\n"
    "Citations available: {citations_text}\n"
    "Return JSON only."
)


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
                if isinstance(data.get("description"), str) and len(data["description"]) > 170:
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
) -> SEOMetadata:
    """Generate SEO metadata from article title and body."""
    logger.info("seo_metadata_generation_started", title=article_title)
    messages: list[SystemMessage | HumanMessage] = [
        SystemMessage(content=_SEO_SYSTEM),
        HumanMessage(
            content=_SEO_USER.format(
                title=article_title,
                body_excerpt=body_text[:2000],
            )
        ),
    ]
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
        SystemMessage(content=_DISCOVER_SYSTEM),
        HumanMessage(
            content=_DISCOVER_USER.format(
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
