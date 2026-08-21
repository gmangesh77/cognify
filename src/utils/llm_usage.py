"""Token-usage extraction from LangChain chat responses.

Promoted from `section_rewriter._extract_usage` (VISUAL-011) so the
section drafter, the rewriter and the regenerate service share one
implementation. Returns ``{"input": int | None, "output": int | None}``.
"""

from __future__ import annotations


def extract_usage(response: object) -> dict[str, int | None]:
    """Pull token counts off whatever Claude / FakeLLM returned."""
    metadata = getattr(response, "usage_metadata", None) or {}
    if isinstance(metadata, dict) and metadata:
        return {
            "input": metadata.get("input_tokens"),
            "output": metadata.get("output_tokens"),
        }
    response_metadata = getattr(response, "response_metadata", None) or {}
    usage = (
        response_metadata.get("usage") if isinstance(response_metadata, dict) else None
    )
    if isinstance(usage, dict):
        return {
            "input": usage.get("input_tokens") or usage.get("prompt_tokens"),
            "output": usage.get("output_tokens") or usage.get("completion_tokens"),
        }
    return {"input": None, "output": None}


__all__ = ["extract_usage"]
