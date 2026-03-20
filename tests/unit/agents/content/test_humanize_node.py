"""Tests for the humanize pipeline node."""

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.humanize_node import make_humanize_node
from src.models.content_pipeline import CitationRef, SectionDraft


def _make_drafts() -> list[SectionDraft]:
    return [
        SectionDraft(
            section_index=0,
            title="Clean Section",
            body_markdown="Security researchers found a 40% increase in breaches [1]. The team responded quickly.",
            word_count=12,
            citations_used=[CitationRef(index=1, source_url="https://a.com", source_title="A")],
        ),
        SectionDraft(
            section_index=1,
            title="Sloppy Section",
            body_markdown="Let me delve into this transformative journey. Moreover, leveraging cutting-edge solutions is crucial [1]. Furthermore, this holistic approach empowers stakeholders. Indeed, it is important to note that this unprecedented paradigm shift will revolutionize the dynamic landscape.",
            word_count=38,
            citations_used=[CitationRef(index=1, source_url="https://a.com", source_title="A")],
        ),
    ]


class TestHumanizeNode:
    async def test_rewrites_low_scoring_sections(self) -> None:
        llm = FakeListChatModel(responses=[
            "This approach focuses on practical solutions [1]. The team found concrete improvements."
        ])
        node = make_humanize_node(llm)
        state = {"section_drafts": _make_drafts(), "status": "draft_complete"}
        result = await node(state)
        drafts = result["section_drafts"]
        assert len(drafts) == 2
        # Sloppy section should have been modified (either rewritten or mechanically fixed)
        assert drafts[1].body_markdown != _make_drafts()[1].body_markdown

    async def test_never_returns_failed_status(self) -> None:
        llm = FakeListChatModel(responses=[])  # will error if called
        node = make_humanize_node(llm)
        # Use clean sections that won't trigger rewrite (score > 70)
        clean_drafts = [
            SectionDraft(
                section_index=0, title="Clean",
                body_markdown="Security researchers found a 40% increase in breaches. The team tested three different approaches over six months.",
                word_count=18,
                citations_used=[],
            ),
        ]
        state = {"section_drafts": clean_drafts, "status": "draft_complete"}
        result = await node(state)
        assert result.get("status") != "failed"
        assert "section_drafts" in result

    async def test_mechanical_fixes_applied_to_all(self) -> None:
        drafts = [
            SectionDraft(
                section_index=0, title="Dash Section",
                body_markdown="The results \u2014 which were good \u2014 improved.",
                word_count=7,
                citations_used=[],
            ),
        ]
        llm = FakeListChatModel(responses=[])
        node = make_humanize_node(llm)
        state = {"section_drafts": drafts, "status": "draft_complete"}
        result = await node(state)
        assert "\u2014" not in result["section_drafts"][0].body_markdown

    async def test_skips_on_failed_status(self) -> None:
        """If pipeline already failed, humanize returns drafts unchanged."""
        llm = FakeListChatModel(responses=[])
        node = make_humanize_node(llm)
        original_drafts = _make_drafts()
        state = {"section_drafts": original_drafts, "status": "failed"}
        result = await node(state)
        # Should return original drafts without modification
        assert result["section_drafts"] == original_drafts
