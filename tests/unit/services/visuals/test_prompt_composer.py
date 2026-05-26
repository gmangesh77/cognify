"""Tests for the persona-aware prompt composer (Phase 2 / VISUAL-005).

The composer is the four-branch decision tree from impactai's
`_build_banner_prompt`:

1. prompt_override + has_style    → "Composition reference IGNORED" framing
2. prompt_override + no_style     → prompt_override only + no_text_clause
3. no_prompt_override + has_style → style fragment + spec subject + no_text_clause
4. no_prompt_override + no_style  → spec subject + no_text_clause

For Gemini Flash (which ignores the aspect param), an aspect_instruction
sentence is appended.
"""

from __future__ import annotations

from src.models.visual import ImagePlacement, ImageSpec
from src.services.visuals.prompt_composer import (
    LABELED_DIAGRAM_CLAUSE,
    LABELED_ROLE_STYLES,
    NO_TEXT_CLAUSE,
    aspect_instruction,
    build_prompt,
    rendering_clause_for_role,
)


def _spec(**overrides: object) -> ImageSpec:
    base: dict[str, object] = {
        "id": "spec_1",
        "role_style": "hero",
        "visual_style": None,
        "prompt": "A founder reviewing dashboards in a sunlit office.",
        "aspect_ratio": "16:9",
        "placement": ImagePlacement(anchor="cover", section_index=-1),
    }
    base.update(overrides)
    return ImageSpec(**base)  # type: ignore[arg-type]


class TestNoTextClause:
    def test_clause_is_present_and_substantial(self) -> None:
        assert isinstance(NO_TEXT_CLAUSE, str)
        assert len(NO_TEXT_CLAUSE) >= 200
        assert "no text" in NO_TEXT_CLAUSE.lower()

    def test_clause_capped_under_800_chars(self) -> None:
        assert len(NO_TEXT_CLAUSE) <= 800


class TestRoleAwareRenderingClause:
    """Diagrammatic roles require labels; illustrative roles ban text."""

    def test_labeled_roles_cover_the_explanatory_set(self) -> None:
        assert sorted(LABELED_ROLE_STYLES) == [
            "comparison_split",
            "concept",
            "process_step",
            "screenshot_mock",
            "stat_card",
        ]

    def test_hero_role_gets_no_text_clause(self) -> None:
        assert rendering_clause_for_role("hero") is NO_TEXT_CLAUSE

    def test_editorial_role_gets_no_text_clause(self) -> None:
        assert rendering_clause_for_role("editorial") is NO_TEXT_CLAUSE

    def test_diagram_roles_get_labeling_clause(self) -> None:
        for role in LABELED_ROLE_STYLES:
            assert rendering_clause_for_role(role) is LABELED_DIAGRAM_CLAUSE

    def test_concept_prompt_requires_labels_not_text_ban(self) -> None:
        prompt = build_prompt(spec=_spec(role_style="concept"))
        assert "label" in prompt.lower()
        # The hard no-text ban must NOT be present for a diagrammatic role.
        assert NO_TEXT_CLAUSE not in prompt

    def test_process_step_prompt_overrides_style_no_text(self) -> None:
        # isometric_3d (process_step default) says "No baked-in text" — the
        # labeling clause must explicitly override that.
        prompt = build_prompt(
            spec=_spec(role_style="process_step", visual_style="isometric_3d")
        )
        assert "override" in prompt.lower()
        assert "label" in prompt.lower()

    def test_hero_prompt_still_bans_text(self) -> None:
        prompt = build_prompt(spec=_spec(role_style="hero"))
        assert NO_TEXT_CLAUSE in prompt


class TestLabeledDiagramClause:
    def test_clause_is_substantial_and_capped(self) -> None:
        assert 200 <= len(LABELED_DIAGRAM_CLAUSE) <= 1000
        assert "label" in LABELED_DIAGRAM_CLAUSE.lower()


class TestAspectInstruction:
    def test_known_aspects_each_have_a_sentence(self) -> None:
        for aspect in ("16:9", "1:1", "4:3", "3:4", "4:5"):
            sentence = aspect_instruction(aspect)
            assert sentence
            assert aspect in sentence

    def test_unknown_aspect_returns_empty(self) -> None:
        assert aspect_instruction("21:9") == ""


