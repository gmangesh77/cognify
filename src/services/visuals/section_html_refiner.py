"""Claude-driven section HTML refinement (Phase 4 / VISUAL-007).

Lets the editor iterate on a section's rendered layout via natural-
language instructions WITHOUT re-running the full content pipeline.

Boundary invariants:
- Pure-content concern (ADR-003) — never imports from
  `src/services/publishing/`. Returns a refined HTML fragment that the
  caller (Studio) decides what to do with.
- Server-side prompt only — the frontend sends the *instruction* but
  the prompt template stays here, so banned-pattern guarantees can be
  enforced consistently.
- Anchor-safe by default — the prompt instructs Claude to preserve
  `data-spec-id` markers, image elements, and `<h2>` headings so
  Visual Studio's image specs stay attached after a refine pass. Hard
  validation (anchor preservation tests) lives in Phase 8 alongside
  the prose rewriter — for Phase 4 we ship the conservative prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = structlog.get_logger()

_REFINER_SYSTEM = (
    "You are a senior front-end engineer iterating on the HTML/CSS of a "
    "single article section. The user will give you the current rendered "
    "HTML and a natural-language instruction. Return ONLY the refined HTML "
    "fragment for that section — no markdown fences, no commentary, no "
    "explanation. PRESERVE every `data-spec-id` attribute on `<img>` and "
    "`<figure>` elements verbatim. PRESERVE every `<h2>` heading text. "
    "PRESERVE every `<a>` href on citations. Use only inline `style` "
    "attributes; do not add `<style>` blocks or `<script>` tags. Do not "
    "embed remote URLs that weren't already in the input."
)


@dataclass(frozen=True)
class SectionHtmlRefineResult:
    html_fragment: str
    model: str
    prompt_used: str


async def refine_section_html(
    *,
    section_id: str,
    instruction: str,
    current_html: str,
    llm: BaseChatModel,
) -> SectionHtmlRefineResult:
    """Apply `instruction` to `current_html` via Claude, return new HTML."""
    messages: list[SystemMessage | HumanMessage] = [
        SystemMessage(content=_REFINER_SYSTEM),
        HumanMessage(
            content=(
                f"Section id: {section_id}\n\n"
                f"Instruction:\n{instruction}\n\n"
                f"Current HTML:\n{current_html}"
            )
        ),
    ]
    response = await llm.ainvoke(messages)
    raw = str(response.content).strip()
    cleaned = _strip_fences(raw)
    model_name = getattr(llm, "model", None) or getattr(llm, "model_name", "unknown")
    return SectionHtmlRefineResult(
        html_fragment=cleaned,
        model=str(model_name),
        prompt_used=_REFINER_SYSTEM,
    )


def _strip_fences(text: str) -> str:
    """Remove ``` fences if Claude ignored the instruction and added them."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3].rstrip()
    return stripped
