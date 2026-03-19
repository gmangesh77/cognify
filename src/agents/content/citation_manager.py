"""Citation management — deduplication, renumbering, validation, URL checks.

Converts per-section CitationRef records into global Citation models,
renumbers inline references, validates source counts, and generates
the references section for article assembly.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

import httpx
import structlog

from src.models.content import Citation
from src.models.content_pipeline import CitationRef, SectionDraft

if TYPE_CHECKING:
    from src.agents.content.pipeline import ContentState

logger = structlog.get_logger()

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")
_MIN_UNIQUE_SOURCES = 5
_URL_CHECK_TIMEOUT = 3.0


class CitationValidationError(Exception):
    """Raised when citations fail validation (e.g. too few sources)."""


def build_global_citation_map(
    drafts: list[SectionDraft],
) -> tuple[list[Citation], dict[tuple[int, int], int]]:
    """Deduplicate citations by URL, assign global indices."""
    url_to_index: dict[str, int] = {}
    citations: list[Citation] = []
    remap: dict[tuple[int, int], int] = {}
    for draft in drafts:
        for ref in draft.citations_used:
            gidx = _get_or_create(url_to_index, citations, ref)
            remap[(draft.section_index, ref.index)] = gidx
    return citations, remap


def _get_or_create(
    url_map: dict[str, int],
    citations: list[Citation],
    ref: CitationRef,
) -> int:
    """Return existing global index or create a new Citation."""
    if ref.source_url in url_map:
        return url_map[ref.source_url]
    gidx = len(citations) + 1
    url_map[ref.source_url] = gidx
    citations.append(_ref_to_citation(ref, gidx))
    return gidx


def _ref_to_citation(ref: CitationRef, index: int) -> Citation:
    """Convert a CitationRef to a full Citation model."""
    authors = [ref.author] if ref.author else []
    return Citation(
        index=index,
        title=ref.source_title,
        url=ref.source_url,
        authors=authors,
        published_at=ref.published_at,
    )


def renumber_section_markdown(
    markdown: str,
    remap: dict[int, int],
) -> str:
    """Replace [N] citation markers using the remap table."""
    if not remap:
        return markdown
    segments = _split_code_blocks(markdown)
    return "".join(
        _renumber_text(s, remap) if not is_code else s for s, is_code in segments
    )


def _split_code_blocks(
    text: str,
) -> list[tuple[str, bool]]:
    """Split text into (segment, is_code_block) pairs."""
    parts = text.split("```")
    return [(p, i % 2 == 1) for i, p in enumerate(parts)]


def _renumber_text(text: str, remap: dict[int, int]) -> str:
    """Replace citation markers in a non-code text segment."""

    def _replace(m: re.Match[str]) -> str:
        local = int(m.group(1))
        return f"[{remap.get(local, local)}]"

    return _CITATION_PATTERN.sub(_replace, text)


def validate_citation_count(
    citations: list[Citation],
    min_sources: int = _MIN_UNIQUE_SOURCES,
) -> None:
    """Raise CitationValidationError if too few unique sources."""
    if len(citations) < min_sources:
        raise CitationValidationError(
            f"Need {min_sources} sources, got {len(citations)}"
        )


async def check_urls(citations: list[Citation]) -> list[Citation]:
    """HEAD-check all citation URLs; log warnings for failures."""
    async with httpx.AsyncClient(timeout=_URL_CHECK_TIMEOUT) as client:
        tasks = [_check_one_url(client, c) for c in citations]
        await asyncio.gather(*tasks, return_exceptions=True)
    return citations


async def _check_one_url(
    client: httpx.AsyncClient,
    citation: Citation,
) -> None:
    """HEAD-check a single URL, log warning on failure."""
    try:
        resp = await client.head(citation.url)
        if resp.status_code >= 400:
            logger.warning(
                "citation_url_unreachable",
                url=citation.url,
                status=resp.status_code,
            )
    except (httpx.HTTPError, httpx.StreamError):
        logger.warning("citation_url_unreachable", url=citation.url)


def generate_references_markdown(
    citations: list[Citation],
) -> str:
    """Build a Markdown references section from citations."""
    lines = ["## References", ""]
    for c in sorted(citations, key=lambda x: x.index):
        lines.append(_format_reference_line(c))
    return "\n".join(lines) + "\n"


def _format_reference_line(c: Citation) -> str:
    """Format a single citation as a reference line."""
    parts = [f"[{c.index}] {c.title}"]
    meta: list[str] = []
    if c.authors:
        meta.append(", ".join(c.authors))
    if c.published_at:
        meta.append(c.published_at.strftime("%Y-%m-%d"))
    if meta:
        parts.append(f" — {', '.join(meta)}.")
    else:
        parts.append(".")
    parts.append(f" {c.url}")
    return "".join(parts)


async def manage_citations(state: ContentState) -> dict[str, object]:
    """Pipeline node: normalize, renumber, validate, and check citations."""
    drafts = list(state.get("section_drafts", []))
    if not drafts:
        return {"status": "failed", "error": "No section drafts to process"}

    # Coerce dicts back to SectionDraft if needed (LangGraph serialization)
    coerced = [
        d if isinstance(d, SectionDraft) else SectionDraft.model_validate(d)
        for d in drafts
    ]

    citations, remap = build_global_citation_map(coerced)

    # Slice composite remap into per-section flat maps
    updated_drafts: list[SectionDraft] = []
    for draft in coerced:
        section_remap = {
            local: remap[(sec_idx, local)]
            for (sec_idx, local) in remap
            if sec_idx == draft.section_index
        }
        new_md = renumber_section_markdown(draft.body_markdown, section_remap)
        updated_drafts.append(draft.model_copy(update={"body_markdown": new_md}))

    try:
        validate_citation_count(citations, _MIN_UNIQUE_SOURCES)
    except CitationValidationError as exc:
        logger.error("citation_validation_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}

    await check_urls(citations)
    refs_md = generate_references_markdown(citations)

    logger.info(
        "citation_management_complete",
        unique_sources=len(citations),
        sections_renumbered=len(updated_drafts),
    )

    return {
        "section_drafts": updated_drafts,
        "global_citations": [c.model_dump() for c in citations],
        "references_markdown": refs_md,
    }
