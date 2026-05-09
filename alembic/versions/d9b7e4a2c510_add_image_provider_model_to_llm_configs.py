"""add image_provider + image_model to llm_configs

Revision ID: d9b7e4a2c510
Revises: c4d8e6f9a2b3
Create Date: 2026-05-09 19:00:00.000000

Phase 2 of the visuals provider/UX work — lets end-users pick the
image-generation provider (OpenAI vs Google) and a specific model
within that provider via the Settings UI. The legacy `image_generation`
column is left in place for backward compatibility (it never wired into
the new provider stack); the new columns are what `image_render_node`
will read at render time.

`image_provider` is backfilled to "dalle_3" via server_default to match
the new application default. `image_model` is nullable — when null, the
provider's own default model is used.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9b7e4a2c510"
down_revision: str | Sequence[str] | None = "c4d8e6f9a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "llm_configs",
        sa.Column(
            "image_provider",
            sa.String(length=60),
            nullable=False,
            server_default="dalle_3",
        ),
    )
    op.add_column(
        "llm_configs",
        sa.Column(
            "image_model",
            sa.String(length=120),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("llm_configs", "image_model")
    op.drop_column("llm_configs", "image_provider")
