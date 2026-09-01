"""SQLAlchemy tables for voice personas + writing samples (AUTHOR-011).

Own module — `src/db/tables.py` is over the 200-line budget; imported from
there so `Base.metadata` is complete for Alembic and `create_all`.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDMixin


class PersonaRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "personas"

    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)


class PersonaSampleRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "persona_samples"

    persona_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        index=True,
    )
    text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
