"""Prompt registry + override resolution (AUTHOR-012, program plan §4.6).

Defaults live in code (`defaults_*.py`, registered at import). Overrides
are a `{key: template}` mapping bound to a contextvar for the duration of
one pipeline run (`pipeline_runner`) or one request (`api/prompt_scope`).
Resolution is `override if bound and present, else default`; an unknown
key is a programming error and raises.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class PromptTemplate:
    """One registered prompt: its code default and the variables it may use."""

    key: str
    step: str
    description: str
    template: str
    variables: frozenset[str]


_REGISTRY: dict[str, PromptTemplate] = {}
DEFAULT_PROMPTS: Mapping[str, PromptTemplate] = MappingProxyType(_REGISTRY)

current_prompt_overrides: contextvars.ContextVar[Mapping[str, str]] = (
    contextvars.ContextVar("prompt_overrides", default=MappingProxyType({}))
)


def register(*templates: PromptTemplate) -> None:
    """Register defaults; called at import time by the defaults modules."""
    for spec in templates:
        if not spec.key.startswith(spec.step + "."):
            msg = f"prompt key {spec.key!r} must start with {spec.step!r}."
            raise ValueError(msg)
        if spec.key in _REGISTRY:
            msg = f"duplicate prompt key {spec.key!r}"
            raise ValueError(msg)
        _REGISTRY[spec.key] = spec


def resolve_prompt(key: str) -> str:
    """Effective template for `key`: bound override, else the code default."""
    spec = DEFAULT_PROMPTS[key]  # KeyError on unknown key — deliberate
    override = current_prompt_overrides.get().get(key)
    if override is None:
        return spec.template
    logger.info("prompt_override_applied", key=key)
    return override


def render_prompt(key: str, **variables: object) -> str:
    """Resolve and `.format()` `key`. Zero-variable templates are returned
    verbatim so literal braces (JSON examples) survive.

    A bound override that fails to format (e.g. a variable was renamed
    after the override was saved) falls back to the default template —
    the registry self-validation test guarantees defaults always format.
    The default path is never guarded this way: a missing variable there
    is a programming error and must raise.
    """
    spec = DEFAULT_PROMPTS[key]  # KeyError on unknown key -- deliberate
    if not spec.variables:
        return resolve_prompt(key)
    overrides = current_prompt_overrides.get()
    if key not in overrides:
        return spec.template.format(**variables)
    logger.info("prompt_override_applied", key=key)
    return _render_override(key, overrides[key], spec.template, variables)


def _render_override(
    key: str, override: str, default: str, variables: dict[str, object]
) -> str:
    """`.format()` an override, falling back to `default` on stale variables."""
    try:
        return override.format(**variables)
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning("prompt_override_render_failed", key=key, error=str(exc))
        return default.format(**variables)


@contextmanager
def bind_prompt_overrides(overrides: Mapping[str, str]) -> Iterator[None]:
    """Bind `overrides` for the enclosed block (nested binds restore)."""
    token = current_prompt_overrides.set(MappingProxyType(dict(overrides)))
    try:
        yield
    finally:
        current_prompt_overrides.reset(token)
