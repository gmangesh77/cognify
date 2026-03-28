"""Content service — bridges API to the content pipeline.

Loads research findings, runs the content pipeline graph,
and manages ArticleDraft records.
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog

from src.agents.content.pipeline import ContentGraphDeps, build_content_graph
from src.api.errors import NotFoundError
from src.models.content import CanonicalArticle
from src.models.content_pipeline import (
    ArticleDraft,
    ArticleOutline,
    DraftStatus,
    SEOResult,
)
from src.models.research import FacetFindings, TopicInput
from src.models.research_db import ResearchSession
from src.services.content_finalize import (
    build_article,
    store_article,
    validate_finalize_ready,
)
from src.services.content_finalize import (
    get_article as _get_article,
)
from src.services.content_repositories import (
    ArticleDraftRepository,
    ArticleRepository,
    ContentDeps,
    ContentRepositories,
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
    ResearchSessionReader,
    aggregate_citations,
)

logger = structlog.get_logger()

# Re-export for backward compatibility
__all__ = [
    "ArticleDraftRepository",
    "ArticleRepository",
    "ContentDeps",
    "ContentRepositories",
    "ContentService",
    "InMemoryArticleDraftRepository",
    "InMemoryArticleRepository",
    "ResearchSessionReader",
]


class ContentService:
    def __init__(
        self,
        repos: ContentRepositories,
        deps: ContentDeps,
        step_repo: object | None = None,
    ) -> None:
        self._repos = repos
        self._deps = deps
        self._step_repo = step_repo

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

    async def finalize_article(self, draft_id: UUID) -> CanonicalArticle:
        """Assemble CanonicalArticle from a completed draft."""
        draft = await self.get_draft(draft_id)
        validate_finalize_ready(draft)
        session = await self._load_session(draft.session_id)
        topic = self._build_topic_input(session)
        article = build_article(draft, topic)
        return await store_article(self._repos, draft, article)

    async def generate_full_article(
        self, session_id: UUID,
    ) -> CanonicalArticle:
        """Run the full content pipeline in a single graph invocation."""
        logger.info("full_article_pipeline_started", session_id=str(session_id))
        session = await self._load_session(session_id)
        findings = self._reconstruct_findings(session)
        topic = self._build_topic_input(session)

        # Single graph run: outline → queries → draft → validate →
        # citations → humanize → SEO → charts → diagrams
        content_deps = None
        if self._step_repo is not None:
            content_deps = ContentGraphDeps(
                step_repo=self._step_repo,  # type: ignore[arg-type]
                session_id=session_id,
            )
        graph = build_content_graph(
            self._require_llm(),
            self._deps.retriever,
            self._deps.settings,
            deps=content_deps,
        )
        result: dict[str, object] = await graph.ainvoke(
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
        # Only fail if outline generation itself failed
        if result.get("outline") is None:
            raise ValueError(result.get("error", "Content pipeline failed"))
        if result["status"] == "failed":
            logger.warning(
                "content_pipeline_partial_failure",
                error=str(result.get("error", "")),
                hint="Continuing with available outputs.",
            )

        # Extract outline
        outline = result["outline"]
        if not isinstance(outline, ArticleOutline):
            outline = ArticleOutline.model_validate(outline)
        logger.info("outline_generated", section_count=len(outline.sections))

        # Store draft with all pipeline outputs
        draft = ArticleDraft(
            session_id=session.id,
            topic_id=session.topic_id,
            outline=outline,
            status=DraftStatus.DRAFT_COMPLETE,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        draft = await self._repos.drafts.create(draft)

        # Update with section drafts, citations, SEO, visuals
        seo_result = result.get("seo_result")
        if seo_result is not None and not isinstance(seo_result, SEOResult):
            seo_result = SEOResult.model_validate(seo_result)
        if seo_result is None:
            from src.models.content import Provenance, SEOMetadata
            seo_result = SEOResult(
                seo=SEOMetadata(
                    title=outline.title[:70],
                    description=(
                        outline.subtitle[:170]
                        if outline.subtitle
                        else outline.title[:170]
                    ),
                    keywords=[],
                ),
                summary=outline.subtitle or outline.title,
                key_claims=[],
                ai_disclosure="This article was generated by AI.",
                provenance=Provenance(
                    primary_model=(
                        settings.primary_model_name if settings else "unknown"
                    ),
                    drafting_model=(
                        settings.drafting_model_name if settings else "unknown"
                    ),
                    embedding_model=settings.embedding_model if settings else "unknown",
                    embedding_version=settings.embedding_version if settings else "v1",
                ),
            )
            logger.warning("seo_fallback_used", title=outline.title)
        raw_drafts = result.get("section_drafts", [])
        drafts_list = list(raw_drafts) if isinstance(raw_drafts, list) else []
        citations = aggregate_citations(drafts_list)

        # Serialize Pydantic objects for JSONB storage (datetime → ISO string)
        def _jsonable(items: list[object]) -> list[object]:
            return [
                i.model_dump(mode="json") if hasattr(i, "model_dump") else i
                for i in items
            ]

        updated = draft.model_copy(
            update={
                "section_drafts": _jsonable(drafts_list),
                "citations": _jsonable(citations),
                "total_word_count": result.get("total_word_count", 0),
                "seo_result": seo_result,
                "global_citations": _jsonable(
                    list(result.get("global_citations") or [])
                ),
                "references_markdown": str(result.get("references_markdown", "")),
                "visuals": _jsonable(list(result.get("visuals") or [])),
            }
        )
        draft = await self._repos.drafts.update(updated)
        logger.info(
            "draft_stored",
            draft_id=str(draft.id),
            word_count=draft.total_word_count,
            sections=len(drafts_list),
        )

        # Finalize → CanonicalArticle
        article = build_article(draft, topic)
        article = await store_article(self._repos, draft, article)
        logger.info(
            "article_finalized",
            article_id=str(article.id),
            title=article.title,
        )
        return article

    async def get_article(self, article_id: UUID) -> CanonicalArticle:
        """Retrieve a stored CanonicalArticle by ID."""
        return await _get_article(self._repos, article_id)

    async def get_draft(self, draft_id: UUID) -> ArticleDraft:
        draft = await self._repos.drafts.get(draft_id)
        if draft is None:
            raise NotFoundError(f"Draft {draft_id} not found")
        return draft

    def _validate_draft_ready(self, draft: ArticleDraft) -> None:
        if self._deps.retriever is None:
            logger.warning(
                "drafting_without_retriever",
                hint="RAG context unavailable, drafting from findings only",
            )
        if draft.status != DraftStatus.OUTLINE_COMPLETE:
            msg = f"Draft {draft.id} not ready for drafting"
            raise ValueError(msg)

    async def _load_session(self, session_id: UUID) -> ResearchSession:
        session = await self._repos.research.get(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id} not found")
        valid = ("complete", "generating_article", "article_complete", "article_failed")
        if session.status not in valid:
            msg = f"Session {session_id} is not complete (status={session.status})"
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

    def _require_llm(self) -> "BaseChatModel":
        if self._deps.llm is None:
            msg = "LLM not configured. Set COGNIFY_ANTHROPIC_API_KEY."
            raise ValueError(msg)
        return self._deps.llm

    async def _run_pipeline(
        self, topic: TopicInput, findings: list[FacetFindings]
    ) -> ArticleOutline:
        graph = build_content_graph(self._require_llm(), settings=self._deps.settings)
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
        graph = build_content_graph(
            self._require_llm(), self._deps.retriever, self._deps.settings
        )
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
        citations = aggregate_citations(drafts)
        seo_result = result.get("seo_result")
        if seo_result is not None and not isinstance(seo_result, SEOResult):
            seo_result = SEOResult.model_validate(seo_result)
        updated = draft.model_copy(
            update={
                "section_drafts": drafts,
                "citations": citations,
                "total_word_count": result.get("total_word_count", 0),
                "seo_result": seo_result,
                "global_citations": list(result.get("global_citations") or []),  # type: ignore[call-overload]
                "references_markdown": str(result.get("references_markdown", "")),
                "visuals": list(result.get("visuals") or []),
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
