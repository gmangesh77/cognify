"""SQLAlchemy table models for PostgreSQL persistence."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin

__all__ = [
    "TopicRow",
    "ResearchSessionRow",
    "AgentStepRow",
    "LlmCallRow",
    "ArticleDraftRow",
    "CanonicalArticleRow",
    "DomainConfigRow",
    "ApiKeyRow",
    "LlmConfigRow",
    "SeoDefaultsRow",
    "GeneralConfigRow",
    "ImageAssetTagRow",
    "SectionVersionRow",
    "PublicationRow",
]


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
        PG_UUID(as_uuid=True),
        ForeignKey("topics.id"),
        nullable=True,
        index=True,
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
    target_audience: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_angle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    topic_description_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    structural_diagram_mode: Mapped[str] = mapped_column(
        String(20), default="illustration", server_default="illustration"
    )
    require_outline_approval: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )

    steps: Mapped[list["AgentStepRow"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AgentStepRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_steps"

    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("research_sessions.id"),
        index=True,
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


class LlmCallRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "llm_calls"

    step_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_steps.id"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("research_sessions.id"),
        index=True,
    )
    call_name: Mapped[str] = mapped_column(String(100))
    model_name: Mapped[str] = mapped_column(String(100))
    prompt_messages: Mapped[list] = mapped_column(JSONB, default=list)
    response_content: Mapped[str] = mapped_column(Text, default="")
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ArticleDraftRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "article_drafts"

    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("research_sessions.id"),
        index=True,
    )
    topic_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("topics.id"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30))
    total_word_count: Mapped[int] = mapped_column(Integer, default=0)
    references_markdown: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    article_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_articles.id"),
        nullable=True,
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


class DomainConfigRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "domain_configs"

    name: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    trend_sources: Mapped[list] = mapped_column(JSONB, default=list)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    article_count: Mapped[int] = mapped_column(Integer, default=0)


class ApiKeyRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "api_keys"

    service: Mapped[str] = mapped_column(String(50), index=True)
    encrypted_key: Mapped[str] = mapped_column(String(2000))
    masked_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")


class LlmConfigRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "llm_configs"

    primary_model: Mapped[str] = mapped_column(String(100))
    drafting_model: Mapped[str] = mapped_column(String(100))
    image_generation: Mapped[str] = mapped_column(String(100))
    # Phase 2 visuals UX — provider key (e.g. "dalle_3", "gemini_flash")
    # honored by image_render_node at render time. `image_model` is
    # optional; null means "use the provider's default model".
    image_provider: Mapped[str] = mapped_column(
        String(60), default="dalle_3", server_default="dalle_3", nullable=False
    )
    image_model: Mapped[str | None] = mapped_column(String(120), nullable=True)


class SeoDefaultsRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "seo_defaults"

    auto_meta_tags: Mapped[bool] = mapped_column(Boolean, default=True)
    keyword_optimization: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_cover_images: Mapped[bool] = mapped_column(Boolean, default=True)
    include_citations: Mapped[bool] = mapped_column(Boolean, default=True)
    human_review_before_publish: Mapped[bool] = mapped_column(Boolean, default=True)


class GeneralConfigRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "general_configs"

    article_length_target: Mapped[str] = mapped_column(String(50))
    content_tone: Mapped[str] = mapped_column(String(50))
    # VISUAL-010 / Phase 7 — default audience persona for the image
    # planner. Backfilled to "general_business" by the migration.
    default_audience_persona: Mapped[str] = mapped_column(
        String(60),
        default="general_business",
        nullable=False,
        server_default="general_business",
    )


class ImageAssetTagRow(Base, UUIDMixin, TimestampMixin):
    """User-curated tags on rendered image assets.

    Phase 7 / VISUAL-010 — lets editors mark a rendered asset as
    "save for re-use" with one or more style tokens (e.g. `hero_v2`,
    `cognify_gallery:engineering`). The Saved Asset Gallery merges
    these rows with the JSONB-derived feed in
    `services.visuals.saved_gallery`.

    Each (article_id, spec_id, tag) tuple is unique so the same asset
    can carry multiple tags but never duplicates.
    """

    __tablename__ = "image_asset_tags"

    article_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_articles.id"),
        nullable=False,
        index=True,
    )
    spec_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "spec_id",
            "tag",
            name="uq_image_asset_tag_unique",
        ),
    )


class SectionVersionRow(Base, UUIDMixin, TimestampMixin):
    """Append-only audit log of section-level edits (VISUAL-011 / Phase 8).

    Each row captures one rewrite, manual save, or restore. The active
    section state still lives on `canonical_articles.body_markdown` —
    this table is a sidecar for history + restore + auditing only.
    `section_id` is the f"{article_id}:{section_index}" string the
    handoff brief specifies.
    """

    __tablename__ = "section_versions"

    article_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_articles.id"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)


class PublicationRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "publications"

    article_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_articles.id"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seo_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_history: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "platform",
            name="uq_publication_article_platform",
        ),
    )
