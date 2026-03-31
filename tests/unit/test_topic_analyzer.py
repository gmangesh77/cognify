"""Unit tests for TopicAnalyzer service."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.schemas.topic_analysis import TopicAnalysisResult
from src.services.topic_analyzer import TopicAnalyzer

_VALID_RESULT = {
    "description": "An overview of AI safety research.",
    "domain": "AI / ML",
    "keywords": ["AI safety", "alignment", "LLM"],
    "target_audience": "ML engineers and researchers",
    "content_tone": "technical-authoritative",
    "preferred_angle": "Current state of AI alignment research",
}


def _make_llm(response_json: dict) -> MagicMock:
    llm = MagicMock()
    message = MagicMock()
    message.content = json.dumps(response_json)
    llm.ainvoke = AsyncMock(return_value=message)
    return llm


@pytest.mark.asyncio
async def test_analyze_topic_returns_all_fields() -> None:
    """Full analysis should return a TopicAnalysisResult with all 6 fields."""
    llm = _make_llm(_VALID_RESULT)
    analyzer = TopicAnalyzer(llm=llm)

    result = await analyzer.analyze(title="AI Safety Research in 2026")

    assert isinstance(result, TopicAnalysisResult)
    assert result.description == _VALID_RESULT["description"]
    assert result.domain == _VALID_RESULT["domain"]
    assert result.keywords == _VALID_RESULT["keywords"]
    assert result.target_audience == _VALID_RESULT["target_audience"]
    assert result.content_tone == _VALID_RESULT["content_tone"]
    assert result.preferred_angle == _VALID_RESULT["preferred_angle"]


@pytest.mark.asyncio
async def test_analyze_topic_with_configured_domains() -> None:
    """Configured domains should appear in the prompt sent to the LLM."""
    llm = _make_llm(_VALID_RESULT)
    analyzer = TopicAnalyzer(llm=llm)
    domains = ["AI / ML", "Cybersecurity", "Cloud"]

    await analyzer.analyze(title="Zero-trust networking", configured_domains=domains)

    call_args = llm.ainvoke.call_args
    messages = call_args[0][0]
    human_message_content = messages[1].content
    assert "AI / ML" in human_message_content
    assert "Cybersecurity" in human_message_content


@pytest.mark.asyncio
async def test_analyze_regenerate_single_field() -> None:
    """regenerate_field should appear in the prompt and keep other fields."""
    current = TopicAnalysisResult(**_VALID_RESULT)
    updated = {**_VALID_RESULT, "preferred_angle": "A new angle entirely"}
    llm = _make_llm(updated)
    analyzer = TopicAnalyzer(llm=llm)

    result = await analyzer.analyze(
        title="AI Safety Research in 2026",
        regenerate_field="preferred_angle",
        current_values=current,
    )

    call_args = llm.ainvoke.call_args
    messages = call_args[0][0]
    human_message_content = messages[1].content
    assert "preferred_angle" in human_message_content
    assert result.preferred_angle == "A new angle entirely"
