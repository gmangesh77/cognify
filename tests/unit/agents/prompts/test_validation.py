"""AUTHOR-012 — save-time template validation."""

from __future__ import annotations

import pytest

from src.agents.prompts.registry import DEFAULT_PROMPTS, PromptTemplate
from src.agents.prompts.validation import MAX_TEMPLATE_CHARS, validate_template


def _spec(variables: set[str]) -> PromptTemplate:
    return PromptTemplate(
        key="content_outline.user",
        step="content_outline",
        description="d",
        template="ignored",
        variables=frozenset(variables),
    )


class TestRules:
    def test_valid_template_returns_no_violations(self) -> None:
        result = validate_template(
            "Title: {title}\nDomain: {domain}", _spec({"title", "domain"})
        )
        assert result == []

    def test_empty_rejected(self) -> None:
        assert validate_template("   \n", _spec(set())) == ["template is empty"]

    def test_too_long_rejected(self) -> None:
        out = validate_template("x" * (MAX_TEMPLATE_CHARS + 1), _spec(set()))
        assert out == [f"template exceeds {MAX_TEMPLATE_CHARS} characters"]

    def test_unknown_variable_rejected(self) -> None:
        assert validate_template("{title} {bogus}", _spec({"title"})) == [
            "unknown variable {bogus}"
        ]

    def test_missing_required_variable_rejected(self) -> None:
        assert validate_template("only {title}", _spec({"title", "domain"})) == [
            "missing required variable {domain}"
        ]

    def test_positional_placeholder_rejected(self) -> None:
        assert "positional placeholders are not allowed" in validate_template(
            "{} and {0} {title}", _spec({"title"})
        )

    def test_format_spec_rejected(self) -> None:
        assert validate_template("{title:>10}", _spec({"title"})) == [
            "format specs and conversions are not allowed ({title:>10})"
        ]

    def test_escaped_braces_accepted(self) -> None:
        result = validate_template('Return {{"a": 1}} for {title}', _spec({"title"}))
        assert result == []

    def test_zero_variable_template_allows_literal_braces(self) -> None:
        # Zero-variable templates are never .format()ed (registry contract).
        assert validate_template('Respond {"title": "x"}', _spec(set())) == []

    def test_unbalanced_brace_in_variable_template_rejected(self) -> None:
        out = validate_template("{title", _spec({"title"}))
        assert out and out[0].startswith("invalid template syntax")


class TestDefaultsSelfValidate:
    @pytest.mark.parametrize("key", sorted(DEFAULT_PROMPTS))
    def test_every_default_passes_its_own_validation(self, key: str) -> None:
        spec = DEFAULT_PROMPTS[key]
        assert validate_template(spec.template, spec) == []
