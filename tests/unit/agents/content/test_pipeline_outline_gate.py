"""Graph span: stop_after_outline ends after queries.

Also verifies outline-in-state skips outline node.
"""

import json
from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.pipeline import ContentGraphDeps, build_content_graph
from tests.unit.agents.content.test_pipeline import (  # reuse existing helpers
    _make_findings,
    _make_topic,
    _outline_json,
)


def _queries_json() -> str:
    return json.dumps([{"section_index": 0, "queries": ["q1"]}])


def _state(**extra):  # type: ignore[no-untyped-def]
    base = {
        "topic": _make_topic(),
        "research_plan": None,
        "findings": _make_findings(),
        "session_id": uuid4(),
        "outline": None,
        "status": "outline_generating",
        "error": None,
        "target_audience": None,
        "content_tone": None,
        "preferred_angle": None,
        "keywords": None,
        "image_specs": [],
    }
    base.update(extra)
    return base


async def test_stop_after_outline_runs_outline_and_queries_only() -> None:
    llm = FakeListChatModel(responses=[_outline_json(), _queries_json()])
    graph = build_content_graph(llm, deps=ContentGraphDeps(stop_after_outline=True))
    result = await graph.ainvoke(_state())
    assert result["outline"] is not None
    assert result.get("section_queries")
    assert not result.get("section_drafts")


async def test_outline_in_state_skips_outline_generation() -> None:
    from src.models.content_pipeline import ArticleOutline

    outline = ArticleOutline.model_validate(json.loads(_outline_json()))
    # First fake response must be consumed by the QUERIES node, not the outline node.
    llm = FakeListChatModel(responses=[_queries_json()] + ["x"] * 12)
    graph = build_content_graph(llm, deps=ContentGraphDeps(stop_after_outline=True))
    result = await graph.ainvoke(_state(outline=outline, status="outline_complete"))
    assert result["outline"].title == outline.title
    assert result.get("section_queries")


async def test_node_sets_identical_across_spans() -> None:
    llm = FakeListChatModel(responses=["x"])
    full = build_content_graph(llm)
    half = build_content_graph(llm, deps=ContentGraphDeps(stop_after_outline=True))
    assert set(full.get_graph().nodes) == set(half.get_graph().nodes)
