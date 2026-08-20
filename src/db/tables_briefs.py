"""SQLAlchemy table for briefs (AUTHOR-003 / ADR-007).

Lives in its own module because `src/db/tables.py` is already over the
200-line budget. Imported from `tables.py` so `Base.metadata` is complete
for Alembic and `create_all`.
"""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDMixin


class BriefRow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "briefs"

    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_angle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    content_type: Mapped[str] = mapped_column(String(20), default="article")
    length_target: Mapped[str] = mapped_column(String(20), default="medium")
    structural_diagram_mode: Mapped[str] = mapped_column(
        String(20), default="illustration"
    )
    audience_persona: Mapped[str | None] = mapped_column(String(100), nullable=True)
    require_outline_approval: Mapped[bool] = mapped_column(Boolean, default=False)
