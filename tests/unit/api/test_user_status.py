"""INFRA-008 — TTL cache in front of the user repository."""

from src.api.auth.repository import InMemoryUserRepository
from src.api.auth.schemas import UserData
from src.api.auth.user_status import UserStatusCache


def _user(user_id: str = "u1", *, is_active: bool = True) -> UserData:
    return UserData(
        id=user_id,
        email=f"{user_id}@example.com",
        password_hash="x",
        role="editor",
        is_active=is_active,
    )


class TestUserStatusCache:
    def test_lookup_reads_through_and_caches(self) -> None:
        repo = InMemoryUserRepository([_user()])
        now = [100.0]
        cache = UserStatusCache(ttl_seconds=30, clock=lambda: now[0])
        assert cache.lookup("u1", repo) is not None
        repo.set_active("u1", False)
        now[0] = 120.0  # still inside the TTL
        cached = cache.lookup("u1", repo)
        assert cached is not None and cached.is_active is True

    def test_lookup_refreshes_after_ttl(self) -> None:
        repo = InMemoryUserRepository([_user()])
        now = [100.0]
        cache = UserStatusCache(ttl_seconds=30, clock=lambda: now[0])
        cache.lookup("u1", repo)
        repo.set_active("u1", False)
        now[0] = 131.0
        refreshed = cache.lookup("u1", repo)
        assert refreshed is not None and refreshed.is_active is False

    def test_lookup_caches_misses(self) -> None:
        repo = InMemoryUserRepository([])
        cache = UserStatusCache(ttl_seconds=30, clock=lambda: 0.0)
        assert cache.lookup("ghost", repo) is None
        repo._users_by_id["ghost"] = _user("ghost")  # noqa: SLF001
        assert cache.lookup("ghost", repo) is None

    def test_invalidate_forces_reload(self) -> None:
        repo = InMemoryUserRepository([_user()])
        cache = UserStatusCache(ttl_seconds=30, clock=lambda: 0.0)
        cache.lookup("u1", repo)
        repo.set_active("u1", False)
        cache.invalidate("u1")
        reloaded = cache.lookup("u1", repo)
        assert reloaded is not None and reloaded.is_active is False


class TestInMemoryUserRepositorySetActive:
    def test_set_active_updates_both_indexes(self) -> None:
        repo = InMemoryUserRepository([_user()])
        updated = repo.set_active("u1", False)
        assert updated is not None and updated.is_active is False
        by_id = repo.get_by_id("u1")
        by_email = repo.get_by_email("u1@example.com")
        assert by_id is not None and by_id.is_active is False
        assert by_email is not None and by_email.is_active is False

    def test_set_active_unknown_returns_none(self) -> None:
        repo = InMemoryUserRepository([])
        assert repo.set_active("nope", False) is None
