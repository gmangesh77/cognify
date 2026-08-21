"""Brief CRUD endpoints (AUTHOR-003 / ADR-007)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.models.brief import Brief, BriefCreate, BriefUpdate
from src.services.briefs import BriefService, BriefUpdateCommand

briefs_router = APIRouter()


def _svc(request: Request) -> BriefService:
    svc = getattr(request.app.state, "brief_service", None)
    if svc is None:
        raise ServiceUnavailableError(message="Brief service not configured.")
    return svc  # type: ignore[no-any-return]


@limiter.limit("30/minute")
@briefs_router.get("/briefs", response_model=list[Brief])
async def list_briefs(
    request: Request, user: TokenPayload = Depends(require_viewer_or_above)
) -> list[Brief]:
    return await _svc(request).list(user.sub)


@limiter.limit("20/minute")
@briefs_router.post("/briefs", response_model=Brief, status_code=HTTP_201_CREATED)
async def create_brief(
    request: Request,
    body: BriefCreate,
    user: TokenPayload = Depends(require_editor_or_above),
) -> Brief:
    return await _svc(request).create(user.sub, body)


@limiter.limit("30/minute")
@briefs_router.get("/briefs/{brief_id}", response_model=Brief)
async def get_brief(
    request: Request,
    brief_id: UUID,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> Brief:
    return await _svc(request).get(user.sub, brief_id)


@limiter.limit("20/minute")
@briefs_router.patch("/briefs/{brief_id}", response_model=Brief)
async def update_brief(
    request: Request,
    brief_id: UUID,
    body: BriefUpdate,
    user: TokenPayload = Depends(require_editor_or_above),
) -> Brief:
    return await _svc(request).update(BriefUpdateCommand(user.sub, brief_id, body))


@limiter.limit("20/minute")
@briefs_router.delete("/briefs/{brief_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_brief(
    request: Request,
    brief_id: UUID,
    user: TokenPayload = Depends(require_editor_or_above),
) -> Response:
    await _svc(request).delete(user.sub, brief_id)
    return Response(status_code=HTTP_204_NO_CONTENT)


@limiter.limit("20/minute")
@briefs_router.post(
    "/briefs/{brief_id}/duplicate", response_model=Brief, status_code=HTTP_201_CREATED
)
async def duplicate_brief(
    request: Request,
    brief_id: UUID,
    user: TokenPayload = Depends(require_editor_or_above),
) -> Brief:
    return await _svc(request).duplicate(user.sub, brief_id)
