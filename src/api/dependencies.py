from collections.abc import Awaitable, Callable

import structlog
from fastapi import Depends, Header, Request

from src.api.auth.schemas import Role, TokenPayload
from src.api.auth.tokens import decode_access_token
from src.api.errors import AuthenticationError, AuthorizationError

logger = structlog.get_logger()


async def get_current_user(
    request: Request,
    # default="" so FastAPI returns our 401, not its own 422 for missing header
    authorization: str = Header(alias="Authorization", default=""),
) -> TokenPayload:
    if not authorization:
        raise AuthenticationError(
            code="invalid_token",
            message="Missing authorization header",
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0] != "Bearer":
        raise AuthenticationError(
            code="invalid_token",
            message="Invalid authorization header format",
        )

    settings = request.app.state.settings
    payload = decode_access_token(parts[1], settings)
    return _recheck_user_status(request, payload)


def _recheck_user_status(request: Request, payload: TokenPayload) -> TokenPayload:
    """INFRA-008: deactivated users lose access within the cache TTL.

    A user unknown to the repository keeps the token's claims (the in-memory
    seed is not authoritative for existence); a role mismatch is logged, not
    enforced — see the INFRA-008 plan, deviations #1/#2.
    """
    repo = getattr(request.app.state, "user_repo", None)
    cache = getattr(request.app.state, "user_status_cache", None)
    if repo is None or cache is None:
        return payload
    user = cache.lookup(payload.sub, repo)
    if user is None:
        return payload
    if not user.is_active:
        logger.warning("auth_user_inactive", user_id=payload.sub)
        raise AuthenticationError(
            code="user_inactive", message="User account is deactivated"
        )
    if user.role != payload.role:
        logger.warning(
            "auth_role_drift",
            user_id=payload.sub,
            token_role=payload.role,
            repo_role=user.role,
        )
    return payload


async def get_db_session() -> None:
    """Placeholder — replaced when database layer is added."""


def require_role(
    *allowed_roles: Role,
) -> Callable[..., Awaitable[TokenPayload]]:
    """Factory that returns a FastAPI dependency checking user role.

    Usage: ``user: TokenPayload = Depends(require_role("admin", "editor"))``
    """

    async def _check_role(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if current_user.role not in allowed_roles:
            logger.warning(
                "authorization_denied",
                user_id=current_user.sub,
                role=current_user.role,
                required_roles=allowed_roles,
            )
            raise AuthorizationError(
                message=f"Role '{current_user.role}' is not authorized"
                " for this resource",
            )
        return current_user

    return _check_role


require_admin = require_role("admin")
require_editor_or_above = require_role("admin", "editor")
require_viewer_or_above = require_role("admin", "editor", "viewer")
