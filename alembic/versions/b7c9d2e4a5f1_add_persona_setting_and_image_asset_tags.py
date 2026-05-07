"""add default_audience_persona to general_configs + image_asset_tags table

Revision ID: b7c9d2e4a5f1
Revises: f6a8d4b2c3e5
Create Date: 2026-05-07 18:50:00.000000

VISUAL-010 / Phase 7 — adds the user-facing default audience persona
setting and the image_asset_tags table that backs the saved-asset
gallery's curation feature.

The persona column is backfilled to "general_business" via the
server_default so the existing single GeneralConfig row keeps validating
without an explicit row update. The tag table has no default rows.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c9d2e4a5f1"
down_revision: str | Sequence[str] | None = "f6a8d4b2c3e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "general_configs",
        sa.Column(
            "default_audience_persona",
            sa.String(length=60),
            nullable=False,
            server_default="general_business",
        ),
    )
    op.create_table(
        "image_asset_tags",
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
        sa.Column(
            "article_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_articles.id"),
            nullable=False,
        ),
        sa.Column("spec_id", sa.String(length=64), nullable=False),
        sa.Column("tag", sa.String(length=120), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "article_id", "spec_id", "tag", name="uq_image_asset_tag_unique"
        ),
    )
    op.create_index(
        "ix_image_asset_tags_article_id",
        "image_asset_tags",
        ["article_id"],
    )
    op.create_index(
        "ix_image_asset_tags_spec_id",
        "image_asset_tags",
        ["spec_id"],
    )
    op.create_index(
        "ix_image_asset_tags_tag",
        "image_asset_tags",
        ["tag"],
    )


def downgrade() -> None:
    op.drop_index("ix_image_asset_tags_tag", table_name="image_asset_tags")
    op.drop_index("ix_image_asset_tags_spec_id", table_name="image_asset_tags")
    op.drop_index("ix_image_asset_tags_article_id", table_name="image_asset_tags")
    op.drop_table("image_asset_tags")
    op.drop_column("general_configs", "default_audience_persona")
