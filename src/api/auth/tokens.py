import uuid
from datetime import UTC, datetime, timedelta

import jwt

from src.api.auth.schemas import TokenPayload
from src.api.errors import AuthenticationError
from src.config.settings import Settings


def create_access_token(
    user_id: str, role: str, settings: Settings
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(
            (
                now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
            ).timestamp()
        ),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload,
        settings.jwt_private_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token() -> str:
    return str(uuid.uuid4())


def decode_access_token(
    token: str, settings: Settings
) -> TokenPayload:
    try:
        # Hardcode RS256 to prevent algorithm confusion attacks (RFC 8725)
        payload = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=["RS256"],
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(
            code="invalid_token",
            message="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise AuthenticationError(
            code="invalid_token",
            message="Invalid or expired token",
        )
