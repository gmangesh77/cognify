"""Helpers for per-section regeneration (AUTHOR-004) — no repository I/O.

`carry_anchor_blocks` is block-aware (via `src/utils/markdown_structure`,
the same parser the humanizer uses) so figure anchors land back where
they were relative to the surrounding prose instead of being appended.
"""

from __future__ import annotations

from uuid import UUID

from src.agents.content.article_assembler import strip_leading_heading
from src.agents.content.citation_manager import strip_citation_markers
from src.agents.content.section_drafter import DraftingContext
from src.models.content_pipeline import OutlineSection, SectionDraft, SectionQueries
from src.services.content.section_anchors import find_spec_ids
from src.services.content.section_history_contracts import (
    SectionNotFoundError,
    md_index_for,
    outline_index_for,
)
from src.services.content.section_markdown import MarkdownSection, split_sections
from src.services.content.section_regenerate_models import (
    RegenerateDeps,
    RegenerateInputs,
)
from src.services.content.section_rewriter import strip_fences
from src.utils.markdown_structure import (
    MarkdownBlock,
    extract_humanizable_text,
    parse_markdown_blocks,
    reassemble,
)

_REFERENCES_HEADING = "references"


def build_drafting_context(
    prep: RegenerateInputs, deps: RegenerateDeps
) -> DraftingContext:
    """Live previous sections + session params + editor instruction."""
    session = prep.session
    return DraftingContext(
        retriever=deps.retriever,
        topic_id=str(prep.draft.topic_id),
        llm=deps.llm,
        prior_drafts=prior_drafts_from_body(
            prep.article.body_markdown, prep.cmd.section_index
        ),
        target_audience=session.target_audience if session else None,
        content_tone=session.content_tone if session else None,
        preferred_angle=session.preferred_angle if session else None,
        keywords=session.keywords if session else None,
        instruction=prep.cmd.instruction,
    )


def reject_non_prose(section: MarkdownSection, article_id: UUID) -> None:
    """The References tail (and anything heading-less) is not regenerable."""
    heading = (section.heading or "").lstrip("#").strip().lower()
    if section.heading is None or heading == _REFERENCES_HEADING:
        raise SectionNotFoundError(
            f"section {outline_index_for(section.index)} of article "
            f"{article_id} is not a prose section"
        )


def _anchor_lines(block: MarkdownBlock, present: set[str]) -> str:
    """Lines of `block` holding a data-spec-id that the new body lacks."""
    return "\n".join(
        ln for ln in block.lines if any(sid not in present for sid in find_spec_ids(ln))
    )


def _slot(pos: int, old_total: int, new_total: int) -> int:
    """First stays first, last stays last, otherwise proportional."""
    if pos == 0:
        return 0
    if pos >= old_total - 1:
        return new_total
    return round(pos / (old_total - 1) * new_total)


def _carried_anchor_lines(old_body: str, new_body: str) -> list[tuple[int, str]]:
    """(old block position, data-spec-id lines) for anchors missing from new."""
    present = set(find_spec_ids(new_body))
    carried: list[tuple[int, str]] = []
    for pos, block in enumerate(parse_markdown_blocks(old_body)):
        lines = _anchor_lines(block, present)
        if lines:
            carried.append((pos, lines))
    return carried


def carry_anchor_blocks(old_body: str, new_body: str) -> str:
    """Re-insert every data-spec-id line of `old_body` by relative position."""
    carried = _carried_anchor_lines(old_body, new_body)
    if not carried:
        return new_body
    old_total = len(parse_markdown_blocks(old_body))
    new_blocks = parse_markdown_blocks(new_body)
    base = len(new_blocks)
    for offset, (pos, lines) in enumerate(carried):
        block = MarkdownBlock(kind="content", raw=lines, lines=lines.split("\n"))
        new_blocks.insert(_slot(pos, old_total, base) + offset, block)
    return reassemble(new_blocks)


def assemble_section(old: MarkdownSection, raw_llm_text: str) -> str:
    """Raw LLM prose → full section: original H2 + clean body + anchors."""
    body = strip_citation_markers(
        strip_leading_heading(strip_fences(raw_llm_text))
    ).strip()
    body = carry_anchor_blocks(old.body, body)
    return f"{old.heading or ''}\n\n{body}".strip("\n") + "\n"


def _is_markup(block: MarkdownBlock) -> bool:
    return block.raw.lstrip().startswith("<") or bool(find_spec_ids(block.raw))


def _prose_only(body: str) -> str:
    blocks = [
        b
        for b in parse_markdown_blocks(body)
        if extract_humanizable_text(b) is not None and not _is_markup(b)
    ]
    return reassemble(blocks)


def prior_drafts_from_body(
    body_markdown: str, section_index: int
) -> list[SectionDraft]:
    """Live H2 sections BEFORE outline `section_index`, prose blocks only."""
    drafts: list[SectionDraft] = []
    for section in split_sections(body_markdown)[1 : md_index_for(section_index)]:
        prose = _prose_only(section.body)
        drafts.append(
            SectionDraft(
                section_index=outline_index_for(section.index),
                title=(section.heading or "").lstrip("#").strip(),
                body_markdown=prose,
                word_count=len(prose.split()),
                citations_used=[],
            )
        )
    return drafts


def queries_for(section: OutlineSection) -> SectionQueries:
    """Cheap retrieval queries — no LLM call (L-007 stays at one call)."""
    return SectionQueries(
        section_index=section.index, queries=[section.title, *section.key_points]
    )


__all__ = [
    "assemble_section",
    "build_drafting_context",
    "carry_anchor_blocks",
    "prior_drafts_from_body",
    "queries_for",
    "reject_non_prose",
]
