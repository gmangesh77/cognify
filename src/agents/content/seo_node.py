"""SEO node factory for the content pipeline graph.

Separate from nodes.py to stay within the 200-line file limit.
Same factory pattern: closure over LLM and settings, returns an
async LangGraph node function.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.content.seo_optimizer import (
    AI_DISCLOSURE_TEXT,
    build_structured_data,
    generate_ai_discoverability,
    generate_seo_metadata,
)
from src.config.settings import Settings
from src.models.content import Provenance, SEOMetadata
from src.models.content_pipeline import (
    ArticleOutline,
    CitationRef,
    SEOResult,
    SectionDraft,
)

if TYPE_CHECKING:
    from src.agents.content.pipeline import ContentState

logger = structlog.get_logger()


def _coerce_outline(state: ContentState) -> ArticleOutline:
    """Extract and coerce outline from state."""
    outline = state["outline"]
    if not isinstance(outline, ArticleOutline):
        return ArticleOutline.model_validate(outline)
    return outline


def _coerce_drafts(state: ContentState) -> list[SectionDraft]:
    """Extract and coerce section drafts from state."""
    raw = state.get("section_drafts", [])
    return [
        d if isinstance(d, SectionDraft) else SectionDraft.model_validate(d)
        for d in raw
    ]


def _collect_citations(drafts: list[SectionDraft]) -> list[CitationRef]:
    """Deduplicate citations across all section drafts."""
    seen: set[str] = set()
    unique: list[CitationRef] = []
    for draft in drafts:
        for c in draft.citations_used:
            if c.source_url not in seen:
                seen.add(c.source_url)
                unique.append(c)
    return unique


def _build_provenance(state: ContentState, settings: Settings) -> Provenance:
    """Build Provenance from settings and session state."""
    return Provenance(
        research_session_id=state["session_id"],
        primary_model=settings.primary_model_name,
        drafting_model=settings.drafting_model_name,
        embedding_model=settings.embedding_model,
        embedding_version=settings.embedding_version,
    )


async def _run_seo(
    state: ContentState,
    llm: BaseChatModel,
    settings: Settings,
) -> dict[str, object]:
    """Core SEO node logic — extracted for < 20-line closures."""
    outline = _coerce_outline(state)
    drafts = _coerce_drafts(state)
    body_text = "\n\n".join(d.body_markdown for d in drafts)
    citations = _collect_citations(drafts)

    seo = await generate_seo_metadata(outline.title, body_text, llm)
    discover = await generate_ai_discoverability(drafts, citations, llm)

    provenance = _build_provenance(state, settings)
    structured = build_structured_data(
        seo, outline.title, datetime.now(UTC).isoformat(),
    )
    seo = seo.model_copy(update={"structured_data": structured})

    result = SEOResult(
        seo=seo,
        summary=discover.summary,
        key_claims=discover.key_claims,
        provenance=provenance,
        ai_disclosure=AI_DISCLOSURE_TEXT,
    )
    logger.info("seo_node_complete", title=seo.title)
    return {"seo_result": result}


def make_seo_node(llm: BaseChatModel, settings: Settings | None = None) -> Any:  # noqa: ANN401
    """Factory for the SEO optimization node."""
    resolved = settings or Settings()

    async def seo_node(state: ContentState) -> dict[str, object]:
        try:
            return await _run_seo(state, llm, resolved)
        except Exception as exc:
            logger.error("seo_node_failed", error=str(exc))
            return {"status": "failed", "error": str(exc)}

    return seo_node
