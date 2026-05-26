"""add structural_diagram_mode to research_sessions

Revision ID: e7c1a9d3f8b2
Revises: d9b7e4a2c510
Create Date: 2026-05-26 16:30:00.000000

VISUAL-012 — per-article toggle for how structural diagrams
(concept / process_step / comparison_split) are rendered:
"illustration" (gpt-image-1 diffusion, default) or "mermaid"
(deterministic Mermaid diagrams). Backfilled to "illustration" via
server_default so existing rows keep current behaviour.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c1a9d3f8b2"
down_revision: str | Sequence[str] | None = "d9b7e4a2c510"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_sessions",
        sa.Column(
            "structural_diagram_mode",
            sa.String(length=20),
            nullable=False,
            server_default="illustration",
        ),
    )


def downgrade() -> None:
    op.drop_column("research_sessions", "structural_diagram_mode")
