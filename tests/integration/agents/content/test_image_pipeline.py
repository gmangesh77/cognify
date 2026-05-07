"""Integration test — planner + render LangGraph mini-pipeline.

Exercises the Phase 2 / VISUAL-005 contract end-to-end:

1. The planner node calls Claude (FakeListChatModel) with a fixture-shaped
   response and emits ImageSpecs into state.
2. The render node fans those specs out via a registry containing a
   single StubImageProvider, persists bytes to a real LocalDisk
   directory, and emits ImageAssets with `spec_id` linking back to the
   plan.
3. Every rendered ImageAsset's `metadata.spec_id` matches one of the
   planned `ImageSpec.id`s — the boundary invariant the planner+render
   pair owes the rest of the system.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, NotRequired, TypedDict
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.graph import END, StateGraph

from src.agents.content.image_planner_node import make_image_planner_node
from src.agents.content.image_render_node import make_image_render_node
from src.models.content import ImageAsset, Provenance, SEOMetadata
from src.models.content_pipeline import (
    ArticleOutline,
    OutlineSection,
    SectionDraft,
    SEOResult,
)
from src.models.research import TopicInput
from src.services.visuals.object_storage import LocalDiskObjectStorage
from src.services.visuals.registry import ImageProviderRegistry
from tests.fixtures.visual_planner.planner_responses import (
    COVER_HERO_GENERAL_JSON,
    CTO_DEEP_DIVE_JSON,
)
from tests.stubs.stub_image_provider import StubImageProvider


class _State(TypedDict):
    topic: Any
    outline: NotRequired[Any]
    section_drafts: list[Any]
    seo_result: NotRequired[Any]
    session_id: UUID
    audience_persona: NotRequired[str | None]
    page_art_direction: NotRequired[str | None]
    target_audience: NotRequired[str | None]
    visuals: list[Any]
    image_specs: NotRequired[list[Any]]


def _topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="The quiet refactor",
        description="Steady cleanups outperform big rewrites.",
        domain="engineering",
    )


def _section(idx: int) -> SectionDraft:
    return SectionDraft(
        section_index=idx,
        title=f"Section {idx}",
        body_markdown="A first paragraph.\n\nA second paragraph.",
        word_count=10,
        citations_used=[],
    )


def _outline() -> ArticleOutline:
    return ArticleOutline(
        title="The quiet refactor",
        subtitle=None,
        content_type="article",
        sections=[
            OutlineSection(
                index=0,
                title="Why it matters",
                description="The case for steady cleanups.",
                key_points=["Steady > heroic"],
                target_word_count=300,
                relevant_facets=[0],
            ),
        ],
        total_target_words=300,
        reasoning="Article structure.",
    )


def _seo_result() -> SEOResult:
    return SEOResult(
        seo=SEOMetadata(title="Quiet refactor", description="Wins via small steps."),
        summary="Small steps compound.",
        key_claims=["Small steps compound."],
        provenance=Provenance(
            research_session_id=uuid4(),
            primary_model="claude-opus-4",
            drafting_model="claude-sonnet-4",
            embedding_model="all-MiniLM-L6-v2",
            embedding_version="1.0.0",
        ),
        ai_disclosure="Generated with AI.",
    )


def _build_graph(
    *,
    llm: FakeListChatModel,
    storage: LocalDiskObjectStorage,
    registry: ImageProviderRegistry,
) -> object:
    graph = StateGraph(_State)
    graph.add_node(
        "image_planner",
        make_image_planner_node(llm, enabled=True, max_images_per_section=4),
    )
    graph.add_node(
        "image_render",
        make_image_render_node(
            registry=registry,
            storage=storage,
            default_provider="gemini_flash",
            concurrency=2,
        ),
    )
    graph.set_entry_point("image_planner")
    graph.add_edge("image_planner", "image_render")
    graph.add_edge("image_render", END)
    return graph.compile()


@pytest.mark.asyncio
class TestImagePipelineIntegration:
    async def test_planner_and_render_flow_produces_aligned_visuals(self) -> None:
        # Two LLM responses: one for the cover, one for the section.
        llm = FakeListChatModel(responses=[COVER_HERO_GENERAL_JSON, CTO_DEEP_DIVE_JSON])
        registry = ImageProviderRegistry()
        registry.register(StubImageProvider())

        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            compiled = _build_graph(llm=llm, storage=storage, registry=registry)

            initial_state: dict[str, object] = {
                "topic": _topic(),
                "outline": _outline(),
                "section_drafts": [_section(0)],
                "seo_result": _seo_result(),
                "session_id": uuid4(),
                "audience_persona": "general_business",
                "page_art_direction": "warm slate, morning light",
                "visuals": [],
            }
            final_state = await compiled.ainvoke(initial_state)

            specs = final_state.get("image_specs") or []
            visuals = final_state.get("visuals") or []
            assert specs, "planner must emit at least one spec"
            assert visuals, "render must emit at least one visual"

            # Every rendered visual has spec_id linking to a planned spec.
            spec_ids = {s.id for s in specs}
            for asset in visuals:
                assert isinstance(asset, ImageAsset)
                spec_id = asset.metadata.get("spec_id")
                assert spec_id in spec_ids, (
                    f"Visual {asset.url} carries spec_id {spec_id!r} which is "
                    f"not in planner output {spec_ids}"
                )
                # Bytes were actually written to the local disk dir.
                assert Path(asset.url).exists()

            # 1 cover + 2 deep-dive specs (from fixtures).
            assert len(specs) == 3
            assert specs[0].placement.anchor == "cover"
            assert specs[0].placement.section_index == -1
            assert specs[1].placement.section_index == 0
            assert specs[2].placement.section_index == 0

            # Render emitted one asset per spec (stub never fails).
            assert len(visuals) == 3

            # Metadata extension carries the full §4.2 field set.
            for asset in visuals:
                for key in (
                    "spec_id",
                    "role_style",
                    "visual_style",
                    "aspect_ratio",
                    "placement_anchor",
                    "provider",
                    "model",
                    "prompt_used",
                    "cost_usd",
                    "generation_ms",
                ):
                    assert key in asset.metadata, f"missing {key}"

    async def test_disabled_planner_leaves_visuals_untouched(self) -> None:
        llm = FakeListChatModel(responses=["never used"])
        registry = ImageProviderRegistry()
        registry.register(StubImageProvider())

        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalDiskObjectStorage(tmp)
            # Build a graph where the planner is disabled.
            graph = StateGraph(_State)
            graph.add_node(
                "image_planner",
                make_image_planner_node(llm, enabled=False),
            )
            graph.add_node(
                "image_render",
                make_image_render_node(
                    registry=registry,
                    storage=storage,
                    default_provider="gemini_flash",
                    concurrency=1,
                ),
            )
            graph.set_entry_point("image_planner")
            graph.add_edge("image_planner", "image_render")
            graph.add_edge("image_render", END)
            compiled = graph.compile()

            # The seed state contains no specs (planner never wrote them).
            initial: dict[str, object] = {
                "topic": _topic(),
                "section_drafts": [_section(0)],
                "session_id": uuid4(),
                "visuals": [],
            }
            final = await compiled.ainvoke(initial)
            # Render returns its existing (empty) visuals untouched.
            assert final.get("visuals") == []
            # Planner never set image_specs.
            assert "image_specs" not in final or not final["image_specs"]
