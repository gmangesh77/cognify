"""Tests for the markdown section splitter / replacer."""

from __future__ import annotations

import pytest

from src.services.content.section_markdown import (
    get_section,
    replace_section,
    split_sections,
)

ARTICLE = (
    "Intro paragraph above any heading.\n\n"
    "## First Section\n"
    "First section body.\nSecond paragraph.\n\n"
    "## Second Section\n"
    "Second section body.\n"
)


class TestSplitSections:
    def test_splits_into_prelude_plus_two_sections(self) -> None:
        sections = split_sections(ARTICLE)
        assert len(sections) == 3
        assert sections[0].heading is None
        assert sections[0].body.startswith("Intro paragraph")
        assert sections[1].heading == "## First Section"
        assert "First section body" in sections[1].body
        assert sections[2].heading == "## Second Section"

    def test_handles_no_headings(self) -> None:
        sections = split_sections("Just one prelude paragraph.")
        assert len(sections) == 1
        assert sections[0].heading is None
        assert sections[0].body == "Just one prelude paragraph."


class TestGetSection:
    def test_returns_section_when_in_range(self) -> None:
        section = get_section(ARTICLE, 1)
        assert section is not None
        assert section.heading == "## First Section"

    def test_returns_none_when_out_of_range(self) -> None:
        assert get_section(ARTICLE, 99) is None
        assert get_section(ARTICLE, -1) is None


class TestReplaceSection:
    def test_replaces_named_section(self) -> None:
        new_md = "## First Section\nRewritten body that is much shorter."
        rebuilt = replace_section(ARTICLE, 1, new_md)
        assert "Rewritten body that is much shorter" in rebuilt
        assert "First section body" not in rebuilt
        # Other sections preserved
        assert "## Second Section" in rebuilt
        assert "Second section body" in rebuilt

    def test_replaces_prelude(self) -> None:
        rebuilt = replace_section(ARTICLE, 0, "Brand new prelude.")
        assert rebuilt.startswith("Brand new prelude.")
        assert "## First Section" in rebuilt

    def test_raises_on_out_of_range(self) -> None:
        with pytest.raises(IndexError):
            replace_section(ARTICLE, 99, "won't matter")

    def test_round_trip_preserves_content(self) -> None:
        sections = split_sections(ARTICLE)
        rebuilt = ARTICLE
        for section in sections:
            rebuilt = replace_section(rebuilt, section.index, section.text)
        # Section bodies survive even if exact whitespace shifts.
        assert "Intro paragraph above any heading" in rebuilt
        assert "## First Section" in rebuilt
        assert "First section body" in rebuilt
        assert "## Second Section" in rebuilt
        assert "Second section body" in rebuilt
