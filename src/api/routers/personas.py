"""Persona voice-engine endpoints (AUTHOR-011): CRUD, samples, fingerprint
recompute, score preview. See spec §6."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette import status as http_status

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.errors import ConflictError, NotFoundError, ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.personas import (
    PersonaDetail,
    PersonaListResponse,
    PersonaSummary,
    ScoreRequest,
)
from src.models.persona import PersonaCreate, PersonaUpdate, SampleCreate, VoiceScore
from src.services.persona.service import (
    PersonaNotReady,
    PersonaService,
    SampleTooShort,
)

personas_router = APIRouter()


def _service(request: Request) -> PersonaService:
    service = getattr(request.app.state, "persona_service", None)
    if service is None:
        raise ServiceUnavailableError(message="Persona store not configured.")
    return service  # type: ignore[no-any-return]


def _not_found(persona_id: UUID) -> NotFoundError:
    return NotFoundError(message=f"unknown persona: {persona_id}")


# Route decorator OUTERMOST or slowapi never evaluates the limit (AUTHOR-006).
@personas_router.get("/personas", response_model=PersonaListResponse)
@limiter.limit("30/minute")
async def list_personas(
    request: Request, user: TokenPayload = Depends(require_viewer_or_above)
) -> PersonaListResponse:
    return PersonaListResponse(items=await _service(request).list_summaries())


@personas_router.post(
    "/personas",
    response_model=PersonaSummary,
    status_code=http_status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def create_persona(
    request: Request,
    body: PersonaCreate,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PersonaSummary:
    return await _service(request).create(user.sub, body)


@personas_router.get("/personas/{persona_id}", response_model=PersonaDetail)
@limiter.limit("30/minute")
async def get_persona(
    request: Request,
    persona_id: UUID,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> PersonaDetail:
    detail = await _service(request).get_detail(persona_id)
    if detail is None:
        raise _not_found(persona_id)
    return detail


@personas_router.patch("/personas/{persona_id}", response_model=PersonaSummary)
@limiter.limit("30/minute")
async def update_persona(
    request: Request,
    persona_id: UUID,
    body: PersonaUpdate,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PersonaSummary:
    summary = await _service(request).update(persona_id, body)
    if summary is None:
        raise _not_found(persona_id)
    return summary


@personas_router.delete(
    "/personas/{persona_id}", status_code=http_status.HTTP_204_NO_CONTENT
)
@limiter.limit("30/minute")
async def delete_persona(
    request: Request,
    persona_id: UUID,
    user: TokenPayload = Depends(require_editor_or_above),
) -> Response:
    if not await _service(request).delete(persona_id):
        raise _not_found(persona_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@personas_router.post(
    "/personas/{persona_id}/samples",
    response_model=PersonaDetail,
    status_code=http_status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def add_sample(
    request: Request,
    persona_id: UUID,
    body: SampleCreate,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PersonaDetail:
    try:
        detail = await _service(request).add_sample(persona_id, body)
    except SampleTooShort as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"violations": [str(exc)]},
        ) from exc
    if detail is None:
        raise _not_found(persona_id)
    return detail


@personas_router.delete(
    "/personas/{persona_id}/samples/{sample_id}", response_model=PersonaDetail
)
@limiter.limit("30/minute")
async def delete_sample(
    request: Request,
    persona_id: UUID,
    sample_id: UUID,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PersonaDetail:
    detail = await _service(request).delete_sample(persona_id, sample_id)
    if detail is None:
        raise _not_found(persona_id)
    return detail


@personas_router.post("/personas/{persona_id}/score", response_model=VoiceScore)
@limiter.limit("30/minute")
async def score_persona(
    request: Request,
    persona_id: UUID,
    body: ScoreRequest,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> VoiceScore:
    try:
        result = await _service(request).score(persona_id, body.text)
    except PersonaNotReady as exc:
        raise ConflictError(code="persona_not_ready", message=str(exc)) from exc
    if result is None:
        raise _not_found(persona_id)
    return result
