"""TopicAnalyzer service — LLM-based topic metadata suggestion."""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.api.schemas.topic_analysis import (
    VALID_TONES,
    TopicAnalysisResult,
)
from src.models.brief import BriefCreate
from src.utils.llm_json import parse_llm_json

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You are an expert content strategist. Given a topic title, suggest "
    "metadata for article generation. Return valid JSON only."
)

_FULL_ANALYSIS_TEMPLATE = (
    "Analyze this topic and suggest article metadata:\n\n"
    "Title: {title}\n\n"
    "{domains_section}"
    "Return JSON with these fields:\n"
    '- "description": 1-2 sentence description of the topic\n'
    '- "domain": best-fit domain for this topic\n'
    '- "keywords": 3-5 keywords for research\n'
    '- "target_audience": who should read this article\n'
    '- "content_tone": one of {valid_tones}\n'
    '- "preferred_angle": suggested editorial angle'
)

_REGENERATE_TEMPLATE = (
    "Regenerate ONLY the '{field}' field for this topic.\n\n"
    "Title: {title}\n\n"
    "Current values (keep all except {field}):\n"
    "{current_json}\n\n"
    "Return the full JSON with only '{field}' changed."
)

_MAX_RETRIES = 2


def suggested_brief_from(title: str, result: TopicAnalysisResult) -> BriefCreate:
    """Prefill a Brief from LLM topic analysis (ADR-007 / AUTHOR-003)."""
    return BriefCreate(
        name=title[:200],
        title=title[:500],
        description=result.description[:4000],
        target_audience=result.target_audience[:500] or None,
        content_tone=(
            result.content_tone if result.content_tone in VALID_TONES else None
        ),
        preferred_angle=result.preferred_angle[:500] or None,
        keywords=result.keywords[:20],
    )


class TopicAnalyzer:
    """Analyze a topic title and suggest article metadata using an LLM."""

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def analyze(
        self,
        title: str,
        configured_domains: list[str] | None = None,
        regenerate_field: str | None = None,
        current_values: TopicAnalysisResult | None = None,
    ) -> TopicAnalysisResult:
        """Return LLM-suggested metadata for the given topic title."""
        logger.info(
            "topic_analysis_started",
            title=title,
            regenerate_field=regenerate_field,
        )
        user_msg = self._build_prompt(
            title, configured_domains, regenerate_field, current_values
        )
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]
        for attempt in range(_MAX_RETRIES):
            response = await self._llm.ainvoke(messages)
            try:
                data = parse_llm_json(str(response.content))
                result = TopicAnalysisResult.model_validate(data)
                return result.model_copy(
                    update={"suggested_brief": suggested_brief_from(title, result)}
                )
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning(
                    "topic_analysis_parse_failed",
                    attempt=attempt + 1,
                    error=str(exc),
                )
        msg = f"Failed to analyze topic after {_MAX_RETRIES} attempts"
        raise ValueError(msg)

    def _build_prompt(
        self,
        title: str,
        configured_domains: list[str] | None,
        regenerate_field: str | None,
        current_values: TopicAnalysisResult | None,
    ) -> str:
        if regenerate_field and current_values:
            return _REGENERATE_TEMPLATE.format(
                field=regenerate_field,
                title=title,
                current_json=current_values.model_dump_json(indent=2),
            )
        domains_section = ""
        if configured_domains:
            domains_section = (
                f"Available domains: {configured_domains}\n"
                "Prefer one of these domains if the topic fits.\n\n"
            )
        return _FULL_ANALYSIS_TEMPLATE.format(
            title=title,
            domains_section=domains_section,
            valid_tones=VALID_TONES,
        )
