"""add personas + persona_samples, voice_persona_id on sessions/briefs/
articles, voice fields on articles

Revision ID: f3b8d1c6a2e4
Revises: e2a7c4d9b1f3
Create Date: 2026-09-01 12:00:00.000000

AUTHOR-011 — persona voice engine.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3b8d1c6a2e4"
down_revision: str | Sequence[str] | None = "e2a7c4d9b1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("owner_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_personas_owner_id", "personas", ["owner_id"])

    op.create_table(
        "persona_samples",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "persona_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("personas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.dialects.postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_persona_samples_persona_id", "persona_samples", ["persona_id"])

    op.add_column(
        "research_sessions",
        sa.Column(
            "voice_persona_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.create_foreign_key(
        "fk_research_sessions_voice_persona_id",
        "research_sessions",
        "personas",
        ["voice_persona_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "briefs",
        sa.Column(
            "voice_persona_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.create_foreign_key(
        "fk_briefs_voice_persona_id",
        "briefs",
        "personas",
        ["voice_persona_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "canonical_articles",
        sa.Column("audience_persona", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "canonical_articles",
        sa.Column(
            "voice_persona_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.create_foreign_key(
        "fk_canonical_articles_voice_persona_id",
        "canonical_articles",
        "personas",
        ["voice_persona_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "canonical_articles",
        sa.Column("voice_match_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "canonical_articles",
        sa.Column(
            "voice_scores_by_section", sa.dialects.postgresql.JSONB(), nullable=True
        ),
    )
    op.add_column(
        "canonical_articles",
        sa.Column(
            "few_shot_sample_ids",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("canonical_articles", "few_shot_sample_ids")
    op.drop_column("canonical_articles", "voice_scores_by_section")
    op.drop_column("canonical_articles", "voice_match_score")
    op.drop_constraint(
        "fk_canonical_articles_voice_persona_id",
        "canonical_articles",
        type_="foreignkey",
    )
    op.drop_column("canonical_articles", "voice_persona_id")
    op.drop_column("canonical_articles", "audience_persona")

    op.drop_constraint("fk_briefs_voice_persona_id", "briefs", type_="foreignkey")
    op.drop_column("briefs", "voice_persona_id")

    op.drop_constraint(
        "fk_research_sessions_voice_persona_id", "research_sessions", type_="foreignkey"
    )
    op.drop_column("research_sessions", "voice_persona_id")

    op.drop_index("ix_persona_samples_persona_id", table_name="persona_samples")
    op.drop_table("persona_samples")

    op.drop_index("ix_personas_owner_id", table_name="personas")
    op.drop_table("personas")
