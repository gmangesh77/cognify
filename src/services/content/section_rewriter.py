"""Claude-driven section / paragraph prose rewrite (VISUAL-011 / Phase 8).

Lets the editor refine the prose of a single section without re-running
the full content pipeline. Mirrors `src/services/visuals/section_html_refiner.py`
in shape: same rate-limit dependency injection at the route layer, same
return-result dataclass, same logger structure.

Boundary invariants:
- Pure-content concern. Never imports from `src/services/publishing/` —
  publishing keeps consuming CanonicalArticle exactly as before.
- Server-side prompt only. The frontend posts a free-text instruction
  OR a tone-preset name; the backend expands presets here so the
  banned-pattern guarantees can be enforced consistently (no platform
  leakage).
- Anchor-safe by default. The prompt instructs Claude to preserve
  `data-spec-id` markers and bound `before_heading` titles; hard
  validation lives in `section_anchors.validate_anchors` and is invoked
  by the API layer so 422 with a structured diff is what bubbles up.
- Persona-aware. Reuses `get_persona_register` from
  `src/services/visuals/persona_directions.py` (the planner already
  uses it). Never forks the register.
- L-002 compliance. Output is plain markdown, not JSON, so no
  `parse_llm_json` wrap is needed — but the model is told explicitly
  to omit fences.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts import DEFAULT_PROMPTS, render_prompt
from src.services.content.word_diff import WordDiffOp, diff_words
from src.services.visuals.persona_directions import get_persona_register
from src.utils.llm_usage import extract_usage

logger = structlog.get_logger()

RewriteScope = Literal["paragraph", "section"]
TonePreset = Literal[
    "shorter",
    "more_concrete",
    "more_conversational",
    "more_authoritative",
]

TONE_PRESETS: dict[TonePreset, str] = {
    "shorter": DEFAULT_PROMPTS["section_rewrite.tone.shorter"].template,
    "more_concrete": DEFAULT_PROMPTS["section_rewrite.tone.more_concrete"].template,
    "more_conversational": (
        DEFAULT_PROMPTS["section_rewrite.tone.more_conversational"].template
    ),
    "more_authoritative": (
        DEFAULT_PROMPTS["section_rewrite.tone.more_authoritative"].template
    ),
}

_BANNED_PATTERNS_BLOCK = (
    "Hard rules — violating any of these makes the output unusable:\n"
    "- Do NOT add new headings (no `##`, no `<h2>` etc.).\n"
    "- Do NOT introduce new statistics, percentages, dollar amounts, "
    "dates, or names that are not in the original markdown.\n"
    "- Do NOT add quoted citations, blockquotes, or `[N]` reference "
    "markers that are not in the original markdown.\n"
    '- Do NOT remove or rename any `data-spec-id="…"` attribute.\n'
    "- Do NOT introduce code blocks, image markdown, or HTML beyond "
    "what was already in the original.\n"
    "- Return PLAIN markdown only — no fenced code blocks around the "
    "output, no commentary, no preamble."
)


@dataclass(frozen=True)
class RewriteResult:
    """Outcome of one Claude rewrite pass."""

    markdown_fragment: str
    diff: list[WordDiffOp]
    model: str
    prompt_used: str
    instruction: str
    tokens_input: int | None
    tokens_output: int | None
    usd: float | None


def expand_tone_preset(preset: TonePreset) -> str:
    """Return the server-side instruction template for a tone preset.

    The frontend never sees this string — it ships only `{ "preset": ... }`
    so banned-pattern guards stay server-side.
    """
    return render_prompt(f"section_rewrite.tone.{preset}")


async def rewrite_section_prose(
    *,
    section_id: str,
    instruction: str,
    current_markdown: str,
    scope: RewriteScope = "section",
    paragraph_index: int | None = None,
    audience_persona: str | None = None,
    llm: BaseChatModel,
) -> RewriteResult:
    """Apply `instruction` to `current_markdown` via Claude.

    Returns the rewritten markdown, a word-level diff for UI display,
    and usage metadata. Anchor preservation is the API layer's job —
    this service just emits the rewrite.
    """
    persona_register = get_persona_register(audience_persona)
    user_prompt = _build_user_prompt(
        section_id=section_id,
        instruction=instruction,
        current_markdown=current_markdown,
        scope=scope,
        paragraph_index=paragraph_index,
        persona_register=persona_register,
    )
    system_prompt = render_prompt("section_rewrite.system")
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = await llm.ainvoke(messages)
    raw = str(response.content).strip()
    fragment = strip_fences(raw)
    diff = diff_words(current_markdown, fragment)
    usage = extract_usage(response)
    model_name = model_label(llm)
    logger.info(
        "section_prose_rewritten",
        section_id=section_id,
        scope=scope,
        instruction_len=len(instruction),
        before_chars=len(current_markdown),
        after_chars=len(fragment),
        diff_ops=len(diff),
    )
    return RewriteResult(
        markdown_fragment=fragment,
        diff=diff,
        model=str(model_name),
        prompt_used=system_prompt,
        instruction=instruction,
        tokens_input=usage.get("input"),
        tokens_output=usage.get("output"),
        usd=None,
    )


def _build_user_prompt(
    *,
    section_id: str,
    instruction: str,
    current_markdown: str,
    scope: RewriteScope,
    paragraph_index: int | None,
    persona_register: str,
) -> str:
    scope_block = _scope_block(scope, paragraph_index)
    return (
        f"Section id: {section_id}\n"
        f"Scope: {scope_block}\n\n"
        f"Audience register (guidance, not a hard rule):\n"
        f"{persona_register}\n\n"
        f"{_BANNED_PATTERNS_BLOCK}\n\n"
        f"Instruction:\n{instruction}\n\n"
        f"Current markdown:\n{current_markdown}"
    )


def _scope_block(scope: RewriteScope, paragraph_index: int | None) -> str:
    if scope == "paragraph" and paragraph_index is not None:
        return f"paragraph {paragraph_index} of the section"
    return "the entire section body"


def strip_fences(text: str) -> str:
    """Drop a surrounding ``` fence the model added despite instructions."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3].rstrip()
    return stripped


def model_label(llm: object) -> str:
    """Best-effort model name for version rows (TrackedChatModel wraps `.inner`)."""
    for target in (llm, getattr(llm, "inner", None)):
        for attr in ("model", "model_name"):
            value = getattr(target, attr, None)
            if isinstance(value, str) and value:
                return value
    return "unknown"


__all__ = [
    "RewriteResult",
    "RewriteScope",
    "TONE_PRESETS",
    "TonePreset",
    "expand_tone_preset",
    "model_label",
    "rewrite_section_prose",
    "strip_fences",
]
