"""Finalization helpers for ContentService.

Validates a draft is ready, assembles the CanonicalArticle, and
persists both the article and the updated draft status. Extracted
from content.py to keep file sizes under 200 lines.
"""

from uuid import UUID

import structlog

from src.agents.content.article_assembler import assemble_canonical_article
from src.api.errors import NotFoundError
from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft, DraftStatus
from src.models.research import TopicInput
from src.services.content_repositories import ContentRepositories

logger = structlog.get_logger()


def validate_finalize_ready(draft: ArticleDraft) -> None:
    """Raise ValueError if draft is not ready for finalization."""
    if draft.status != DraftStatus.DRAFT_COMPLETE:
        msg = f"Draft {draft.id} not ready for finalization"
        raise ValueError(msg)
    if draft.seo_result is None:
        msg = f"Draft {draft.id}: SEO optimization not completed"
        raise ValueError(msg)


async def store_article(
    repos: ContentRepositories,
    draft: ArticleDraft,
    article: CanonicalArticle,
) -> CanonicalArticle:
    """Persist article and update draft status to COMPLETE."""
    stored = await repos.articles.create(article)
    updated = draft.model_copy(
        update={
            "status": DraftStatus.COMPLETE,
            "article_id": article.id,
        },
    )
    await repos.drafts.update(updated)
    logger.info(
        "article_finalization_complete",
        draft_id=str(draft.id),
        article_id=str(article.id),
    )
    return stored


async def get_article(
    repos: ContentRepositories,
    article_id: UUID,
) -> CanonicalArticle:
    """Retrieve a stored CanonicalArticle by ID."""
    article = await repos.articles.get(article_id)
    if article is None:
        raise NotFoundError(f"Article {article_id} not found")
    return article


def build_article(
    draft: ArticleDraft,
    topic: TopicInput,
) -> CanonicalArticle:
    """Assemble a CanonicalArticle from a finalized draft."""
    return assemble_canonical_article(draft, topic)
