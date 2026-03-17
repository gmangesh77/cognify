"""LLM-based completeness evaluation with heuristic guardrails.

Calls Claude Sonnet to judge whether research findings are sufficient.
Hard guardrails enforce max 2 rounds and flag zero-source facets.
"""

import json
from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.models.research import (
    EvaluationResult,
    FacetFindings,
    TopicInput,
)

logger = structlog.get_logger()

_MAX_ROUNDS = 2

_SYSTEM_PROMPT = (
    "You are a research completeness evaluator. Given a topic and "
    "research findings, determine if the findings are sufficient for "
    "a comprehensive article. Respond with valid JSON only."
)

_USER_TEMPLATE = (
    "Topic: {title} ({domain})\n\n"
    "Findings per facet:\n{findings_summary}\n\n"
    "Are these findings sufficient? Identify weak facets by index.\n"
    'Return JSON: {{"is_complete": bool, "weak_facets": [int], '
    '"reasoning": "..."}}'
)


def _summarize_findings(findings: list[FacetFindings]) -> str:
    lines = []
    for f in findings:
        lines.append(
            f"Facet {f.facet_index}: {len(f.sources)} sources, "
            f"{len(f.claims)} claims — {f.summary[:100]}"
        )
    return "\n".join(lines)


def _apply_guardrails(
    result: EvaluationResult,
    findings: list[FacetFindings],
    round_number: int,
) -> EvaluationResult:
    # Guardrail: force complete at max rounds
    if round_number >= _MAX_ROUNDS:
        return EvaluationResult(
            is_complete=True,
            weak_facets=[],
            reasoning=f"Forced complete at round {round_number}",
        )

    # Guardrail: zero-source facets are always weak
    zero_source = [f.facet_index for f in findings if len(f.sources) == 0]
    if zero_source:
        all_weak = list(set(result.weak_facets) | set(zero_source))
        return EvaluationResult(
            is_complete=False,
            weak_facets=all_weak,
            reasoning=result.reasoning,
        )

    return result


@dataclass(frozen=True)
class EvaluationContext:
    """Bundles evaluation inputs to respect 3-param limit."""

    topic: TopicInput
    findings: list[FacetFindings]
    round_number: int


async def evaluate_completeness(
    ctx: EvaluationContext, llm: BaseChatModel
) -> EvaluationResult:
    """Evaluate research completeness via LLM + guardrails."""
    user_msg = _USER_TEMPLATE.format(
        title=ctx.topic.title,
        domain=ctx.topic.domain,
        findings_summary=_summarize_findings(ctx.findings),
    )
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_msg)]
    response = await llm.ainvoke(messages)

    try:
        data = json.loads(response.content)
        result = EvaluationResult.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("evaluation_parse_failed", error=str(exc))
        result = EvaluationResult(
            is_complete=False,
            weak_facets=[],
            reasoning=f"Parse error: {exc}",
        )

    return _apply_guardrails(result, ctx.findings, ctx.round_number)
