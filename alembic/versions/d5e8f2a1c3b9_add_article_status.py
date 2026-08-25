"""Add canonical_articles.status (AUTHOR-007).

Editorial workflow state: draft | in_review | approved | published.
Existing rows default to 'draft' per program plan §4.4. String(40)
follows the research_sessions.status width lesson (PR #75).

Revision ID: d5e8f2a1c3b9
Revises: c4d8e2f1a9b7
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5e8f2a1c3b9"
down_revision: str | Sequence[str] | None = "c4d8e2f1a9b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "canonical_articles",
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="draft",
        ),
    )


def downgrade() -> None:
    op.drop_column("canonical_articles", "status")
