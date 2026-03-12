from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
)

from src.api.errors import (
    CognifyError,
    CognifyValidationError,
    NotFoundError,
    RateLimitError,
    build_error_response,
)


class TestCognifyErrors:
    def test_cognify_error_base(self) -> None:
        err = CognifyError(
            status_code=400, code="bad_request", message="Bad"
        )
        assert err.status_code == 400
        assert err.code == "bad_request"
        assert err.message == "Bad"

    def test_not_found_error(self) -> None:
        err = NotFoundError(message="Topic not found")
        assert err.status_code == HTTP_404_NOT_FOUND
        assert err.code == "not_found"

    def test_validation_error(self) -> None:
        err = CognifyValidationError(message="Invalid input")
        assert err.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        assert err.code == "validation_error"

    def test_rate_limit_error(self) -> None:
        err = RateLimitError()
        assert err.status_code == HTTP_429_TOO_MANY_REQUESTS
        assert err.code == "rate_limited"

    def test_build_error_response(self) -> None:
        body = build_error_response(
            code="test_error", message="Test", details=["detail1"]
        )
        assert body == {
            "error": {
                "code": "test_error",
                "message": "Test",
                "details": ["detail1"],
            }
        }