class TestBuildPromptBranchOne:
    """Branch 1: prompt_override + has_style → composition-reference trick."""

    def test_includes_composition_ignored_framing(self) -> None:
        prompt = build_prompt(
            spec=_spec(visual_style="lifestyle_photo"),
            prompt_override="Photo of a woman writing notes at a wooden desk.",
        )
        assert "Composition reference" in prompt or "IGNORED" in prompt
        assert "Photo of a woman writing notes" in prompt
        # Style fragment must be present too (lifestyle_photo => "DSLR" verbiage).
        assert "dslr" in prompt.lower() or "editorial-grade" in prompt.lower()

    def test_includes_no_text_clause(self) -> None:
        prompt = build_prompt(
            spec=_spec(visual_style="lifestyle_photo"),
            prompt_override="Override scene.",
        )
        assert "no text" in prompt.lower()


class TestBuildPromptBranchTwo:
    """Branch 2: prompt_override only — no style override."""

    def test_returns_override_plus_no_text_clause(self) -> None:
        prompt = build_prompt(
            spec=_spec(visual_style=None),
            prompt_override="Concrete subject scene.",
        )
        assert "Concrete subject scene." in prompt
        assert "no text" in prompt.lower()
        assert "Composition reference" not in prompt

    def test_does_not_include_a_style_fragment(self) -> None:
        prompt = build_prompt(
            spec=_spec(visual_style=None),
            prompt_override="Override only.",
        )
        # No catalogue fragments should leak through.
        assert "dslr" not in prompt.lower()
        assert "isometric" not in prompt.lower()


class TestBuildPromptBranchThree:
    """Branch 3: no override + has_style → style fragment + spec subject."""

    def test_combines_subject_with_style_fragment(self) -> None:
        prompt = build_prompt(
            spec=_spec(
                prompt="An engineering team during a sprint review.",
                visual_style="isometric_3d",
            ),
            prompt_override=None,
        )
        assert "engineering team" in prompt.lower()
        assert "isometric" in prompt.lower()

    def test_carries_no_text_clause(self) -> None:
        prompt = build_prompt(
            spec=_spec(prompt="Engineering scene.", visual_style="isometric_3d"),
            prompt_override=None,
        )
        assert "no text" in prompt.lower()


class TestBuildPromptBranchFour:
    """Branch 4: no override + no style → spec subject + no_text_clause only."""

    def test_minimal_prompt_returns_subject_with_no_text_clause(self) -> None:
        prompt = build_prompt(
            spec=_spec(prompt="Soft morning light over a quiet workshop."),
            prompt_override=None,
        )
        assert "Soft morning light" in prompt
        assert "no text" in prompt.lower()


class TestPageDirectionAndSectionOverride:
    def test_page_direction_layered_in(self) -> None:
        prompt = build_prompt(
            spec=_spec(visual_style="lifestyle_photo"),
            page_direction="warm slate palette, crisp morning light",
        )
        assert "warm slate" in prompt.lower()

    def test_section_override_layered_in(self) -> None:
        prompt = build_prompt(
            spec=_spec(visual_style="lifestyle_photo"),
            section_override="emphasise hands typing on keyboard",
        )
        assert "emphasise hands" in prompt.lower()

    def test_refine_note_layered_in(self) -> None:
        prompt = build_prompt(
            spec=_spec(visual_style="lifestyle_photo"),
            refine_note="more candid, less posed",
        )
        assert "more candid" in prompt.lower()


class TestGeminiAspectInstruction:
    def test_aspect_sentence_appended_for_gemini_flash(self) -> None:
        prompt = build_prompt(
            spec=_spec(aspect_ratio="1:1", provider="gemini_flash"),
        )
        # The sentence asks the model to compose for the aspect ratio.
        assert "1:1" in prompt

    def test_no_aspect_sentence_for_imagen(self) -> None:
        prompt = build_prompt(
            spec=_spec(aspect_ratio="3:4", provider="imagen_4"),
        )
        # Imagen has a native aspect parameter; no need to repeat in the prompt.
        # The aspect token may incidentally appear inside the no-text clause,
        # but the dedicated "compose this image with a … aspect ratio" sentence
        # should not be present for Imagen.
        assert "compose this image with a 3:4 aspect ratio" not in prompt.lower()


class TestStyleTextCap:
    def test_style_block_capped_at_800_chars(self) -> None:
        # A monstrous page_direction should not balloon the style block.
        big = "x" * 4000
        prompt = build_prompt(
            spec=_spec(visual_style="lifestyle_photo"),
            page_direction=big,
        )
        # The style block portion should never carry the full 4000 chars.
        assert prompt.count("x" * 1000) == 0


class TestProviderHint:
    def test_no_text_clause_present_regardless_of_provider(self) -> None:
        for provider in ("gemini_flash", "gemini_3_pro", "imagen_4", "dalle_3"):
            prompt = build_prompt(spec=_spec(provider=provider))  # type: ignore[arg-type]
            assert "no text" in prompt.lower()
