"""AUTHOR-012 — content-pipeline prompts render byte-identically via the registry."""

from __future__ import annotations

from src.agents.content import (
    chart_generator,
    diagram_generator,
    outline_generator,
    query_generator,
    section_prompt,
    seo_optimizer,
)
from src.agents.prompts import DEFAULT_PROMPTS, bind_prompt_overrides, render_prompt


class TestGoldens:
    def test_outline_system_is_registry_default(self) -> None:
        assert (
            DEFAULT_PROMPTS["content_outline.system"].template
            == outline_generator._SYSTEM_PROMPT
        )
        assert "Respond with valid JSON only." in outline_generator._SYSTEM_PROMPT

    def test_outline_user_renders_all_slots(self) -> None:
        out = render_prompt(
            "content_outline.user",
            title="T",
            description="D",
            domain="X",
            findings_summary="F",
            requirements="R",
            schema_hint="S",
        )
        assert out == (
            "Generate an article outline for this topic:\n\n"
            "Title: T\nDescription: D\nDomain: X\n\n"
            "Research findings:\nF\n\nR\nReturn JSON: S"
        )

    def test_queries_user_matches_legacy_literal(self) -> None:
        out = render_prompt("content_queries.user", sections_text="SEC")
        assert out == (
            "Generate retrieval queries for each section:\n\nSEC\n\n"
            'Return JSON array: [{"section_index": 0, "queries": ["query1", "query2"]}]'
        )

    def test_draft_system_keeps_word_target_slot(self) -> None:
        assert (
            DEFAULT_PROMPTS["content_draft.system"].template
            == section_prompt.SYSTEM_PROMPT
        )
        assert "approximately 300 words" in render_prompt(
            "content_draft.system", target_word_count=300
        )

    def test_seo_user_matches_legacy_literal(self) -> None:
        out = render_prompt("content_seo.user", title="T", body_excerpt="B")
        assert out == (
            "Generate SEO metadata for this article:\n\nTitle: T\nBody (excerpt): B\n\n"
            "Requirements: title 50-60 chars, description 150-160 chars, "
            "5-10 keywords. Return JSON only."
        )

    def test_seo_system_keeps_literal_json_braces(self) -> None:
        out = render_prompt("content_seo.system")
        assert '{"title": "50-60 char", "description": "150-160 char", ' in out

    def test_discover_user_matches_legacy_literal(self) -> None:
        out = render_prompt(
            "content_discover.user", sections_text="S", citations_text="C"
        )
        assert out == (
            "Extract summary and key claims from this article:\n\nS\n\n"
            "Citations available: C\nReturn JSON only."
        )

    def test_charts_and_diagrams_prompts_end_with_sections(self) -> None:
        assert render_prompt("content_charts.prompt", sections_text="SS").endswith(
            "## Article Sections\nSS"
        )
        assert render_prompt("content_diagrams.prompt", sections_text="SS").endswith(
            "## Article Sections\nSS"
        )
        assert (
            "propose 0-3 data charts"
            in DEFAULT_PROMPTS["content_charts.prompt"].template
        )
        assert (
            "Do not exceed 5 total."
            in DEFAULT_PROMPTS["content_diagrams.prompt"].template
        )

    def test_humanize_system_registered(self) -> None:
        assert "<<<BLOCK>>>" in DEFAULT_PROMPTS["content_humanize.system"].template


class TestOverridesReachCallSites:
    def test_query_generator_uses_override(self) -> None:
        # The module must call the registry at call time, not cache at import.
        from src.models.content_pipeline import ArticleOutline, OutlineSection

        outline = ArticleOutline(
            title="t",
            subtitle="s",
            content_type="article",
            sections=[
                OutlineSection(
                    index=0,
                    title="A",
                    description="d",
                    key_points=["k"],
                    target_word_count=100,
                    relevant_facets=[0],
                )
            ],
            total_target_words=100,
            reasoning="r",
        )
        with bind_prompt_overrides({"content_queries.user": "OVR {sections_text}"}):
            msg = query_generator._build_user_message(outline)
        assert msg.startswith("OVR Section 0: A")

    def test_chart_prompt_uses_override(self) -> None:
        with bind_prompt_overrides({"content_charts.prompt": "C {sections_text}"}):
            assert chart_generator._build_prompt([]) == "C "

    def test_diagram_prompt_uses_override(self) -> None:
        with bind_prompt_overrides({"content_diagrams.prompt": "D {sections_text}"}):
            assert diagram_generator._build_prompt([]) == "D "

    def test_seo_messages_use_override(self) -> None:
        with bind_prompt_overrides({"content_seo.system": "SYS-OVR"}):
            messages = seo_optimizer._seo_messages("T", "B", "")
        assert messages[0].content == "SYS-OVR"
