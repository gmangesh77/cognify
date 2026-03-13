from fastapi import Header, Request

from src.api.auth.schemas import TokenPayload
from src.api.auth.tokens import decode_access_token
from src.api.errors import AuthenticationError


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
    return decode_access_token(parts[1], settings)


async def get_db_session() -> None:
    """Placeholder — replaced when database layer is added."""
