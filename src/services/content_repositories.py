"""Content repository protocols and in-memory implementations.

Extracted from content.py to keep file sizes under 200 lines.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from langchain_core.language_models import BaseChatModel

from src.config.settings import Settings
from src.models.content import CanonicalArticle
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


class InMemoryArticleRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, CanonicalArticle] = {}

    async def create(self, article: CanonicalArticle) -> CanonicalArticle:
        self._store[article.id] = article
        return article

    async def get(self, article_id: UUID) -> CanonicalArticle | None:
        return self._store.get(article_id)


@dataclass(frozen=True)
class ContentRepositories:
    drafts: ArticleDraftRepository
    research: ResearchSessionReader
    articles: ArticleRepository


@dataclass(frozen=True)
class ContentDeps:
    """Bundled dependencies for ContentService."""

    llm: BaseChatModel
    retriever: MilvusRetriever | None = None
    settings: Settings | None = None
