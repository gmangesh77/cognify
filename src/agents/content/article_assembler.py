"""Assembles a CanonicalArticle from completed pipeline outputs.

Pure function — no LLM calls, no I/O. Takes an ArticleDraft with all
pipeline stages complete and produces the frozen CanonicalArticle that
the publishing pipeline consumes.
"""

import structlog
from pydantic import ValidationError

from src.models.content import CanonicalArticle, Citation, ContentType, ImageAsset
from src.models.content_pipeline import ArticleDraft, SectionDraft
from src.models.research import TopicInput

logger = structlog.get_logger()

_MIN_WORD_COUNT = 1500
_MIN_CITATIONS = 5


def assemble_canonical_article(
    draft: ArticleDraft,
    topic: TopicInput,
    visuals: list[ImageAsset] | None = None,
) -> CanonicalArticle:
    """Build a CanonicalArticle from a completed ArticleDraft."""
    seo_result = draft.seo_result
    assert seo_result is not None  # noqa: S101

    citations = _transform_citations(draft.global_citations)
    body = _compile_body(draft.section_drafts, draft.references_markdown)
    _validate_assembly(body, citations)

    try:
        article = CanonicalArticle(
            title=draft.outline.title if draft.outline else topic.title,
            subtitle=draft.outline.subtitle if draft.outline else None,
            body_markdown=body,
            summary=seo_result.summary,
            key_claims=seo_result.key_claims,
            content_type=ContentType(
                draft.outline.content_type if draft.outline else "article",
            ),
            seo=seo_result.seo,
            citations=citations,
            visuals=visuals if visuals is not None else [],
            authors=["Cognify"],
            domain=topic.domain,
            provenance=seo_result.provenance,
            ai_generated=True,
        )
    except ValidationError as exc:
        msg = f"CanonicalArticle validation failed: {exc}"
        raise ValueError(msg) from exc

    word_count = len(body.split())
    logger.info(
        "article_assembled",
        article_id=str(article.id),
        title=article.title,
        word_count=word_count,
        citation_count=len(citations),
    )
    return article


def _transform_citations(
    global_citations: list[dict[str, object]],
) -> list[Citation]:
    """Deserialise raw citation dicts into Citation models."""
    return [Citation.model_validate(c) for c in global_citations]


def _strip_leading_heading(body: str) -> str:
    """Remove leading markdown heading if present (LLM often duplicates it)."""
    stripped = body.lstrip()
    if stripped.startswith("#"):
        # Remove the first line if it's a heading
        first_newline = stripped.find("\n")
        if first_newline != -1:
            return stripped[first_newline + 1:].lstrip("\n")
    return body


def _compile_body(
    sections: list[SectionDraft] | list[dict[str, object]],
    references_md: str,
) -> str:
    """Concatenate section drafts with H2 headings and a references tail."""
    parsed = [
        s if isinstance(s, SectionDraft) else SectionDraft.model_validate(s)
        for s in sections
    ]
    sorted_sections = sorted(parsed, key=lambda s: s.section_index)
    parts = [
        f"## {s.title}\n\n{_strip_leading_heading(s.body_markdown)}"
        for s in sorted_sections
    ]
    if references_md:
        parts.append(references_md)
    return "\n\n".join(parts)


def _validate_assembly(
    body: str,
    citations: list[Citation],
) -> None:
    """Warn if minimum thresholds are not met."""
    word_count = len(body.split())
    if word_count < _MIN_WORD_COUNT:
        logger.warning(
            "article_below_word_threshold",
            word_count=word_count,
            minimum=_MIN_WORD_COUNT,
        )
    if len(citations) < _MIN_CITATIONS:
        logger.warning(
            "article_below_citation_threshold",
            citation_count=len(citations),
            minimum=_MIN_CITATIONS,
            hint="RAG retriever may be unavailable.",
        )
