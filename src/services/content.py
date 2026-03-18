"""Content service — bridges API to the content pipeline.

Loads research findings, runs the content pipeline graph,
and manages ArticleDraft records.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import structlog
from langchain_core.language_models import BaseChatModel

from src.agents.content.pipeline import build_content_graph
from src.api.errors import NotFoundError
from src.models.content_pipeline import (
    ArticleDraft,
    ArticleOutline,
    DraftStatus,
)
from src.models.research import FacetFindings, TopicInput
from src.models.research_db import ResearchSession

logger = structlog.get_logger()


class ArticleDraftRepository(Protocol):
    async def create(self, draft: ArticleDraft) -> ArticleDraft: ...
    async def get(self, draft_id: UUID) -> ArticleDraft | None: ...


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


@dataclass(frozen=True)
class ContentRepositories:
    drafts: ArticleDraftRepository
    research: ResearchSessionReader


class ContentService:
    def __init__(self, repos: ContentRepositories, llm: BaseChatModel) -> None:
        self._repos = repos
        self._llm = llm

    async def generate_outline(self, session_id: UUID) -> ArticleDraft:
        session = await self._load_session(session_id)
        findings = self._reconstruct_findings(session)
        topic = self._build_topic_input(session)
        outline = await self._run_pipeline(topic, findings)
        return await self._store_draft(session, outline)

    async def get_draft(self, draft_id: UUID) -> ArticleDraft:
        draft = await self._repos.drafts.get(draft_id)
        if draft is None:
            raise NotFoundError(f"Draft {draft_id} not found")
        return draft

    async def _load_session(self, session_id: UUID) -> ResearchSession:
        session = await self._repos.research.get(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id} not found")
        if session.status != "complete":
            msg = f"Session {session_id} is not complete"
            raise ValueError(msg)
        return session

    def _reconstruct_findings(self, session: ResearchSession) -> list[FacetFindings]:
        return [FacetFindings.model_validate(f) for f in session.findings_data]

    def _build_topic_input(self, session: ResearchSession) -> TopicInput:
        return TopicInput(
            id=session.topic_id,
            title=session.topic_title or f"Topic {session.topic_id}",
            description=session.topic_description,
            domain=session.topic_domain,
        )

    async def _run_pipeline(
        self, topic: TopicInput, findings: list[FacetFindings]
    ) -> ArticleOutline:
        graph = build_content_graph(self._llm)
        result = await graph.ainvoke(
            {
                "topic": topic,
                "research_plan": None,
                "findings": findings,
                "session_id": topic.id,
                "outline": None,
                "status": "outline_generating",
                "error": None,
            }
        )
        if result["status"] == "failed":
            raise ValueError(result.get("error", "Outline generation failed"))
        return result["outline"]

    async def _store_draft(
        self, session: ResearchSession, outline: ArticleOutline
    ) -> ArticleDraft:
        draft = ArticleDraft(
            session_id=session.id,
            topic_id=session.topic_id,
            outline=outline,
            status=DraftStatus.OUTLINE_COMPLETE,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        logger.info(
            "outline_stored",
            draft_id=str(draft.id),
            session_id=str(session.id),
        )
        return await self._repos.drafts.create(draft)
