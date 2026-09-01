"""Prompt registry endpoints (AUTHOR-012): view every registered prompt,
override one (admin), reset one (admin)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette import status as http_status

from src.agents.prompts import DEFAULT_PROMPTS, PromptTemplate
from src.agents.prompts.validation import validate_template
from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_admin, require_editor_or_above
from src.api.errors import NotFoundError, ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.prompts import PromptListResponse, PromptView, UpdatePromptRequest
from src.db.prompt_override_repository import PromptOverrideRepository
from src.models.prompt_override import PromptOverride

prompts_router = APIRouter()


def _repo(request: Request) -> PromptOverrideRepository:
    repo = getattr(request.app.state, "prompt_override_repo", None)
    if repo is None:
        raise ServiceUnavailableError(message="Prompt override store not configured.")
    return repo  # type: ignore[no-any-return]


def _spec(key: str) -> PromptTemplate:
    spec = DEFAULT_PROMPTS.get(key)
    if spec is None:
        raise NotFoundError(message=f"unknown prompt key: {key}")
    return spec


def _view(spec: PromptTemplate, override: PromptOverride | None) -> PromptView:
    return PromptView(
        key=spec.key,
        step=spec.step,
        description=spec.description,
        variables=sorted(spec.variables),
        default_template=spec.template,
        template=override.template if override else spec.template,
        is_overridden=override is not None,
        updated_by=override.updated_by if override else None,
        updated_at=override.updated_at if override else None,
    )


def _list_view(spec: PromptTemplate, overrides: dict[str, str]) -> PromptView:
    """List rows carry no author/timestamp — `load_all()` returns templates
    only. Never fabricate `updated_by`/`updated_at` here (see task brief)."""
    return PromptView(
        key=spec.key,
        step=spec.step,
        description=spec.description,
        variables=sorted(spec.variables),
        default_template=spec.template,
        template=overrides.get(spec.key, spec.template),
        is_overridden=spec.key in overrides,
        updated_by=None,
        updated_at=None,
    )


# Route decorator OUTERMOST or slowapi never evaluates the limit (AUTHOR-006).
@prompts_router.get("/prompts", response_model=PromptListResponse)
@limiter.limit("30/minute")
async def list_prompts(
    request: Request, user: TokenPayload = Depends(require_editor_or_above)
) -> PromptListResponse:
    overrides = await _repo(request).load_all()
    items = [_list_view(spec, overrides) for _, spec in sorted(DEFAULT_PROMPTS.items())]
    return PromptListResponse(items=items)


@prompts_router.get("/prompts/{key}", response_model=PromptView)
@limiter.limit("30/minute")
async def get_prompt(
    request: Request, key: str, user: TokenPayload = Depends(require_editor_or_above)
) -> PromptView:
    return _view(_spec(key), await _repo(request).get(key))


@prompts_router.put("/prompts/{key}", response_model=PromptView)
@limiter.limit("30/minute")
async def put_prompt(
    request: Request,
    key: str,
    body: UpdatePromptRequest,
    user: TokenPayload = Depends(require_admin),
) -> PromptView:
    spec = _spec(key)
    violations = validate_template(body.template, spec)
    if violations:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"violations": violations},
        )
    saved = await _repo(request).upsert(
        key, template=body.template, updated_by=user.sub
    )
    return _view(spec, saved)


@prompts_router.delete("/prompts/{key}", response_model=PromptView)
@limiter.limit("30/minute")
async def reset_prompt(
    request: Request, key: str, user: TokenPayload = Depends(require_admin)
) -> PromptView:
    spec = _spec(key)
    if not await _repo(request).delete(key):
        raise NotFoundError(message=f"no override for prompt key: {key}")
    return _view(spec, None)
