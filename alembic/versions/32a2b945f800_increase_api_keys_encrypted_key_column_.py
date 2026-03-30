"""increase api_keys encrypted_key column to 2000

Revision ID: 32a2b945f800
Revises: c1f4a8b2e903
Create Date: 2026-03-30 15:34:37.315526

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32a2b945f800'
down_revision: Union[str, Sequence[str], None] = 'c1f4a8b2e903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "api_keys",
        "encrypted_key",
        type_=sa.String(2000),
        existing_type=sa.String(500),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "api_keys",
        "encrypted_key",
        type_=sa.String(500),
        existing_type=sa.String(2000),
    )
