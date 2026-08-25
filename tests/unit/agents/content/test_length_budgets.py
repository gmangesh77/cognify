"""Tests for length-target word budgets (AUTHOR-008)."""

from src.agents.content.length_budgets import (
    DEFAULT_LENGTH_BUDGETS,
    budget_for,
    content_type_guidance,
)

_KEYS = {
    "sections_min",
    "sections_max",
    "section_min",
    "section_max",
    "total_min",
    "total_max",
}


class TestDefaults:
    def test_all_four_targets_have_complete_budgets(self) -> None:
        assert set(DEFAULT_LENGTH_BUDGETS) == {"short", "medium", "long", "pillar"}
        for budget in DEFAULT_LENGTH_BUDGETS.values():
            assert set(budget) == _KEYS

    def test_medium_matches_legacy_hardcoded_numbers(self) -> None:
        m = DEFAULT_LENGTH_BUDGETS["medium"]
        assert (m["sections_min"], m["sections_max"]) == (4, 8)
        assert (m["section_min"], m["section_max"]) == (200, 500)
        assert (m["total_min"], m["total_max"]) == (1500, 3000)

    def test_budgets_scale_monotonically(self) -> None:
        order = ["short", "medium", "long", "pillar"]
        totals = [DEFAULT_LENGTH_BUDGETS[k]["total_max"] for k in order]
        assert totals == sorted(totals)


class TestBudgetFor:
    def test_none_falls_back_to_medium(self) -> None:
        assert budget_for(None, {}) == DEFAULT_LENGTH_BUDGETS["medium"]

    def test_unknown_falls_back_to_medium(self) -> None:
        assert budget_for("epic", {}) == DEFAULT_LENGTH_BUDGETS["medium"]

    def test_override_merges_per_key_not_wholesale(self) -> None:
        merged = budget_for("long", {"long": {"total_max": 6000}})
        assert merged["total_max"] == 6000
        assert merged["section_min"] == DEFAULT_LENGTH_BUDGETS["long"]["section_min"]

    def test_override_for_other_target_is_ignored(self) -> None:
        assert (
            budget_for("short", {"long": {"total_max": 6000}})
            == DEFAULT_LENGTH_BUDGETS["short"]
        )


class TestContentTypeGuidance:
    def test_article_and_none_yield_no_guidance(self) -> None:
        assert content_type_guidance("article") is None
        assert content_type_guidance(None) is None

    def test_how_to_analysis_report_have_guidance(self) -> None:
        for ct in ("how-to", "analysis", "report"):
            text = content_type_guidance(ct)
            assert text is not None
            assert len(text) > 20
