"""Shared /content route helpers (AUTHOR-004 Task 3)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.routers.content_shared import anchor_violation_http, get_history_service
from src.services.content.section_anchors import AnchorViolation
from src.services.content.section_history import AnchorViolationError


def test_anchor_violation_http_shape_matches_section_update_contract() -> None:
    exc = AnchorViolationError(
        [AnchorViolation(kind="spec_id", value="s1", spec_id="s1", message="dropped")]
    )
    http = anchor_violation_http(exc)
    assert http.status_code == 422
    assert http.detail == {
        "error": "anchor_violation",
        "violations": [
            {"kind": "spec_id", "value": "s1", "spec_id": "s1", "message": "dropped"}
        ],
    }


def test_get_history_service_503_when_unconfigured() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(HTTPException) as ei:
        get_history_service(request)  # type: ignore[arg-type]
    assert ei.value.status_code == 503
