"""AUTHOR-012 — research prompts render byte-identically via the registry."""

from __future__ import annotations

from src.agents.prompts import DEFAULT_PROMPTS, bind_prompt_overrides, render_prompt


class TestGoldens:
    def test_plan_user_matches_legacy_literal(self) -> None:
        out = render_prompt(
            "plan_research.user",
            title="T",
            description="D",
            domain="X",
            context_block="CB",
        )
        assert out.startswith(
            "Plan research for this topic:\nTitle: T\nDescription: D\nDomain: X\nCB\n"
        )
        assert out.endswith('"source_type": "web|academic|both"}], "reasoning": "..."}')

    def test_evaluate_user_matches_legacy_literal(self) -> None:
        out = render_prompt(
            "evaluate_completeness.user", title="T", domain="X", findings_summary="F"
        )
        assert out == (
            "Topic: T (X)\n\nFindings per facet:\nF\n\n"
            "Are these findings sufficient? Identify weak facets by index.\n"
            'Return JSON: {"is_complete": bool, "weak_facets": [int], '
            '"reasoning": "..."}'
        )

    def test_web_claims_user_matches_legacy_literal(self) -> None:
        out = render_prompt("research_web_claims.user", title="T", snippets="S")
        assert out == (
            "Search results about 'T':\n\nS\n\n"
            "Extract 3-5 key factual claims and a 2-3 sentence summary.\n"
            'Return JSON: {"claims": ["..."], "summary": "..."}'
        )

    def test_literature_claims_user_matches_legacy_literal(self) -> None:
        out = render_prompt("research_literature_claims.user", title="T", abstracts="A")
        assert out == (
            "Paper abstracts about 'T':\n\nA\n\n"
            "Extract 3-5 key factual claims (cite as Author et al. (year)) "
            "and a 2-3 sentence summary of research contributions.\n"
            'Return JSON: {"claims": ["..."], "summary": "..."}'
        )

    def test_systems_registered(self) -> None:
        assert (
            "research planning assistant"
            in DEFAULT_PROMPTS["plan_research.system"].template
        )
        assert (
            "completeness evaluator"
            in DEFAULT_PROMPTS["evaluate_completeness.system"].template
        )
        assert (
            "search results" in DEFAULT_PROMPTS["research_web_claims.system"].template
        )
        assert (
            "paper abstracts"
            in DEFAULT_PROMPTS["research_literature_claims.system"].template
        )


class TestOverrideReachesPlanner:
    def test_planner_user_message_uses_override(self) -> None:
        from uuid import uuid4

        from src.agents.research.planner import _build_user_message
        from src.models.research import TopicInput

        topic = TopicInput(id=uuid4(), title="T", description="D", domain="X")
        with bind_prompt_overrides({"plan_research.user": "OVR {title}"}):
            assert _build_user_message(topic) == "OVR T"
