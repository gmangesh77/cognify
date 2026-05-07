"""Mechanical text fixes and LLM-based section rewriting.

fix_mechanical() applies regex-only cleanups (dashes, whitespace).
rewrite_section() sends a single LLM pass to rephrase flagged slop —
structure-aware (CONTENT-007): the markdown is parsed into typed
blocks, only the prose blocks are sent to the LLM, and headings,
images, code fences, tables, and horizontal rules are restored
verbatim. This prevents the rewriter from garbling structure when a
section's body contains lists or fenced code.
"""

import re

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.content_pipeline import SectionDraft, SlopScore
from src.utils.markdown_structure import (
    MarkdownBlock,
    extract_humanizable_text,
    humanizable_blocks,
    parse_markdown_blocks,
    reassemble,
    replace_humanized_text,
    strip_inline_markdown,
)

logger = structlog.get_logger()

_CITATION_RE = re.compile(r"\[(\d+)\]")

_REWRITE_SYSTEM = (
    "You are an editor making AI-generated text sound natural. "
    "Rewrite the section to fix the listed issues. Keep all factual "
    "claims and [N] citations exactly as they are. Do not change the "
    "meaning. Only fix the writing style. "
    "If the input contains the sentinel `<<<BLOCK>>>` between chunks, "
    "preserve every sentinel verbatim and rewrite each chunk in place "
    "— the rewrite must contain exactly the same number of sentinels "
    "as the input."
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


def _build_rewrite_prompt(
    section: SectionDraft,
    score: SlopScore,
    prose_payload: str | None = None,
) -> str:
    """Format violations into LLM instructions.

    `prose_payload`, when provided, is the structure-stripped prose
    (CONTENT-007) — only the prose blocks separated by `<<<BLOCK>>>`
    sentinels. Falls back to `section.body_markdown` for callers that
    haven't migrated yet.
    """
    body = prose_payload if prose_payload is not None else section.body_markdown
    lines = ["Rewrite the following section to fix these issues:\n"]
    for v in score.violations:
        lines.append(f'- Sentence {v.sentence_index}: {v.category} "{v.phrase}"')
    lines.append(f"\nSection text:\n{body}")
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
    """Send one LLM pass to rephrase flagged slop, preserving markdown structure.

    Headings, fenced code, images, tables, and HRs are restored
    verbatim. Only paragraph + list + blockquote blocks are sent to
    the LLM as a concatenated prose payload; the rewriter slots the
    response back into the original block shapes. Citations are
    re-checked at the end — if any `[N]` marker is lost, we fall
    back to the original section (same behaviour as before
    CONTENT-007).
    """
    originals = {m.group(0) for m in _CITATION_RE.finditer(section.body_markdown)}

    blocks = parse_markdown_blocks(section.body_markdown)
    rewritable = humanizable_blocks(blocks)
    if not rewritable:
        logger.debug(
            "humanizer_no_prose_blocks",
            section_index=section.section_index,
        )
        return section

    prose_payload = _payload_for_llm(rewritable)
    prompt = _build_rewrite_prompt(section, slop_score, prose_payload)
    messages = [
        SystemMessage(content=_REWRITE_SYSTEM),
        HumanMessage(content=prompt),
    ]
    response = await llm.ainvoke(messages)
    new_text = str(response.content).strip()

    rebuilt = _slot_back(blocks, rewritable, new_text)
    new_body = reassemble(rebuilt)

    if originals and not _citations_preserved(new_body, originals):
        logger.warning(
            "rewrite_citations_lost",
            section_index=section.section_index,
            expected=sorted(originals),
        )
        return section

    return _build_rewritten_draft(section, new_body)


_BLOCK_DELIM = "\n\n<<<BLOCK>>>\n\n"


def _payload_for_llm(rewritable: list[tuple[int, MarkdownBlock]]) -> str:
    """Concatenate prose blocks with a sentinel the LLM is told to keep."""
    parts: list[str] = []
    for _, block in rewritable:
        prose = extract_humanizable_text(block) or ""
        parts.append(prose)
    return _BLOCK_DELIM.join(parts)


def _slot_back(
    blocks: list[MarkdownBlock],
    rewritable: list[tuple[int, MarkdownBlock]],
    rewritten_payload: str,
) -> list[MarkdownBlock]:
    """Replace the prose blocks in `blocks` with the LLM's per-block output.

    Falls back to the original block when the LLM emits the wrong number
    of blocks (it sometimes drops the sentinel) — better to keep
    structure intact than to over-trust a flaky LLM response.
    """
    new_chunks = rewritten_payload.split(_BLOCK_DELIM)
    if len(new_chunks) != len(rewritable):
        logger.warning(
            "humanizer_block_count_mismatch",
            expected=len(rewritable),
            received=len(new_chunks),
            hint="Falling back to original prose blocks.",
        )
        return blocks
    out = list(blocks)
    for (idx, original_block), new_text in zip(rewritable, new_chunks, strict=False):
        original_prose = extract_humanizable_text(original_block) or ""
        _, markers = strip_inline_markdown(original_prose)
        out[idx] = replace_humanized_text(original_block, new_text.strip(), markers)
    return out
