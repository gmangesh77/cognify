"""resolve_session_params precedence: inline > brief > default (AUTHOR-003)."""

from datetime import UTC, datetime
from uuid import uuid4

from src.api.routers.research_params import (
    ParamSources,
    inline_brief_create,
    resolve_session_params,
)
from src.api.schemas.research import CreateResearchSessionRequest
from src.models.brief import Brief


def _brief(**kw: object) -> Brief:
    now = datetime.now(UTC)
    base = dict(id=uuid4(), owner_id="u", name="b", created_at=now, updated_at=now)
    return Brief(**{**base, **kw})  # type: ignore[arg-type]


def test_inline_only_matches_legacy_defaults() -> None:
    body = CreateResearchSessionRequest(topic_id=uuid4(), target_audience="devs")
    p = resolve_session_params(ParamSources(body, None, default_gate=False))
    assert p.target_audience == "devs"
    assert p.structural_diagram_mode == "illustration"
    assert p.require_outline_approval is False
    assert p.brief_id is None


def test_brief_values_used_when_inline_absent() -> None:
    b = _brief(
        target_audience="CISOs",
        structural_diagram_mode="mermaid",
        require_outline_approval=True,
        keywords=["zt"],
        length_target="long",
    )
    body = CreateResearchSessionRequest(topic_id=uuid4())
    p = resolve_session_params(ParamSources(body, b, default_gate=False))
    assert p.brief_id == b.id
    assert p.target_audience == "CISOs"
    assert p.structural_diagram_mode == "mermaid"
    assert p.require_outline_approval is True
    assert p.keywords == ["zt"]
    assert p.length_target == "long"


def test_inline_overrides_brief_but_keeps_link() -> None:
    b = _brief(target_audience="CISOs", content_tone="analytical")
    body = CreateResearchSessionRequest(topic_id=uuid4(), target_audience="devs")
    p = resolve_session_params(ParamSources(body, b, default_gate=False))
    assert p.target_audience == "devs"
    assert p.content_tone == "analytical"
    assert p.brief_id == b.id


def test_gate_falls_back_to_settings_default() -> None:
    body = CreateResearchSessionRequest(topic_id=uuid4())
    p = resolve_session_params(ParamSources(body, None, default_gate=True))
    assert p.require_outline_approval is True


def test_inline_brief_create_uses_brief_name_or_topic_title() -> None:
    body = CreateResearchSessionRequest(
        topic_id=uuid4(), keywords=["a"], content_tone="educational", save_as_brief=True
    )
    bc = inline_brief_create(body, "Topic T")
    assert bc.name == "Topic T"
    assert bc.keywords == ["a"]
    assert bc.content_tone == "educational"
    body2 = body.model_copy(update={"brief_name": "My brief"})
    assert inline_brief_create(body2, "Topic T").name == "My brief"
