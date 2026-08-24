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
    async def find_latest_by_session(self, session_id: UUID) -> ArticleDraft | None: ...
    async def find_by_article_id(self, article_id: UUID) -> ArticleDraft | None: ...


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

    async def find_latest_by_session(self, session_id: UUID) -> ArticleDraft | None:
        candidates = [d for d in self._store.values() if d.session_id == session_id]
        if not candidates:
            return None
        return max(candidates, key=lambda d: d.created_at)

    async def find_by_article_id(self, article_id: UUID) -> ArticleDraft | None:
        """Newest draft stamped with `article_id` (set by store_article)."""
        candidates = [d for d in self._store.values() if d.article_id == article_id]
        if not candidates:
            return None
        return max(candidates, key=lambda d: d.created_at)


class ArticleRepository(Protocol):
    async def create(self, article: CanonicalArticle) -> CanonicalArticle: ...
    async def get(self, article_id: UUID) -> CanonicalArticle | None: ...
    async def find_by_session(self, session_id: UUID) -> CanonicalArticle | None: ...
    async def append_visual(
        self,
        article_id: UUID,
        visual: ImageAsset,
    ) -> CanonicalArticle | None: ...
    async def update_metadata(
        self,
        article_id: UUID,
        fields: dict[str, object],
    ) -> CanonicalArticle | None: ...


class InMemoryArticleRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, CanonicalArticle] = {}

    async def create(self, article: CanonicalArticle) -> CanonicalArticle:
        self._store[article.id] = article
        return article

    async def get(self, article_id: UUID) -> CanonicalArticle | None:
        return self._store.get(article_id)

    async def find_by_session(self, session_id: UUID) -> CanonicalArticle | None:
        for article in self._store.values():
            if article.provenance.research_session_id == session_id:
                return article
        return None

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

    async def update_metadata(
        self,
        article_id: UUID,
        fields: dict[str, object],
    ) -> CanonicalArticle | None:
        existing = self._store.get(article_id)
        if existing is None:
            return None
        allowed = {k: v for k, v in fields.items() if k in ("title", "subtitle", "seo")}
        updated = existing.model_copy(update=allowed)
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
