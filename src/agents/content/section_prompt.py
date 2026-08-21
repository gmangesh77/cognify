"""Prompt assembly for single-section drafting (split out of section_drafter).

Pure functions — no I/O, no graph imports. `DraftingContext` is imported
under TYPE_CHECKING only to avoid a circular import with section_drafter.

The optional editor instruction (AUTHOR-004 regenerate) is appended to the
HUMAN turn, never to the system prompt — same convention as
`section_rewriter` (SECURITY_CHECKLIST §5: no user-controlled prompt
structure).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.models.content_pipeline import OutlineSection, SectionDraft
from src.models.research import ChunkResult

if TYPE_CHECKING:
    from src.agents.content.section_drafter import DraftingContext

SYSTEM_PROMPT = (
    "You are an expert long-form writer. Draft a section of an article "
    "using the provided research context. Every factual claim must include "
    "an inline citation like [1], [2] referencing the numbered sources. "
    "Write in a clear, authoritative tone. Target approximately "
    "{target_word_count} words. "
    "Do not use em-dashes or en-dashes. Use periods or commas instead. "
    "Avoid words like delve, leverage, innovative, transformative, unprecedented. "
    "Skip transitions like moreover, furthermore, additionally. "
    "Vary sentence length and structure. "
    "Write in a natural voice as a knowledgeable human, not an AI assistant."
)


def build_system_prompt(section: OutlineSection, ctx: DraftingContext) -> str:
    """System prompt = base + session params (audience / tone / angle / keywords)."""
    system = SYSTEM_PROMPT.format(target_word_count=section.target_word_count)
    if ctx.target_audience:
        system += f"\nWrite for this audience: {ctx.target_audience}."
    if ctx.content_tone:
        system += f"\nTone: {ctx.content_tone}."
    if ctx.preferred_angle:
        system += f"\nEditorial angle: {ctx.preferred_angle}."
    if ctx.keywords:
        system += (
            f"\nEnsure these key topics are referenced naturally: "
            f"{', '.join(ctx.keywords)}."
        )
    return system


def build_user_prompt(
    section: OutlineSection,
    chunks: list[ChunkResult],
    ctx: DraftingContext,
) -> str:
    """Human turn: section info, RAG context, prior summary, editor instruction."""
    parts = [
        f"## Section: {section.title}\n{section.description}",
        f"Key points: {', '.join(section.key_points)}",
        f"Target: ~{section.target_word_count} words\n",
        *_context_part(chunks),
        *_prior_part(ctx.prior_drafts),
    ]
    instruction = (ctx.instruction or "").strip()
    if instruction:
        parts.append(f"### Editor instruction\n{instruction}")
    return "\n".join(parts)


def _context_part(chunks: list[ChunkResult]) -> list[str]:
    """Numbered research sources; empty when nothing was retrieved."""
    if not chunks:
        return []
    parts = ["### Research Context"]
    for i, c in enumerate(chunks, 1):
        source = f'[{i}] Source: "{c.source_title}" ({c.source_url})'
        parts.append(f"{source}\n{c.text}\n")
    return parts


def _prior_part(prior_drafts: list[SectionDraft]) -> list[str]:
    """One-line summary (first sentence) of each already-drafted section."""
    if not prior_drafts:
        return []
    parts = ["### Prior Sections"]
    for d in prior_drafts:
        first = d.body_markdown.split(".")[0] + "."
        parts.append(f"- {d.title}: {first}")
    return parts


def build_messages(
    section: OutlineSection,
    chunks: list[ChunkResult],
    ctx: DraftingContext,
) -> list[BaseMessage]:
    """System + human message pair for one section draft."""
    return [
        SystemMessage(content=build_system_prompt(section, ctx)),
        HumanMessage(content=build_user_prompt(section, chunks, ctx)),
    ]


__all__ = [
    "SYSTEM_PROMPT",
    "build_messages",
    "build_system_prompt",
    "build_user_prompt",
]
