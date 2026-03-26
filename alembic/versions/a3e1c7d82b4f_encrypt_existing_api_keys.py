"""encrypt existing api keys

Revision ID: a3e1c7d82b4f
Revises: 5cc5207085ff
Create Date: 2026-03-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a3e1c7d82b4f"
down_revision: Union[str, Sequence[str], None] = "5cc5207085ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FERNET_PREFIX = "gAAAAA"


def upgrade() -> None:
    """Encrypt any plain-text API keys stored before encryption was added."""
    from src.utils.encryption import encrypt_value

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, encrypted_key FROM api_keys"),
    ).fetchall()
    for row in rows:
        if row.encrypted_key and not row.encrypted_key.startswith(_FERNET_PREFIX):
            encrypted = encrypt_value(row.encrypted_key)
            conn.execute(
                sa.text("UPDATE api_keys SET encrypted_key = :val WHERE id = :id"),
                {"val": encrypted, "id": row.id},
            )


def downgrade() -> None:
    raise NotImplementedError(
        "Cannot reverse encryption migration — decryption requires the "
        "original COGNIFY_ENCRYPTION_KEY. Restore from backup if needed."
    )
