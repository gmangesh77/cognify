"""AUTHOR-012 — registry resolution + contextvar binding."""

from __future__ import annotations

import pytest

from src.agents.prompts.registry import (
    _REGISTRY,
    DEFAULT_PROMPTS,
    PromptTemplate,
    bind_prompt_overrides,
    current_prompt_overrides,
    register,
    render_prompt,
    resolve_prompt,
)


def _probe() -> PromptTemplate:
    return DEFAULT_PROMPTS["content_queries.user"]


class TestDefaults:
    def test_every_default_renders_with_its_declared_variables(self) -> None:
        for key, spec in DEFAULT_PROMPTS.items():
            rendered = render_prompt(key, **{v: f"<{v}>" for v in spec.variables})
            assert rendered, key
            for v in spec.variables:
                assert f"<{v}>" in rendered, (key, v)

    def test_key_matches_dict_key_and_step_prefix(self) -> None:
        for key, spec in DEFAULT_PROMPTS.items():
            assert spec.key == key
            assert key.startswith(spec.step + "."), key


class TestResolve:
    def test_unbound_returns_default(self) -> None:
        assert resolve_prompt(_probe().key) == _probe().template

    def test_bound_missing_key_returns_default(self) -> None:
        with bind_prompt_overrides({"other.key": "x"}):
            assert resolve_prompt(_probe().key) == _probe().template

    def test_bound_present_key_returns_override(self) -> None:
        with bind_prompt_overrides({_probe().key: "OVERRIDE {sections_text}"}):
            assert resolve_prompt(_probe().key) == "OVERRIDE {sections_text}"

    def test_unknown_key_raises(self) -> None:
        with pytest.raises(KeyError):
            resolve_prompt("nope.system")


class TestRender:
    def test_render_formats_variables(self) -> None:
        out = render_prompt("content_queries.user", sections_text="S1")
        assert "S1" in out
        assert "{sections_text}" not in out

    def test_zero_variable_template_returned_verbatim(self) -> None:
        # No .format() pass: literal braces (JSON examples) must survive.
        spec = DEFAULT_PROMPTS["content_queries.system"]
        assert spec.variables == frozenset()
        assert render_prompt(spec.key) == spec.template

    def test_override_is_rendered_too(self) -> None:
        with bind_prompt_overrides({"content_queries.user": "X {sections_text} Y"}):
            assert render_prompt("content_queries.user", sections_text="1") == "X 1 Y"


class TestBind:
    def test_nested_bind_restores_outer(self) -> None:
        with bind_prompt_overrides({"a": "1"}):
            with bind_prompt_overrides({"a": "2"}):
                assert current_prompt_overrides.get()["a"] == "2"
            assert current_prompt_overrides.get()["a"] == "1"
        assert current_prompt_overrides.get() == {}


class TestRenderOverrideFallback:
    def test_override_with_unknown_placeholder_falls_back_to_default(self) -> None:
        key = _probe().key
        default = DEFAULT_PROMPTS[key].template
        with bind_prompt_overrides({key: "OVERRIDE {sections_text} {typo_var}"}):
            out = render_prompt(key, sections_text="S1")
        assert out == default.format(sections_text="S1")

    def test_default_path_missing_variable_still_raises(self) -> None:
        with pytest.raises(KeyError):
            render_prompt(_probe().key)


class TestRegisterDuplicateGuard:
    def test_duplicate_key_raises(self) -> None:
        spec = PromptTemplate(
            key="content_outline.__test_dup",
            step="content_outline",
            description="d",
            template="x",
            variables=frozenset(),
        )
        register(spec)
        try:
            with pytest.raises(ValueError, match="duplicate prompt key"):
                register(spec)
        finally:
            del _REGISTRY[spec.key]

    def test_bad_step_prefix_raises(self) -> None:
        spec = PromptTemplate(
            key="not_the_step.user",
            step="content_outline",
            description="d",
            template="x",
            variables=frozenset(),
        )
        with pytest.raises(ValueError, match="must start with"):
            register(spec)
