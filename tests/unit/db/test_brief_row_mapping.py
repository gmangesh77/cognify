"""Unit tests for BriefRow <-> Brief mapping helpers (AUTHOR-003 / ADR-007).

Pure mapping tests — no database involved.
"""

from datetime import UTC, datetime
from uuid import uuid4

from src.db.brief_repository import brief_create_to_row, row_to_brief
from src.models.brief import BriefCreate


def test_create_to_row_and_back() -> None:
    data = BriefCreate(
        name="n",
        keywords=["a"],
        content_type="how-to",
        length_target="short",
        audience_persona="general_business",
        content_tone="educational",
    )
    row = brief_create_to_row("user-1", data)
    assert row.owner_id == "user-1"
    assert row.keywords == ["a"]
    assert row.content_type == "how-to"
    row.id = uuid4()
    row.created_at = row.updated_at = datetime.now(UTC)
    brief = row_to_brief(row)
    assert brief.name == "n"
    assert brief.length_target == "short"
    assert brief.content_type == "how-to"
    assert brief.owner_id == "user-1"


def test_voice_persona_id_round_trips() -> None:
    voice_persona_id = uuid4()
    data = BriefCreate(name="n", voice_persona_id=voice_persona_id)
    row = brief_create_to_row("user-1", data)
    row.id = uuid4()
    row.created_at = row.updated_at = datetime.now(UTC)
    brief = row_to_brief(row)
    assert brief.voice_persona_id == voice_persona_id


def test_voice_persona_id_defaults_to_none() -> None:
    data = BriefCreate(name="n")
    row = brief_create_to_row("user-1", data)
    row.id = uuid4()
    row.created_at = row.updated_at = datetime.now(UTC)
    brief = row_to_brief(row)
    assert brief.voice_persona_id is None
