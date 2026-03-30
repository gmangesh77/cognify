"""add per-article params to research_sessions

Revision ID: d4e2f1a9b7c3
Revises: c1f4a8b2e903
Create Date: 2026-03-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e2f1a9b7c3"
down_revision: Union[str, Sequence[str], None] = "c1f4a8b2e903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_sessions",
        sa.Column("target_audience", sa.String(500), nullable=True),
    )
    op.add_column(
        "research_sessions",
        sa.Column("content_tone", sa.String(100), nullable=True),
    )
    op.add_column(
        "research_sessions",
        sa.Column("preferred_angle", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_sessions", "preferred_angle")
    op.drop_column("research_sessions", "content_tone")
    op.drop_column("research_sessions", "target_audience")
