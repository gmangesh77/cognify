"""AUTHOR-012 — editing prompts (rewrite / tone presets / topic analyzer)."""

from __future__ import annotations

from src.agents.prompts import DEFAULT_PROMPTS, bind_prompt_overrides, render_prompt
from src.services.content.section_rewriter import TONE_PRESETS, expand_tone_preset
from src.services.topic_analyzer import TopicAnalyzer


class TestTonePresets:
    def test_presets_are_registry_defaults(self) -> None:
        for name, text in TONE_PRESETS.items():
            assert DEFAULT_PROMPTS[f"section_rewrite.tone.{name}"].template == text

    def test_expand_uses_override(self) -> None:
        with bind_prompt_overrides({"section_rewrite.tone.shorter": "Cut it."}):
            assert expand_tone_preset("shorter") == "Cut it."
        assert expand_tone_preset("shorter").startswith(
            "Make this paragraph noticeably shorter"
        )


class TestRewriterSystem:
    def test_registered_and_mentions_data_spec_id(self) -> None:
        assert "data-spec-id" in render_prompt("section_rewrite.system")


class TestTopicAnalyzer:
    def test_full_prompt_matches_legacy_literal(self) -> None:
        analyzer = TopicAnalyzer(llm=object())  # type: ignore[arg-type]
        out = analyzer._build_prompt("T", ["ai"], None, None)
        assert out.startswith(
            "Analyze this topic and suggest article metadata:\n\n"
            "Title: T\n\nAvailable domains: ['ai']\n"
        )
        assert '- "preferred_angle": suggested editorial angle' in out

    def test_regenerate_prompt_uses_override(self) -> None:
        from src.api.schemas.topic_analysis import TopicAnalysisResult

        current = TopicAnalysisResult(
            description="d",
            domain="x",
            keywords=[],
            target_audience="a",
            content_tone="neutral",
            preferred_angle="p",
        )
        analyzer = TopicAnalyzer(llm=object())  # type: ignore[arg-type]
        with bind_prompt_overrides(
            {"topic_analyze.regenerate": "R {field} {title} {current_json}"}
        ):
            out = analyzer._build_prompt("T", None, "domain", current)
        assert out.startswith("R domain T {")
