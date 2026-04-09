"""add llm_calls table

Revision ID: e5f3a2b8c1d7
Revises: 3f5c3175ee7d
Create Date: 2026-04-02 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5f3a2b8c1d7"
down_revision: Union[str, Sequence[str], None] = "3f5c3175ee7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_steps.id"),
            nullable=True,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_sessions.id"),
            nullable=False,
        ),
        sa.Column("call_name", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column(
            "prompt_messages",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("response_content", sa.Text(), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_calls_step_id", "llm_calls", ["step_id"])
    op.create_index("ix_llm_calls_session_id", "llm_calls", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_session_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_step_id", table_name="llm_calls")
    op.drop_table("llm_calls")
