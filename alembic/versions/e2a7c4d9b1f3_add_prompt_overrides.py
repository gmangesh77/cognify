"""add prompt_overrides table

Revision ID: e2a7c4d9b1f3
Revises: d5e8f2a1c3b9
Create Date: 2026-08-31 12:00:00.000000

AUTHOR-012 — global prompt overrides, one row per registry key.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2a7c4d9b1f3"
down_revision: str | Sequence[str] | None = "d5e8f2a1c3b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_overrides",
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
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("key", name="uq_prompt_overrides_key"),
    )
    op.create_index("ix_prompt_overrides_key", "prompt_overrides", ["key"])


def downgrade() -> None:
    op.drop_index("ix_prompt_overrides_key", table_name="prompt_overrides")
    op.drop_table("prompt_overrides")
