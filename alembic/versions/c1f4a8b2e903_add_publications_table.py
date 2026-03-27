"""add publications table

Revision ID: c1f4a8b2e903
Revises: a3e1c7d82b4f
Create Date: 2026-03-27 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c1f4a8b2e903"
down_revision: Union[str, Sequence[str], None] = "a3e1c7d82b4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "article_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seo_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "event_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
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
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["canonical_articles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id", "platform", name="uq_publication_article_platform"
        ),
    )
    op.create_index(
        op.f("ix_publications_platform"), "publications", ["platform"], unique=False,
    )
    op.create_index(
        op.f("ix_publications_status"), "publications", ["status"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_publications_status"), table_name="publications")
    op.drop_index(op.f("ix_publications_platform"), table_name="publications")
    op.drop_table("publications")
