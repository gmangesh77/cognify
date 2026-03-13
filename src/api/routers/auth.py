from fastapi import APIRouter, Request
from starlette.responses import Response

from src.api.auth.schemas import LoginRequest, RefreshRequest, TokenResponse
from src.api.auth.service import AuthService
from src.api.rate_limiter import limiter

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
