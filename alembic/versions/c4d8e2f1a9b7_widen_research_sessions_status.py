"""widen research_sessions.status to 40 chars

AUTHOR-002 added the `awaiting_outline_review` status (23 chars) but the
column stayed VARCHAR(20), so the outline gate failed live with
StringDataRightTruncationError. Widen to 40.

Revision ID: c4d8e2f1a9b7
Revises: b3c7e1f9a2d4
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d8e2f1a9b7"
down_revision: str | Sequence[str] | None = "b3c7e1f9a2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "research_sessions",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Rows holding >20-char statuses would be truncated/rejected; none of the
    # pre-AUTHOR-002 statuses exceed 20 chars.
    op.alter_column(
        "research_sessions",
        "status",
        existing_type=sa.String(length=40),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
