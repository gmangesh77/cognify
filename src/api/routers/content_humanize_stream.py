"""AUTHOR-009 — POST-SSE endpoint for the multi-pass humanize preview.

Kept in its own module (content.py is already over the line budget).
Preview-only: the client stages the resolved markdown through
`/content/section-update`, which runs the anchor validator.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.rate_limiter import limiter
from src.api.routers.content import _get_content_llm
from src.services.content.humanize_stream import stream_humanization
from src.services.content.section_history_contracts import parse_section_id

content_humanize_stream_router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


class HumanizeStreamRequest(BaseModel):
    section_id: str = Field(min_length=3, max_length=80)
    title: str = Field(default="Section", max_length=200)
    current_markdown: str = Field(min_length=1, max_length=20000)


def _section_index_or_400(section_id: str) -> int:
    try:
        return parse_section_id(section_id)[1]
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


# Route decorator OUTERMOST or slowapi never evaluates the limit (AUTHOR-006).
@content_humanize_stream_router.post(
    "/content/humanize-preview/stream",
    summary="Stream a multi-pass humanization preview (SSE)",
)
@limiter.limit("20/minute")
async def humanize_preview_stream(
    request: Request,
    body: HumanizeStreamRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> StreamingResponse:
    """Emit `pass` events (score per pass), then `done` with sentence segments.

    Preview-only — nothing is persisted. The client resolves per-sentence
    decisions and saves through `/content/section-update`.
    """
    section_index = _section_index_or_400(body.section_id)
    llm = _get_content_llm(request)
    max_passes = request.app.state.settings.humanize_preview_max_passes

    async def gen() -> AsyncIterator[str]:
        events = stream_humanization(
            section_index=section_index,
            title=body.title,
            markdown=body.current_markdown,
            llm=llm,
            max_llm_passes=max_passes,
        )
        async for event in events:
            if await request.is_disconnected():
                return
            yield event.to_sse()

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers=_SSE_HEADERS
    )


__all__ = ["content_humanize_stream_router"]
