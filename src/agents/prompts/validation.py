"""Save-time validation for prompt overrides (AUTHOR-012, spec §3.3)."""

from __future__ import annotations

from string import Formatter

from src.agents.prompts.registry import PromptTemplate

MAX_TEMPLATE_CHARS = 20_000


def validate_template(template: str, spec: PromptTemplate) -> list[str]:
    """Return every rule the template breaks (empty list = valid)."""
    if not template.strip():
        return ["template is empty"]
    if len(template) > MAX_TEMPLATE_CHARS:
        return [f"template exceeds {MAX_TEMPLATE_CHARS} characters"]
    if not spec.variables:
        # Zero-variable templates are returned verbatim by the registry —
        # literal braces are fine and there is nothing to check.
        return []
    try:
        fields = list(Formatter().parse(template))
    except ValueError as exc:
        return [f"invalid template syntax: {exc}"]
    return _placeholder_violations(fields, spec)


def _format_spec_message(name: str, fmt: str | None, conversion: str | None) -> str:
    """Render a placeholder with format spec/conversion for error message."""
    rendered = "{" + name
    if conversion:
        rendered += f"!{conversion}"
    if fmt:
        rendered += f":{fmt}"
    rendered += "}"
    return f"format specs and conversions are not allowed ({rendered})"


def _placeholder_violations(
    fields: list[tuple[str, str | None, str | None, str | None]],
    spec: PromptTemplate,
) -> list[str]:
    violations: list[str] = []
    seen: set[str] = set()
    for _literal, name, fmt, conversion in fields:
        if name is None:
            continue
        if name == "" or name.isdigit():
            violations.append("positional placeholders are not allowed")
            continue
        # Record before the format-spec check so a badly-formatted named
        # placeholder isn't ALSO reported as a missing required variable.
        seen.add(name)
        if fmt or conversion:
            msg = _format_spec_message(name, fmt, conversion)
            violations.append(msg)
            continue
        if name not in spec.variables:
            violations.append(f"unknown variable {{{name}}}")
    for missing in sorted(spec.variables - seen):
        violations.append(f"missing required variable {{{missing}}}")
    return list(dict.fromkeys(violations))
