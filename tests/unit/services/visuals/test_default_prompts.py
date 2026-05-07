"""Tests for the per-role default prompt seeds (Phase 2 / VISUAL-005)."""

from __future__ import annotations

from src.models.visual import ImageRoleStyle
from src.services.visuals.default_prompts import (
    DEFAULT_SECTION_VISUAL_PROMPTS,
    default_prompt_for_role,
)

ALL_ROLES: tuple[str, ...] = (
    "hero",
    "feature_card",
    "concept",
    "process_step",
    "comparison_split",
    "quote_card",
    "stat_card",
    "screenshot_mock",
    "editorial",
    "background",
)


class TestDefaultSectionVisualPrompts:
    def test_every_role_has_a_seed(self) -> None:
        for role in ALL_ROLES:
            assert role in DEFAULT_SECTION_VISUAL_PROMPTS

    def test_each_seed_is_substantial(self) -> None:
        for role, seed in DEFAULT_SECTION_VISUAL_PROMPTS.items():
            assert len(seed) >= 30, f"{role} seed too short: {seed}"

    def test_seeds_describe_a_subject_not_a_style(self) -> None:
        # Style verbiage belongs in visual_styles.py, not the role seeds.
        # Role seeds describe *what* to render, not *how*.
        for seed in DEFAULT_SECTION_VISUAL_PROMPTS.values():
            assert "isometric" not in seed.lower()
            assert "dslr" not in seed.lower()

    def test_seeds_avoid_text_keywords(self) -> None:
        # Role seeds should not request text — that's owned by no_text_clause
        # in prompt_composer.py. Catching obvious leaks.
        for seed in DEFAULT_SECTION_VISUAL_PROMPTS.values():
            assert "label text" not in seed.lower()
            assert "speech bubble" not in seed.lower()


class TestDefaultPromptForRole:
    def test_returns_seed_for_known_role(self) -> None:
        seed = default_prompt_for_role("hero")
        assert seed == DEFAULT_SECTION_VISUAL_PROMPTS["hero"]

    def test_typing_accepts_image_role_style_literals(self) -> None:
        # Compile-time-ish: the literal should be accepted directly.
        role: ImageRoleStyle = "feature_card"
        assert default_prompt_for_role(role)

    def test_unknown_role_falls_back_to_hero(self) -> None:
        # Defensive behaviour — never crash the planner with KeyError.
        seed = default_prompt_for_role("not_a_real_role")  # type: ignore[arg-type]
        assert seed == DEFAULT_SECTION_VISUAL_PROMPTS["hero"]
