"""PostgreSQL repository implementations.

Implements the repository protocols from services/research.py and
services/content_repositories.py using SQLAlchemy async sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from src.api.schemas.topics import PersistedTopic, RankedTopic

from src.db.tables import (
    AgentStepRow,
    ArticleDraftRow,
    CanonicalArticleRow,
    ResearchSessionRow,
    TopicRow,
)
from src.models.content import (
    CanonicalArticle,
    Citation,
    ContentType,
    ImageAsset,
    Provenance,
    SEOMetadata,
)
from src.models.content_pipeline import (
    ArticleDraft,
    ArticleOutline,
    CitationRef,
    DraftStatus,
    SectionDraft,
    SEOResult,
)
from src.models.research import TopicInput
from src.models.research_db import AgentStep, ResearchSession


class PgResearchSessionRepository:
    """PostgreSQL-backed research session repository."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, session: ResearchSession) -> ResearchSession:
        async with self._sf() as db:
            row = ResearchSessionRow(
                id=session.id,
                topic_id=session.topic_id,
                status=session.status,
                round_count=session.round_count,
                findings_count=session.findings_count,
                indexed_count=session.indexed_count,
                topic_title=session.topic_title,
                topic_description=session.topic_description,
                topic_domain=session.topic_domain,
                duration_seconds=session.duration_seconds,
                started_at=session.started_at,
                completed_at=session.completed_at,
                agent_plan=session.agent_plan or {},
                findings_data=session.findings_data or [],
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    async def get(self, session_id: UUID) -> ResearchSession | None:
        async with self._sf() as db:
            row = await db.get(ResearchSessionRow, session_id)
            if row is None:
                return None
            return self._to_model(row)

    async def update(self, session: ResearchSession) -> ResearchSession:
        async with self._sf() as db:
            row = await db.get(ResearchSessionRow, session.id)
            if row is None:
                raise ValueError(f"ResearchSession {session.id} not found")
            row.status = session.status
            row.round_count = session.round_count
            row.findings_count = session.findings_count
            row.indexed_count = session.indexed_count
            row.duration_seconds = session.duration_seconds
            row.completed_at = session.completed_at
            row.agent_plan = session.agent_plan or {}
            row.findings_data = session.findings_data or []
            row.topic_title = session.topic_title
            row.topic_description = session.topic_description
            row.topic_domain = session.topic_domain
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    async def list(
        self, status: str | None, page: int, size: int
    ) -> tuple[list[ResearchSession], int]:
        async with self._sf() as db:
            query = select(ResearchSessionRow)
            count_query = select(func.count()).select_from(ResearchSessionRow)
            if status:
                # Group related statuses for filtering
                status_groups: dict[str, list[str]] = {
                    "article_complete": ["article_complete", "complete"],
                    "failed": ["failed", "article_failed"],
                    "generating_article": ["generating_article"],
                    "in_progress": ["in_progress", "researching", "evaluating"],
                }
                statuses = status_groups.get(status, [status])
                query = query.where(ResearchSessionRow.status.in_(statuses))
                count_query = count_query.where(
                    ResearchSessionRow.status.in_(statuses)
                )
            total_result = await db.execute(count_query)
            total = total_result.scalar_one()
            offset = (page - 1) * size
            query = query.offset(offset).limit(size)
            result = await db.execute(query)
            rows = result.scalars().all()
            return [self._to_model(r) for r in rows], total

    @staticmethod
    def _to_model(row: ResearchSessionRow) -> ResearchSession:
        return ResearchSession(
            id=row.id,
            topic_id=row.topic_id,
            status=row.status,
            round_count=row.round_count,
            findings_count=row.findings_count,
            indexed_count=row.indexed_count,
            topic_title=row.topic_title,
            topic_description=row.topic_description,
            topic_domain=row.topic_domain,
            duration_seconds=row.duration_seconds,
            started_at=row.started_at,
            completed_at=row.completed_at,
            agent_plan=row.agent_plan or {},
            findings_data=row.findings_data or [],
        )


class PgAgentStepRepository:
    """PostgreSQL-backed agent step repository."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, step: AgentStep) -> AgentStep:
        async with self._sf() as db:
            row = AgentStepRow(
                id=step.id,
                session_id=step.session_id,
                step_name=step.step_name,
                status=step.status,
                input_data=step.input_data or {},
                output_data=step.output_data or {},
                duration_ms=step.duration_ms,
                started_at=step.started_at,
                completed_at=step.completed_at,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    async def update(self, step: AgentStep) -> AgentStep:
        async with self._sf() as db:
            row = await db.get(AgentStepRow, step.id)
            if row is None:
                raise ValueError(f"AgentStep {step.id} not found")
            row.status = step.status
            row.output_data = step.output_data or {}
            row.duration_ms = step.duration_ms
            row.completed_at = step.completed_at
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    async def list_by_session(self, session_id: UUID) -> list[AgentStep]:
        async with self._sf() as db:
            query = select(AgentStepRow).where(
                AgentStepRow.session_id == session_id
            )
            result = await db.execute(query)
            rows = result.scalars().all()
            return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(row: AgentStepRow) -> AgentStep:
        return AgentStep(
            id=row.id,
            session_id=row.session_id,
            step_name=row.step_name,
            status=row.status,
            input_data=row.input_data or {},
            output_data=row.output_data or {},
            duration_ms=row.duration_ms,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )


class PgTopicRepository:
    """PostgreSQL-backed topic repository."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def exists(self, topic_id: UUID) -> bool:
        async with self._sf() as db:
            row = await db.get(TopicRow, topic_id)
            return row is not None

    async def get(self, topic_id: UUID) -> TopicInput | None:
        async with self._sf() as db:
            row = await db.get(TopicRow, topic_id)
            if row is None:
                return None
            return self._to_model(row)

    async def _seed_async(self, topic: TopicInput) -> None:
        """Seed a topic for testing."""
        async with self._sf() as db:
            existing = await db.get(TopicRow, topic.id)
            if existing is not None:
                return
            row = TopicRow(
                id=topic.id,
                title=topic.title,
                description=topic.description,
                domain=topic.domain,
                source="seed",
                trend_score=0.0,
                discovered_at=__import__(
                    "datetime"
                ).datetime.now(__import__("datetime").timezone.utc),
            )
            db.add(row)
            await db.commit()

    async def create_from_ranked(
        self,
        topic: RankedTopic,
        domain: str,
    ) -> UUID:
        """Insert a new topic from a ranked scan result."""
        topic_id = uuid4()
        async with self._sf() as session:
            row = TopicRow(
                id=topic_id,
                title=topic.title,
                description=topic.description,
                source=topic.source,
                external_url=topic.external_url,
                trend_score=topic.trend_score,
                velocity=topic.velocity,
                domain=domain,
                discovered_at=topic.discovered_at,
                domain_keywords=topic.domain_keywords,
                composite_score=topic.composite_score,
                rank=topic.rank,
                source_count=topic.source_count,
            )
            session.add(row)
            await session.commit()
        return topic_id

    async def update_from_scan(
        self,
        topic_id: UUID,
        topic: RankedTopic,
    ) -> None:
        """Update an existing topic with fresh scan data."""
        async with self._sf() as session:
            row = await session.get(TopicRow, topic_id)
            if row is None:
                return
            row.trend_score = topic.trend_score
            row.velocity = topic.velocity
            row.discovered_at = topic.discovered_at
            row.composite_score = topic.composite_score
            row.rank = topic.rank
            row.source_count = row.source_count + 1
            await session.commit()

    async def list_by_domain(
        self,
        domain: str,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[PersistedTopic], int]:
        """List topics by domain, ordered by composite_score.

        Pass an empty string for *domain* to return topics across all domains.
        """
        from src.api.schemas.topics import PersistedTopic
        async with self._sf() as session:
            count_q = select(func.count()).select_from(TopicRow)
            q = select(TopicRow).order_by(
                TopicRow.created_at.desc(),
                TopicRow.composite_score.desc().nulls_last(),
            )
            if domain:
                count_q = count_q.where(TopicRow.domain == domain)
                q = q.where(TopicRow.domain == domain)
            total = (await session.execute(count_q)).scalar_one()
            q = q.offset((page - 1) * size).limit(size)
            rows = (await session.execute(q)).scalars().all()
            items = [
                PersistedTopic(
                    id=r.id,
                    title=r.title,
                    description=r.description,
                    source=r.source,
                    external_url=r.external_url,
                    trend_score=r.trend_score,
                    velocity=r.velocity,
                    domain=r.domain,
                    discovered_at=r.discovered_at,
                    composite_score=r.composite_score,
                    rank=r.rank,
                    source_count=r.source_count,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]
            return items, total

    @staticmethod
    def _to_model(row: TopicRow) -> TopicInput:
        return TopicInput(
            id=row.id,
            title=row.title,
            description=row.description,
            domain=row.domain,
        )


class PgArticleDraftRepository:
    """PostgreSQL-backed article draft repository."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, draft: ArticleDraft) -> ArticleDraft:
        async with self._sf() as db:
            row = ArticleDraftRow(
                id=draft.id,
                session_id=draft.session_id,
                topic_id=draft.topic_id,
                status=draft.status.value,
                total_word_count=draft.total_word_count,
                references_markdown=draft.references_markdown,
                created_at=draft.created_at,
                completed_at=draft.completed_at,
                article_id=draft.article_id,
                outline=(
                    draft.outline.model_dump(mode="json")
                    if draft.outline else None
                ),
                section_drafts=[
                    s.model_dump(mode="json")
                    for s in draft.section_drafts
                ],
                citations=[
                    c.model_dump(mode="json")
                    for c in draft.citations
                ],
                seo_result=(
                    draft.seo_result.model_dump(mode="json")
                    if draft.seo_result else None
                ),
                global_citations=draft.global_citations,
                visuals=[v.model_dump(mode="json") for v in draft.visuals],
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    async def get(self, draft_id: UUID) -> ArticleDraft | None:
        async with self._sf() as db:
            row = await db.get(ArticleDraftRow, draft_id)
            if row is None:
                return None
            return self._to_model(row)

    async def update(self, draft: ArticleDraft) -> ArticleDraft:
        async with self._sf() as db:
            row = await db.get(ArticleDraftRow, draft.id)
            if row is None:
                raise ValueError(f"ArticleDraft {draft.id} not found")
            row.status = draft.status.value
            row.total_word_count = draft.total_word_count
            row.references_markdown = draft.references_markdown
            row.completed_at = draft.completed_at
            row.article_id = draft.article_id
            row.outline = (
                draft.outline.model_dump(mode="json") if draft.outline else None
            )
            row.section_drafts = [
                s.model_dump(mode="json") for s in draft.section_drafts
            ]
            row.citations = [c.model_dump(mode="json") for c in draft.citations]
            row.seo_result = (
                draft.seo_result.model_dump(mode="json") if draft.seo_result else None
            )
            row.global_citations = draft.global_citations
            row.visuals = [v.model_dump(mode="json") for v in draft.visuals]
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    @staticmethod
    def _to_model(row: ArticleDraftRow) -> ArticleDraft:
        outline = (
            ArticleOutline.model_validate(row.outline)
            if row.outline
            else None
        )
        section_drafts = [
            SectionDraft.model_validate(s) for s in (row.section_drafts or [])
        ]
        citations = [
            CitationRef.model_validate(c) for c in (row.citations or [])
        ]
        seo_result = (
            SEOResult.model_validate(row.seo_result)
            if row.seo_result
            else None
        )
        visuals = [
            ImageAsset.model_validate(v) for v in (row.visuals or [])
        ]
        return ArticleDraft(
            id=row.id,
            session_id=row.session_id,
            topic_id=row.topic_id,
            status=DraftStatus(row.status),
            total_word_count=row.total_word_count,
            references_markdown=row.references_markdown,
            created_at=row.created_at,
            completed_at=row.completed_at,
            article_id=row.article_id,
            outline=outline,
            section_drafts=section_drafts,
            citations=citations,
            seo_result=seo_result,
            global_citations=row.global_citations or [],
            visuals=visuals,
        )


class PgArticleRepository:
    """PostgreSQL-backed canonical article repository."""

    def __init__(self, sf: async_sessionmaker[AsyncSession]) -> None:
        self._sf = sf

    async def create(self, article: CanonicalArticle) -> CanonicalArticle:
        async with self._sf() as db:
            row = CanonicalArticleRow(
                id=article.id,
                title=article.title,
                subtitle=article.subtitle,
                body_markdown=article.body_markdown,
                summary=article.summary,
                content_type=article.content_type.value,
                domain=article.domain,
                ai_generated=article.ai_generated,
                generated_at=article.generated_at,
                key_claims=list(article.key_claims),
                seo=article.seo.model_dump(mode="json"),
                citations=[c.model_dump(mode="json") for c in article.citations],
                visuals=[v.model_dump(mode="json") for v in article.visuals],
                provenance=article.provenance.model_dump(mode="json"),
                authors=list(article.authors),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return self._to_model(row)

    async def get(self, article_id: UUID) -> CanonicalArticle | None:
        async with self._sf() as db:
            row = await db.get(CanonicalArticleRow, article_id)
            if row is None:
                return None
            return self._to_model(row)

    async def list(
        self, page: int = 1, size: int = 20,
    ) -> tuple[list[CanonicalArticle], int]:
        """List all articles, newest first."""
        async with self._sf() as session:
            count_q = select(func.count()).select_from(
                CanonicalArticleRow,
            )
            total = (await session.execute(count_q)).scalar_one()
            q = (
                select(CanonicalArticleRow)
                .order_by(CanonicalArticleRow.generated_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
            rows = (await session.execute(q)).scalars().all()
            return [self._to_model(r) for r in rows], total

    @staticmethod
    def _to_model(row: CanonicalArticleRow) -> CanonicalArticle:
        seo = SEOMetadata.model_validate(row.seo)
        citations = [Citation.model_validate(c) for c in (row.citations or [])]
        visuals = [ImageAsset.model_validate(v) for v in (row.visuals or [])]
        provenance = Provenance.model_validate(row.provenance)
        return CanonicalArticle(
            id=row.id,
            title=row.title,
            subtitle=row.subtitle,
            body_markdown=row.body_markdown,
            summary=row.summary,
            key_claims=row.key_claims or [],
            content_type=ContentType(row.content_type),
            seo=seo,
            citations=citations,
            visuals=visuals,
            authors=row.authors or [],
            domain=row.domain,
            generated_at=row.generated_at,
            provenance=provenance,
            ai_generated=row.ai_generated,
        )
