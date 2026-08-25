"""Section drafter — RAG retrieval + LLM drafting + citation extraction.

Drafts a single article section grounded in retrieved research chunks.
Citations are extracted post-draft by matching [N] refs to source chunks.
"""

import re
from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from src.agents.content.section_prompt import SYSTEM_PROMPT, build_messages
from src.models.content_pipeline import (
    CitationRef,
    OutlineSection,
    SectionDraft,
    SectionQueries,
)
from src.models.research import ChunkResult
from src.services.milvus_retriever import MilvusRetriever
from src.utils.llm_usage import extract_usage

logger = structlog.get_logger()

# Re-exported so existing prompt-regression tests keep importing from here.
_SYSTEM_PROMPT = SYSTEM_PROMPT

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class DraftingContext:
    """Shared dependencies for section drafting."""

    retriever: MilvusRetriever | None
    topic_id: str
    llm: BaseChatModel
    prior_drafts: list[SectionDraft]
    target_audience: str | None = None
    content_tone: str | None = None
    preferred_angle: str | None = None
    keywords: list[str] | None = None
    instruction: str | None = None


@dataclass(frozen=True)
class OneSectionDraft:
    """Graph-free single-section result (AUTHOR-004 regenerate path)."""

    body_markdown: str
    word_count: int
    tokens_input: int | None
    tokens_output: int | None


async def draft_section(
    section: OutlineSection,
    queries: SectionQueries,
    ctx: DraftingContext,
) -> SectionDraft:
    """Draft one section using RAG context and LLM (pipeline entry point)."""
    draft, _ = await _draft(section, queries, ctx)
    return draft


async def draft_one_section(
    section: OutlineSection,
    queries: SectionQueries,
    ctx: DraftingContext,
) -> OneSectionDraft:
    """Graph-free single-section draft with token usage (AUTHOR-004).

    Exactly one LLM call; retrieval is skipped when `ctx.retriever` is None.
    """
    draft, response = await _draft(section, queries, ctx)
    usage = extract_usage(response)
    return OneSectionDraft(
        body_markdown=draft.body_markdown,
        word_count=draft.word_count,
        tokens_input=usage.get("input"),
        tokens_output=usage.get("output"),
    )


async def _draft(
    section: OutlineSection,
    queries: SectionQueries,
    ctx: DraftingContext,
) -> tuple[SectionDraft, BaseMessage]:
    """Retrieve, call the LLM once, build the SectionDraft (+ raw response)."""
    logger.info(
        "section_draft_started", section_index=section.index, title=section.title
    )
    chunks = await _retrieve_chunks(queries, ctx)
    logger.info(
        "section_chunks_retrieved",
        section_index=section.index,
        chunk_count=len(chunks),
        unique_sources=len({c.source_url for c in chunks}),
    )
    response = await ctx.llm.ainvoke(build_messages(section, chunks, ctx))
    return _to_draft(section, str(response.content), chunks), response


def _to_draft(
    section: OutlineSection, text: str, chunks: list[ChunkResult]
) -> SectionDraft:
    """Extract citations, log the word count and build the SectionDraft."""
    citations = extract_citations(text, chunks)
    word_count = len(text.split())
    _log_word_count(section, word_count, len(citations))
    return SectionDraft(
        section_index=section.index,
        title=section.title,
        body_markdown=text,
        word_count=word_count,
        citations_used=citations,
    )


async def _retrieve_chunks(
    queries: SectionQueries,
    ctx: DraftingContext,
) -> list[ChunkResult]:
    """Retrieve and deduplicate chunks across all queries."""
    if ctx.retriever is None:
        return []
    seen: dict[tuple[str, int], ChunkResult] = {}
    for q in queries.queries:
        results = await ctx.retriever.retrieve(q, ctx.topic_id, top_k=5)
        for chunk in results:
            key = (chunk.source_url, chunk.chunk_index)
            if key not in seen or chunk.score > seen[key].score:
                seen[key] = chunk
    ranked = sorted(seen.values(), key=lambda c: c.score, reverse=True)
    return ranked[:5]


def extract_citations(
    text: str,
    chunks: list[ChunkResult],
) -> list[CitationRef]:
    """Parse [N] references from text and map to source chunks."""
    refs: list[CitationRef] = []
    seen: set[int] = set()
    for match in _CITATION_PATTERN.finditer(text):
        num = int(match.group(1))
        if num in seen or num < 1 or num > len(chunks):
            if num > len(chunks):
                logger.warning("citation_reference_invalid", ref_number=num)
            continue
        seen.add(num)
        chunk = chunks[num - 1]
        refs.append(
            CitationRef(
                index=num,
                source_url=chunk.source_url,
                source_title=chunk.source_title,
                published_at=chunk.published_at,
                author=chunk.author,
            )
        )
    return refs


def _log_word_count(
    section: OutlineSection,
    wc: int,
    citation_count: int,
) -> None:
    """Log word count with warning if outside the section's budget band."""
    if section.target_word_count > 0:
        lo, hi = section.target_word_count // 2, section.target_word_count * 3 // 2
    else:
        lo, hi = 200, 500
    if wc < lo or wc > hi:
        logger.warning(
            "section_word_count_outside_range",
            section_index=section.index,
            word_count=wc,
            target=section.target_word_count,
        )
    logger.info(
        "section_draft_complete",
        section_index=section.index,
        word_count=wc,
        citations_count=citation_count,
    )


__all__ = [
    "DraftingContext",
    "OneSectionDraft",
    "draft_one_section",
    "draft_section",
    "extract_citations",
]
