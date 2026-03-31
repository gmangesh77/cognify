"""Tests for the topic analysis endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.schemas.topic_analysis import AnalyzeTopicRequest, TopicAnalysisResult

_SENTINEL = object()


def _make_mock_request(
    *,
    drafting_llm: object = _SENTINEL,
    domain_config_repo: object = None,
) -> MagicMock:
    """Build a minimal mock that satisfies the analyze_topic function."""
    mock_request = MagicMock()
    mock_request.app.state.drafting_llm = (
        MagicMock() if drafting_llm is _SENTINEL else drafting_llm
    )
    mock_request.app.state.domain_config_repo = domain_config_repo
    return mock_request


@pytest.mark.asyncio
async def test_analyze_topic_endpoint() -> None:
    """POST /topics/analyze returns analysis result."""
    mock_result = TopicAnalysisResult(
        description="desc",
        domain="cybersecurity",
        keywords=["zero trust"],
        target_audience="Engineers",
        content_tone="technical-authoritative",
        preferred_angle="Guide",
    )

    with patch("src.api.routers.topics.TopicAnalyzer") as MockAnalyzer:
        instance = AsyncMock()
        instance.analyze.return_value = mock_result
        MockAnalyzer.return_value = instance

        from src.api.routers.topics import analyze_topic

        # Use __wrapped__ to bypass the @limiter.limit decorator
        inner = analyze_topic.__wrapped__  # type: ignore[attr-defined]
        result = await inner(
            request=_make_mock_request(),
            body=AnalyzeTopicRequest(title="Zero Trust Architecture"),
            user=MagicMock(),
        )

    assert result.domain == "cybersecurity"
    assert result.target_audience == "Engineers"


@pytest.mark.asyncio
async def test_analyze_topic_requires_llm() -> None:
    """POST /topics/analyze raises ServiceUnavailableError when LLM not configured."""
    from src.api.errors import ServiceUnavailableError
    from src.api.routers.topics import analyze_topic

    inner = analyze_topic.__wrapped__  # type: ignore[attr-defined]

    with pytest.raises(ServiceUnavailableError):
        await inner(
            request=_make_mock_request(drafting_llm=None),
            body=AnalyzeTopicRequest(title="Zero Trust Architecture"),
            user=MagicMock(),
        )


@pytest.mark.asyncio
async def test_analyze_topic_calls_analyzer_with_title() -> None:
    """TopicAnalyzer.analyze is invoked with the request title."""
    mock_result = TopicAnalysisResult(
        description="desc",
        domain="tech",
        keywords=[],
        target_audience="Devs",
        content_tone="conversational",
        preferred_angle="News",
    )

    with patch("src.api.routers.topics.TopicAnalyzer") as MockAnalyzer:
        instance = AsyncMock()
        instance.analyze.return_value = mock_result
        MockAnalyzer.return_value = instance

        from src.api.routers.topics import analyze_topic

        inner = analyze_topic.__wrapped__  # type: ignore[attr-defined]
        await inner(
            request=_make_mock_request(),
            body=AnalyzeTopicRequest(title="My Custom Topic"),
            user=MagicMock(),
        )

        instance.analyze.assert_called_once()
        call_kwargs = instance.analyze.call_args.kwargs
        assert call_kwargs["title"] == "My Custom Topic"
