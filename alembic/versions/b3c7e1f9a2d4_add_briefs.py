"""add briefs table + brief linkage on research_sessions

Revision ID: b3c7e1f9a2d4
Revises: a9d4e2f7c1b8
Create Date: 2026-08-20 10:00:00.000000

AUTHOR-003 / ADR-007 — Brief as the authoring input contract. Sessions
denormalise brief values at start; `brief_id` is a nullable FK with
ON DELETE SET NULL so deleting a brief never touches past sessions.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c7e1f9a2d4"
down_revision: str | Sequence[str] | None = "a9d4e2f7c1b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "briefs",
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
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_audience", sa.String(length=500), nullable=True),
        sa.Column("content_tone", sa.String(length=100), nullable=True),
        sa.Column("preferred_angle", sa.String(length=500), nullable=True),
        sa.Column(
            "keywords",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "content_type",
            sa.String(length=20),
            nullable=False,
            server_default="article",
        ),
        sa.Column(
            "length_target",
            sa.String(length=20),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "structural_diagram_mode",
            sa.String(length=20),
            nullable=False,
            server_default="illustration",
        ),
        sa.Column("audience_persona", sa.String(length=100), nullable=True),
        sa.Column(
            "require_outline_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index("ix_briefs_owner_id", "briefs", ["owner_id"])
    op.add_column(
        "research_sessions",
        sa.Column("brief_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_research_sessions_brief_id",
        "research_sessions",
        "briefs",
        ["brief_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_research_sessions_brief_id", "research_sessions", ["brief_id"])
    op.add_column(
        "research_sessions",
        sa.Column("content_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "research_sessions",
        sa.Column("length_target", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "research_sessions",
        sa.Column("audience_persona", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_sessions", "audience_persona")
    op.drop_column("research_sessions", "length_target")
    op.drop_column("research_sessions", "content_type")
    op.drop_index("ix_research_sessions_brief_id", table_name="research_sessions")
    op.drop_constraint(
        "fk_research_sessions_brief_id", "research_sessions", type_="foreignkey"
    )
    op.drop_column("research_sessions", "brief_id")
    op.drop_index("ix_briefs_owner_id", table_name="briefs")
    op.drop_table("briefs")
