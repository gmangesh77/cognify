"""Unit tests for RBAC authorization dependencies."""

import pytest
import structlog.testing

from src.api.auth.schemas import TokenPayload
from src.api.errors import AuthorizationError


def _make_payload(role: str) -> TokenPayload:
    """Create a TokenPayload with the given role for testing."""
    return TokenPayload(
        sub="user-1",
        role=role,  # type: ignore[arg-type]
        exp=9999999999,
        iat=0,
        jti="test-jti",
    )


class TestRequireRole:
    """Test the require_role dependency factory."""

    async def test_admin_allowed_for_admin_only(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin")
        result = await checker(current_user=_make_payload("admin"))
        assert result.sub == "user-1"
        assert result.role == "admin"

    async def test_editor_denied_for_admin_only(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin")
        with pytest.raises(AuthorizationError) as exc_info:
            await checker(current_user=_make_payload("editor"))
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == "insufficient_permissions"
        assert "editor" in exc_info.value.message

    async def test_viewer_denied_for_admin_only(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin")
        with pytest.raises(AuthorizationError) as exc_info:
            await checker(current_user=_make_payload("viewer"))
        assert exc_info.value.status_code == 403
        assert "viewer" in exc_info.value.message

    async def test_admin_allowed_for_editor_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor")
        result = await checker(current_user=_make_payload("admin"))
        assert result.role == "admin"

    async def test_editor_allowed_for_editor_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor")
        result = await checker(current_user=_make_payload("editor"))
        assert result.role == "editor"

    async def test_viewer_denied_for_editor_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor")
        with pytest.raises(AuthorizationError):
            await checker(current_user=_make_payload("viewer"))

    async def test_admin_allowed_for_viewer_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor", "viewer")
        result = await checker(current_user=_make_payload("admin"))
        assert result.role == "admin"

    async def test_editor_allowed_for_viewer_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor", "viewer")
        result = await checker(current_user=_make_payload("editor"))
        assert result.role == "editor"

    async def test_viewer_allowed_for_viewer_or_above(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role("admin", "editor", "viewer")
        result = await checker(current_user=_make_payload("viewer"))
        assert result.role == "viewer"

    async def test_empty_roles_denies_all(self) -> None:
        from src.api.dependencies import require_role

        checker = require_role()
        with pytest.raises(AuthorizationError):
            await checker(current_user=_make_payload("admin"))

    async def test_denial_logs_warning(self) -> None:
        import src.api.dependencies as deps
        from src.api.dependencies import require_role

        # Reset the module-level logger so capture_logs() can intercept it
        # (structlog caches bound loggers; a prior test may have triggered
        # caching with the production JSON renderer)
        deps.logger = structlog.get_logger()

        checker = require_role("admin")
        with (
            structlog.testing.capture_logs() as logs,
            pytest.raises(AuthorizationError),
        ):
            await checker(current_user=_make_payload("editor"))
        denied = [entry for entry in logs if entry["event"] == "authorization_denied"]
        assert len(denied) == 1
        assert denied[0]["user_id"] == "user-1"
        assert denied[0]["role"] == "editor"
        assert denied[0]["log_level"] == "warning"


class TestConvenienceWrappers:
    """Test pre-built convenience wrappers."""

    async def test_require_admin_allows_admin(self) -> None:
        from src.api.dependencies import require_admin

        result = await require_admin(current_user=_make_payload("admin"))
        assert result.role == "admin"

    async def test_require_admin_denies_editor(self) -> None:
        from src.api.dependencies import require_admin

        with pytest.raises(AuthorizationError):
            await require_admin(current_user=_make_payload("editor"))

    async def test_require_editor_or_above_allows_editor(self) -> None:
        from src.api.dependencies import require_editor_or_above

        result = await require_editor_or_above(current_user=_make_payload("editor"))
        assert result.role == "editor"

    async def test_require_editor_or_above_denies_viewer(self) -> None:
        from src.api.dependencies import require_editor_or_above

        with pytest.raises(AuthorizationError):
            await require_editor_or_above(current_user=_make_payload("viewer"))

    async def test_require_viewer_or_above_allows_viewer(self) -> None:
        from src.api.dependencies import require_viewer_or_above

        result = await require_viewer_or_above(current_user=_make_payload("viewer"))
        assert result.role == "viewer"
