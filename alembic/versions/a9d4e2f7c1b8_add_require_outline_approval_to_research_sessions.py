"""add require_outline_approval to research_sessions

Revision ID: a9d4e2f7c1b8
Revises: e7c1a9d3f8b2
Create Date: 2026-08-19 00:00:00.000000

AUTHOR-002 — per-article opt-in outline approval gate. When true, a
session pauses in "awaiting_outline_review" after research completes
instead of auto-continuing into article generation. Backfilled to
false via server_default so existing rows keep current (auto-continue)
behaviour.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9d4e2f7c1b8"
down_revision: str | Sequence[str] | None = "e7c1a9d3f8b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_sessions",
        sa.Column(
            "require_outline_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("research_sessions", "require_outline_approval")
