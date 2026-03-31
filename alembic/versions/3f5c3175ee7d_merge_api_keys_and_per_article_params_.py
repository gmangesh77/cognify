"""merge api_keys and per_article_params heads

Revision ID: 3f5c3175ee7d
Revises: 32a2b945f800, d4e2f1a9b7c3
Create Date: 2026-03-31 09:16:50.331324

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f5c3175ee7d'
down_revision: Union[str, Sequence[str], None] = ('32a2b945f800', 'd4e2f1a9b7c3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
