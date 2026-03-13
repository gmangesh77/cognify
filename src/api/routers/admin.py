"""Admin routes — requires admin role."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_admin

admin_router = APIRouter()


class RoleCheckResponse(BaseModel):
    user_id: str
    role: str
    message: str


@admin_router.get(
    "/admin/check",
    response_model=RoleCheckResponse,
    summary="Verify admin access",
)
async def admin_check(
    user: TokenPayload = Depends(require_admin),
) -> RoleCheckResponse:
    return RoleCheckResponse(
        user_id=user.sub,
        role=user.role,
        message="Admin access verified",
    )
