from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_429_TOO_MANY_REQUESTS,
)


def build_error_response(
    code: str,
    message: str,
    details: list[str] | None = None,
) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }


class CognifyError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(CognifyError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(
            status_code=HTTP_404_NOT_FOUND,
            code="not_found",
            message=message,
        )


class CognifyValidationError(CognifyError):
    def __init__(self, message: str = "Validation error") -> None:
        super().__init__(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message=message,
        )


class RateLimitError(CognifyError):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            code="rate_limited",
            message=message,
        )


class AuthenticationError(CognifyError):
    def __init__(
        self,
        code: str = "authentication_failed",
        message: str = "Authentication failed",
    ) -> None:
        super().__init__(
            status_code=HTTP_401_UNAUTHORIZED,
            code=code,
            message=message,
        )


class AuthorizationError(CognifyError):
    def __init__(
        self,
        message: str = "Insufficient permissions",
    ) -> None:
        super().__init__(
            status_code=HTTP_403_FORBIDDEN,
            code="insufficient_permissions",
            message=message,
        )
