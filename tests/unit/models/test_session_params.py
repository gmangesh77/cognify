from datetime import UTC, datetime
from uuid import uuid4

from src.models.brief import Brief
from src.models.session_params import SessionParams


def _brief() -> Brief:
    now = datetime.now(UTC)
    return Brief(
        id=uuid4(),
        owner_id="user-1",
        name="n",
        created_at=now,
        updated_at=now,
        target_audience="CISOs",
        content_tone="analytical",
        preferred_angle="risk",
        keywords=["zero trust"],
        content_type="analysis",
        length_target="long",
        structural_diagram_mode="mermaid",
        audience_persona="general_business",
        require_outline_approval=True,
        description="brief desc",
    )


def test_from_brief_copies_every_authoring_field() -> None:
    b = _brief()
    p = SessionParams.from_brief(b)
    assert p.brief_id == b.id
    assert p.target_audience == "CISOs"
    assert p.content_tone == "analytical"
    assert p.preferred_angle == "risk"
    assert p.keywords == ["zero trust"]
    assert p.content_type == "analysis"
    assert p.length_target == "long"
    assert p.structural_diagram_mode == "mermaid"
    assert p.audience_persona == "general_business"
    assert p.require_outline_approval is True
    assert p.topic_description_override == "brief desc"


def test_defaults_match_legacy_behaviour() -> None:
    p = SessionParams()
    assert p.structural_diagram_mode == "illustration"
    assert p.require_outline_approval is False
    assert p.brief_id is None
