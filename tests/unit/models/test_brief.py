"""Brief model validation (AUTHOR-003, ADR-007)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.brief import Brief, BriefCreate, BriefUpdate
from src.models.content import ContentType


def test_brief_create_defaults() -> None:
    b = BriefCreate(name="Q3 security explainer")
    assert b.content_type == ContentType.ARTICLE
    assert b.length_target == "medium"
    assert b.structural_diagram_mode == "illustration"
    assert b.keywords == []
    assert b.require_outline_approval is False


def test_brief_create_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(name="")


def test_brief_create_rejects_unknown_tone() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(name="x", content_tone="sarcastic")


def test_brief_create_accepts_known_tone_and_persona() -> None:
    b = BriefCreate(
        name="x", content_tone="educational", audience_persona="general_business"
    )
    assert b.content_tone == "educational"


def test_brief_create_rejects_unknown_persona() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(name="x", audience_persona="martians")


def test_brief_create_rejects_bad_length_target() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(name="x", length_target="gigantic")


def test_brief_update_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        BriefUpdate()
    assert BriefUpdate(name="renamed").name == "renamed"


def test_brief_round_trips_json_mode() -> None:
    now = datetime.now(UTC)
    b = Brief(
        id=uuid4(),
        owner_id="user-1",
        name="n",
        created_at=now,
        updated_at=now,
        keywords=["a", "b"],
    )
    dumped = b.model_dump(mode="json")
    assert dumped["keywords"] == ["a", "b"]
    assert isinstance(dumped["id"], str)


def test_keyword_items_are_length_bounded() -> None:
    with pytest.raises(ValidationError):
        BriefCreate(name="A", keywords=["x" * 101])
    assert BriefCreate(name="A", keywords=["x" * 100]).keywords == ["x" * 100]
