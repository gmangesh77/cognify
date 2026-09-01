"""TopicAnalyzer service — LLM-based topic metadata suggestion."""

import json

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.agents.prompts import render_prompt
from src.api.schemas.topic_analysis import (
    TopicAnalysisResult,
)
from src.models.brief import BriefCreate
from src.models.tones import VALID_TONES
from src.utils.llm_json import parse_llm_json

logger = structlog.get_logger()

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
            SystemMessage(content=render_prompt("topic_analyze.system")),
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
            return render_prompt(
                "topic_analyze.regenerate",
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
        return render_prompt(
            "topic_analyze.full",
            title=title,
            domains_section=domains_section,
            valid_tones=VALID_TONES,
        )
