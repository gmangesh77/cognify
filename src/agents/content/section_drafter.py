"""Section drafter — RAG retrieval + LLM drafting + citation extraction.

Drafts a single article section grounded in retrieved research chunks.
Citations are extracted post-draft by matching [N] refs to source chunks.
"""

import re
from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.content_pipeline import (
    CitationRef,
    OutlineSection,
    SectionDraft,
    SectionQueries,
)
from src.models.research import ChunkResult
from src.services.milvus_retriever import MilvusRetriever

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
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

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class DraftingContext:
    """Shared dependencies for section drafting."""

    retriever: MilvusRetriever | None
    topic_id: str
    llm: BaseChatModel
    prior_drafts: list[SectionDraft]


async def draft_section(
    section: OutlineSection,
    queries: SectionQueries,
    ctx: DraftingContext,
) -> SectionDraft:
    """Draft one section using RAG context and LLM."""
    logger.info(
        "section_draft_started",
        section_index=section.index,
        title=section.title,
    )
    chunks = await _retrieve_chunks(queries, ctx)
    logger.info(
        "section_chunks_retrieved",
        section_index=section.index,
        chunk_count=len(chunks),
        unique_sources=len({c.source_url for c in chunks}),
    )
    text = await _call_llm(section, chunks, ctx)
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


async def _call_llm(
    section: OutlineSection,
    chunks: list[ChunkResult],
    ctx: DraftingContext,
) -> str:
    """Build prompt and call LLM to draft section text."""
    system = _SYSTEM_PROMPT.format(
        target_word_count=section.target_word_count,
    )
    user = _build_user_prompt(section, chunks, ctx.prior_drafts)
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    response = await ctx.llm.ainvoke(messages)
    return str(response.content)


def _build_user_prompt(
    section: OutlineSection,
    chunks: list[ChunkResult],
    prior_drafts: list[SectionDraft],
) -> str:
    """Assemble user prompt with section info, RAG context, and prior summary."""
    parts = [
        f"## Section: {section.title}\n{section.description}",
        f"Key points: {', '.join(section.key_points)}",
        f"Target: ~{section.target_word_count} words\n",
    ]
    if chunks:
        parts.append("### Research Context")
        for i, c in enumerate(chunks, 1):
            source = f'[{i}] Source: "{c.source_title}" ({c.source_url})'
            parts.append(f"{source}\n{c.text}\n")
    if prior_drafts:
        parts.append("### Prior Sections")
        for d in prior_drafts:
            first = d.body_markdown.split(".")[0] + "."
            parts.append(f"- {d.title}: {first}")
    return "\n".join(parts)


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
    """Log word count with warning if outside target range."""
    if wc < 200 or wc > 500:
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
