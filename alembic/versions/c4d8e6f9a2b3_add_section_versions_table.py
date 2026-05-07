"""add section_versions table

Revision ID: c4d8e6f9a2b3
Revises: b7c9d2e4a5f1
Create Date: 2026-05-07 19:55:00.000000

VISUAL-011 / Phase 8 — append-only audit log of per-section prose
edits. The active section markdown still lives on
`canonical_articles.body_markdown`; this table is a sidecar for
history, restore, and auditing only.

`section_id` is the f"{article_id}:{section_index}" string the handoff
brief specifies. We index on (article_id, section_id) so the history
drawer can paginate one section quickly.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d8e6f9a2b3"
down_revision: str | Sequence[str] | None = "b7c9d2e4a5f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "section_versions",
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
            "article_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_articles.id"),
            nullable=False,
        ),
        sa.Column("section_id", sa.String(length=80), nullable=False),
        sa.Column("section_index", sa.Integer(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("usd", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
    )
    op.create_index(
        "ix_section_versions_article_id",
        "section_versions",
        ["article_id"],
    )
    op.create_index(
        "ix_section_versions_section_id",
        "section_versions",
        ["section_id"],
    )
    op.create_index(
        "ix_section_versions_article_section",
        "section_versions",
        ["article_id", "section_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_section_versions_article_section", table_name="section_versions")
    op.drop_index("ix_section_versions_section_id", table_name="section_versions")
    op.drop_index("ix_section_versions_article_id", table_name="section_versions")
    op.drop_table("section_versions")
