"""add keywords and topic_description_override to research_sessions

Revision ID: f6a8d4b2c3e5
Revises: e5f3a2b8c1d7
Create Date: 2026-04-09 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f6a8d4b2c3e5"
down_revision: Union[str, Sequence[str], None] = "e5f3a2b8c1d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_sessions",
        sa.Column("keywords", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "research_sessions",
        sa.Column("topic_description_override", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_sessions", "topic_description_override")
    op.drop_column("research_sessions", "keywords")
