"""Helpers shared by the /content routers (content.py + content_regenerate.py).

Lifted out of `content.py` (AUTHOR-004) so the regenerate router can emit a
byte-identical 422 anchor-violation payload and resolve the same
`SectionHistoryService` without importing the 500-line module.
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel

from src.services.content.section_history import (
    AnchorViolationError,
    SectionHistoryService,
)
from src.services.content.word_diff import WordDiffOp


class WordDiffEntry(BaseModel):
    """Wire-format mirror of `WordDiffOp` so OpenAPI knows the shape."""

    kind: Literal["equal", "insert", "delete", "replace"]
    before: str
    after: str

    @classmethod
    def from_op(cls, op: WordDiffOp) -> WordDiffEntry:
        return cls(kind=op.kind, before=op.before, after=op.after)


class AnchorViolationEntry(BaseModel):
    kind: Literal["spec_id", "heading_text"]
    value: str
    spec_id: str | None = None
    message: str


def anchor_violation_http(exc: AnchorViolationError) -> HTTPException:
    """The ONE 422 shape for every anchor violation (update, restore, regenerate)."""
    return HTTPException(
        status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "error": "anchor_violation",
            "violations": [
                AnchorViolationEntry(
                    kind=v.kind, value=v.value, spec_id=v.spec_id, message=v.message
                ).model_dump()
                for v in exc.violations
            ],
        },
    )


def get_history_service(request: Request) -> SectionHistoryService:
    """Resolve (and memoise) SectionHistoryService from app.state; 503 if missing."""
    svc = getattr(request.app.state, "section_history_service", None)
    if svc is None:
        article_repo = getattr(request.app.state, "article_repo", None)
        version_repo = getattr(request.app.state, "section_version_repo", None)
        if article_repo is None or version_repo is None:
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="section history service is not configured",
            )
        svc = SectionHistoryService(article_repo, version_repo)
        request.app.state.section_history_service = svc
    assert isinstance(svc, SectionHistoryService)
    return svc


__all__ = [
    "AnchorViolationEntry",
    "WordDiffEntry",
    "anchor_violation_http",
    "get_history_service",
]
