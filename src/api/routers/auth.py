import structlog
from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from src.api.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    TokenPayload,
    TokenResponse,
    UserActiveRequest,
    UserActiveResponse,
)
from src.api.auth.service import AuthService
from src.api.dependencies import require_admin
from src.api.errors import NotFoundError
from src.api.rate_limiter import limiter

logger = structlog.get_logger()

auth_router = APIRouter()


def _get_auth_service(request: Request) -> AuthService:
    return AuthService(
        settings=request.app.state.settings,
        refresh_repo=request.app.state.refresh_repo,
        user_repo=request.app.state.user_repo,
    )


@auth_router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest) -> TokenResponse:
    service = _get_auth_service(request)
    return service.login(body.email, body.password)


@auth_router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
@limiter.limit("10/minute")
async def refresh(request: Request, body: RefreshRequest) -> TokenResponse:
    service = _get_auth_service(request)
    return service.refresh(body.refresh_token)


@auth_router.post(
    "/auth/logout",
    status_code=204,
    summary="Logout and revoke refresh token",
)
@limiter.limit("10/minute")
async def logout(request: Request, body: RefreshRequest) -> Response:
    service = _get_auth_service(request)
    service.logout(body.refresh_token)
    return Response(status_code=204)


@auth_router.patch(
    "/auth/users/{user_id}/active",
    response_model=UserActiveResponse,
    summary="Activate or deactivate a user (admin only)",
)
@limiter.limit("10/minute")
async def set_user_active(
    request: Request,
    user_id: str,
    body: UserActiveRequest,
    admin: TokenPayload = Depends(require_admin),
) -> UserActiveResponse:
    """INFRA-008 — takes effect on the user's next request (cache invalidated)."""
    user = request.app.state.user_repo.set_active(user_id, body.is_active)
    if user is None:
        raise NotFoundError(message=f"User '{user_id}' not found")
    request.app.state.user_status_cache.invalidate(user_id)
    if not body.is_active:
        request.app.state.refresh_repo.revoke_all_for_user(user_id)
    logger.info(
        "user_active_changed",
        user_id=user_id,
        is_active=body.is_active,
        changed_by=admin.sub,
    )
    return UserActiveResponse(user_id=user_id, is_active=user.is_active)
