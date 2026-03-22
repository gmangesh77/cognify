"""SQLAlchemy table models for PostgreSQL persistence."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin


class TopicRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "topics"

    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(50))
    external_url: Mapped[str] = mapped_column(String(2000), default="")
    trend_score: Mapped[float] = mapped_column(Float)
    velocity: Mapped[float] = mapped_column(Float, default=0.0)
    domain: Mapped[str] = mapped_column(String(100), index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    domain_keywords: Mapped[dict] = mapped_column(JSONB, default=list)
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, default=1)


class ResearchSessionRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "research_sessions"

    topic_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="planning", index=True)
    round_count: Mapped[int] = mapped_column(Integer, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_count: Mapped[int] = mapped_column(Integer, default=0)
    topic_title: Mapped[str] = mapped_column(String(500))
    topic_description: Mapped[str] = mapped_column(Text, default="")
    topic_domain: Mapped[str] = mapped_column(String(100), default="")
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    findings_data: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    steps: Mapped[list["AgentStepRow"]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
    )


class AgentStepRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_steps"

    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("research_sessions.id"), index=True,
    )
    step_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    session: Mapped["ResearchSessionRow"] = relationship(back_populates="steps")


class ArticleDraftRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "article_drafts"

    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("research_sessions.id"), index=True,
    )
    topic_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("topics.id"), index=True,
    )
    status: Mapped[str] = mapped_column(String(30))
    total_word_count: Mapped[int] = mapped_column(Integer, default=0)
    references_markdown: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    article_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("canonical_articles.id"), nullable=True,
    )
    outline: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    section_drafts: Mapped[list] = mapped_column(JSONB, default=list)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    seo_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    global_citations: Mapped[list] = mapped_column(JSONB, default=list)
    visuals: Mapped[list] = mapped_column(JSONB, default=list)


class CanonicalArticleRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "canonical_articles"

    title: Mapped[str] = mapped_column(String(500))
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_markdown: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(20))
    domain: Mapped[str] = mapped_column(String(100))
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    key_claims: Mapped[list] = mapped_column(JSONB, default=list)
    seo: Mapped[dict] = mapped_column(JSONB)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    visuals: Mapped[list] = mapped_column(JSONB, default=list)
    provenance: Mapped[dict] = mapped_column(JSONB)
    authors: Mapped[list] = mapped_column(JSONB, default=list)
