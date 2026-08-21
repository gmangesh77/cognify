from uuid import uuid4

from src.agents.content.seo_node import _build_provenance
from src.config.settings import Settings


def test_provenance_carries_brief_id_from_state() -> None:
    bid = uuid4()
    state = {"session_id": uuid4(), "brief_id": bid}
    prov = _build_provenance(state, Settings(_env_file=None))  # type: ignore[arg-type]
    assert prov.brief_id == bid


def test_provenance_brief_id_defaults_none() -> None:
    prov = _build_provenance({"session_id": uuid4()}, Settings(_env_file=None))  # type: ignore[arg-type]
    assert prov.brief_id is None
