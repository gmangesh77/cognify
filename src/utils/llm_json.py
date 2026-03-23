"""Utility for parsing JSON from LLM responses."""

import json


def parse_llm_json(text: str) -> object:
    """Parse JSON from LLM output, stripping markdown fences."""
    return json.loads(strip_markdown_fences(text))


def strip_markdown_fences(text: str) -> str:
    """Strip ```json ... ``` fences from LLM output."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1:]
        if stripped.endswith("```"):
            stripped = stripped[:-3].rstrip()
    return stripped
