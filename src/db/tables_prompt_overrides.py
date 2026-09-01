"""SQLAlchemy table for global prompt overrides (AUTHOR-012).

Own module: `src/db/tables.py` is over the 200-line budget. Imported from
`tables.py` so `Base.metadata` is complete for Alembic and `create_all`.
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDMixin


class PromptOverrideRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "prompt_overrides"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    template: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(String(100))
