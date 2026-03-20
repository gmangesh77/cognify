"""Mechanical text fixes and LLM-based section rewriting.

fix_mechanical() applies regex-only cleanups (dashes, whitespace).
rewrite_section() sends a single LLM pass to rephrase flagged slop.
"""

import re

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.content_pipeline import SectionDraft, SlopScore

logger = structlog.get_logger()

_CITATION_RE = re.compile(r"\[(\d+)\]")

_REWRITE_SYSTEM = (
    "You are an editor making AI-generated text sound natural. "
    "Rewrite the section to fix the listed issues. Keep all factual "
    "claims and [N] citations exactly as they are. Do not change the "
    "meaning. Only fix the writing style."
)


def _replace_dashes(text: str) -> str:
    """Replace em/en-dashes with comma or period."""
    result: list[str] = []
    i = 0
    while i < len(text):
        if text[i] in ("\u2014", "\u2013"):
            # Strip trailing space before the dash
            while result and result[-1] == " ":
                result.pop()
            rest = text[i + 1 :].lstrip()
            if rest and rest[0].isupper():
                result.append(".")
            else:
                result.append(",")
            # Skip any whitespace after the dash
            i += 1
            while i < len(text) and text[i] == " ":
                i += 1
            result.append(" ")
            continue
        result.append(text[i])
        i += 1
    return "".join(result)


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces and blank lines."""
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fix_mechanical(text: str) -> str:
    """Apply regex-only mechanical fixes (no LLM)."""
    text = _replace_dashes(text)
    return _normalize_whitespace(text)


def _build_rewrite_prompt(section: SectionDraft, score: SlopScore) -> str:
    """Format violations into LLM instructions."""
    lines = ["Rewrite the following section to fix these issues:\n"]
    for v in score.violations:
        lines.append(
            f"- Sentence {v.sentence_index}: {v.category} \"{v.phrase}\""
        )
    lines.append(f"\nSection text:\n{section.body_markdown}")
    return "\n".join(lines)


def _citations_preserved(new_text: str, originals: set[str]) -> bool:
    """Check every original citation ref appears in new text."""
    found = {m.group(0) for m in _CITATION_RE.finditer(new_text)}
    return originals.issubset(found)


def _build_rewritten_draft(section: SectionDraft, text: str) -> SectionDraft:
    """Construct a new SectionDraft from rewritten text."""
    return SectionDraft(
        section_index=section.section_index,
        title=section.title,
        body_markdown=text,
        word_count=len(text.split()),
        citations_used=section.citations_used,
    )


async def rewrite_section(
    section: SectionDraft,
    slop_score: SlopScore,
    llm: BaseChatModel,
) -> SectionDraft:
    """Send one LLM pass to rephrase flagged slop."""
    originals = {m.group(0) for m in _CITATION_RE.finditer(section.body_markdown)}

    prompt = _build_rewrite_prompt(section, slop_score)
    messages = [SystemMessage(content=_REWRITE_SYSTEM), HumanMessage(content=prompt)]
    response = await llm.ainvoke(messages)
    new_text = str(response.content).strip()

    if originals and not _citations_preserved(new_text, originals):
        logger.warning(
            "rewrite_citations_lost",
            section_index=section.section_index,
            expected=sorted(originals),
        )
        return section

    return _build_rewritten_draft(section, new_text)
