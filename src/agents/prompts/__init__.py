"""Prompt registry (AUTHOR-012). Import the defaults modules for their
side effect of registering templates."""

from src.agents.prompts import (  # noqa: F401 — registration side effects
    defaults_content,
    defaults_content_post,
    defaults_editing,
    defaults_linkedin,
    defaults_research,
)
from src.agents.prompts.registry import (
    DEFAULT_PROMPTS,
    PromptTemplate,
    bind_prompt_overrides,
    current_prompt_overrides,
    render_prompt,
    resolve_prompt,
)

__all__ = [
    "DEFAULT_PROMPTS",
    "PromptTemplate",
    "bind_prompt_overrides",
    "current_prompt_overrides",
    "render_prompt",
    "resolve_prompt",
]
