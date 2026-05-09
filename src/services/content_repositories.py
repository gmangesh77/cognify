"""Content repository protocols and in-memory implementations.

Extracted from content.py to keep file sizes under 200 lines.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from langchain_core.language_models import BaseChatModel

from src.config.settings import Settings
from src.models.content import CanonicalArticle, ImageAsset
from src.models.content_pipeline import ArticleDraft
from src.models.research_db import ResearchSession
from src.services.milvus_retriever import MilvusRetriever


class ArticleDraftRepository(Protocol):
    async def create(self, draft: ArticleDraft) -> ArticleDraft: ...
    async def get(self, draft_id: UUID) -> ArticleDraft | None: ...
    async def update(self, draft: ArticleDraft) -> ArticleDraft: ...


class ResearchSessionReader(Protocol):
    """Read-only access to research sessions."""

    async def get(self, session_id: UUID) -> ResearchSession | None: ...


class InMemoryArticleDraftRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, ArticleDraft] = {}

    async def create(self, draft: ArticleDraft) -> ArticleDraft:
        self._store[draft.id] = draft
        return draft

    async def get(self, draft_id: UUID) -> ArticleDraft | None:
        return self._store.get(draft_id)

    async def update(self, draft: ArticleDraft) -> ArticleDraft:
        self._store[draft.id] = draft
        return draft


class ArticleRepository(Protocol):
    async def create(self, article: CanonicalArticle) -> CanonicalArticle: ...
    async def get(self, article_id: UUID) -> CanonicalArticle | None: ...
    async def append_visual(
        self,
        article_id: UUID,
        visual: ImageAsset,
    ) -> CanonicalArticle | None: ...


class InMemoryArticleRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, CanonicalArticle] = {}

    async def create(self, article: CanonicalArticle) -> CanonicalArticle:
        self._store[article.id] = article
        return article

    async def get(self, article_id: UUID) -> CanonicalArticle | None:
        return self._store.get(article_id)

    async def append_visual(
        self,
        article_id: UUID,
        visual: ImageAsset,
    ) -> CanonicalArticle | None:
        existing = self._store.get(article_id)
        if existing is None:
            return None
        # CanonicalArticle is frozen — rebuild with the appended visual.
        updated = existing.model_copy(update={"visuals": [*existing.visuals, visual]})
        self._store[article_id] = updated
        return updated


@dataclass(frozen=True)
class ContentRepositories:
    drafts: ArticleDraftRepository
    research: ResearchSessionReader
    articles: ArticleRepository


@dataclass(frozen=True)
class ContentDeps:
    """Bundled dependencies for ContentService."""

    llm: BaseChatModel | None = None
    retriever: MilvusRetriever | None = None
    settings: Settings | None = None


def aggregate_citations(
    drafts: list[object],
) -> list[object]:
    """Collect unique citations from all section drafts by URL."""
    seen: dict[str, object] = {}
    for d in drafts:
        for c in getattr(d, "citations_used", []):
            if c.source_url not in seen:
                seen[c.source_url] = c
    return list(seen.values())
