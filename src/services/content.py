"""Content service — bridges API to the content pipeline.

Loads research findings, runs the content pipeline graph,
and manages ArticleDraft records.
"""

from datetime import UTC, datetime
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
from src.services.content_repositories import (
    ArticleDraftRepository,
    ContentRepositories,
    InMemoryArticleDraftRepository,
    ResearchSessionReader,
)
from src.services.milvus_retriever import MilvusRetriever

logger = structlog.get_logger()

# Re-export for backward compatibility
__all__ = [
    "ArticleDraftRepository",
    "ContentRepositories",
    "ContentService",
    "InMemoryArticleDraftRepository",
    "ResearchSessionReader",
]


class ContentService:
    def __init__(
        self,
        repos: ContentRepositories,
        llm: BaseChatModel,
        retriever: MilvusRetriever | None = None,
    ) -> None:
        self._repos = repos
        self._llm = llm
        self._retriever = retriever

    async def generate_outline(self, session_id: UUID) -> ArticleDraft:
        session = await self._load_session(session_id)
        findings = self._reconstruct_findings(session)
        topic = self._build_topic_input(session)
        outline = await self._run_pipeline(topic, findings)
        return await self._store_draft(session, outline)

    async def draft_article(self, draft_id: UUID) -> ArticleDraft:
        """Load outline-complete draft, run section drafting."""
        draft = await self.get_draft(draft_id)
        self._validate_draft_ready(draft)
        session = await self._load_session(draft.session_id)
        findings = self._reconstruct_findings(session)
        topic = self._build_topic_input(session)
        result = await self._run_drafting(topic, findings, draft)
        return await self._store_drafted(draft, result)

    async def get_draft(self, draft_id: UUID) -> ArticleDraft:
        draft = await self._repos.drafts.get(draft_id)
        if draft is None:
            raise NotFoundError(f"Draft {draft_id} not found")
        return draft

    def _validate_draft_ready(self, draft: ArticleDraft) -> None:
        if self._retriever is None:
            msg = "retriever required for drafting"
            raise ValueError(msg)
        if draft.status != DraftStatus.OUTLINE_COMPLETE:
            msg = f"Draft {draft.id} not ready for drafting"
            raise ValueError(msg)

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
        outline = result["outline"]
        if not isinstance(outline, ArticleOutline):
            return ArticleOutline.model_validate(outline)
        return outline

    async def _run_drafting(
        self,
        topic: TopicInput,
        findings: list[FacetFindings],
        draft: ArticleDraft,
    ) -> dict[str, object]:
        """Run the content pipeline with existing outline."""
        graph = build_content_graph(self._llm, self._retriever)
        result: dict[str, object] = await graph.ainvoke(
            {
                "topic": topic,
                "research_plan": None,
                "findings": findings,
                "session_id": topic.id,
                "outline": draft.outline,
                "status": "outline_complete",
                "error": None,
            }
        )
        if result["status"] == "failed":
            raise ValueError(result.get("error", "Drafting failed"))
        return result

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

    async def _store_drafted(
        self,
        draft: ArticleDraft,
        result: dict[str, object],
    ) -> ArticleDraft:
        """Persist completed section drafts to the draft record."""
        raw_drafts = result.get("section_drafts", [])
        drafts: list[object] = list(raw_drafts) if isinstance(raw_drafts, list) else []
        citations = _aggregate_citations(drafts)
        updated = draft.model_copy(
            update={
                "section_drafts": drafts,
                "citations": citations,
                "total_word_count": result.get("total_word_count", 0),
                "status": DraftStatus.DRAFT_COMPLETE,
                "completed_at": datetime.now(UTC),
            }
        )
        logger.info(
            "article_drafting_complete",
            draft_id=str(draft.id),
            total_words=updated.total_word_count,
        )
        return await self._repos.drafts.update(updated)


def _aggregate_citations(
    drafts: list[object],
) -> list[object]:
    """Collect unique citations from all section drafts by URL."""
    seen: dict[str, object] = {}
    for d in drafts:
        for c in getattr(d, "citations_used", []):
            if c.source_url not in seen:
                seen[c.source_url] = c
    return list(seen.values())
