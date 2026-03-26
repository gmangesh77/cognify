"""Tests for shared anti-AI style prompt constants."""

from src.agents.content.style_prompts import (
    ANTI_SLOP_RULES,
    STYLE_EXAMPLES,
    TONE_INSTRUCTIONS,
)


class TestStylePrompts:
    def test_tone_instructions_non_empty(self) -> None:
        assert len(TONE_INSTRUCTIONS) > 50

    def test_anti_slop_rules_covers_all_categories(self) -> None:
        for category in [
            "Buzzwords", "Transitions", "Hedges", "Overblown",
            "Corporate", "Fluff", "Meta", "AI openers",
        ]:
            assert category.lower() in ANTI_SLOP_RULES.lower(), (
                f"Missing category: {category}"
            )

    def test_style_examples_has_before_after(self) -> None:
        assert "BAD:" in STYLE_EXAMPLES
        assert "GOOD:" in STYLE_EXAMPLES

    def test_anti_slop_rules_includes_top_offenders(self) -> None:
        for phrase in ["delve", "leverage", "moreover", "furthermore"]:
            assert phrase in ANTI_SLOP_RULES.lower()
