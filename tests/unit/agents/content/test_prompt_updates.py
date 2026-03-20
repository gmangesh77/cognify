"""Tests for humanization style rules in generation prompts."""

from src.agents.content.outline_generator import _SYSTEM_PROMPT as OUTLINE_PROMPT
from src.agents.content.section_drafter import _SYSTEM_PROMPT as DRAFTER_PROMPT


class TestPromptStyleRules:
    def test_outline_prompt_has_em_dash_rule(self) -> None:
        prompt = OUTLINE_PROMPT.lower()
        assert "em-dash" in prompt or "em dash" in prompt

    def test_drafter_prompt_has_transition_rule(self) -> None:
        assert (
            "moreover" in DRAFTER_PROMPT.lower()
            or "formal transition" in DRAFTER_PROMPT.lower()
        )

    def test_drafter_prompt_has_buzzword_rule(self) -> None:
        assert "delve" in DRAFTER_PROMPT.lower() or "buzzword" in DRAFTER_PROMPT.lower()

    def test_drafter_prompt_has_tone_rule(self) -> None:
        assert (
            "conversational" in DRAFTER_PROMPT.lower()
            or "natural" in DRAFTER_PROMPT.lower()
        )
