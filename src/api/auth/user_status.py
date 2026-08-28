"""INFRA-008 — live user status re-check with a short TTL cache.

``get_current_user`` consults this on every request so a deactivated user
loses access within ``Settings.auth_recheck_ttl_seconds`` without a restart,
while the hot path stays a dict lookup rather than a repository hit.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from src.api.auth.repository import UserRepository
from src.api.auth.schemas import UserData


@dataclass
class _Entry:
    user: UserData | None
    expires_at: float


@dataclass
class UserStatusCache:
    ttl_seconds: float = 30.0
    clock: Callable[[], float] = time.monotonic
    _entries: dict[str, _Entry] = field(default_factory=dict, repr=False)

    def lookup(self, user_id: str, repo: UserRepository) -> UserData | None:
        """Return the repo's view of the user, cached for ``ttl_seconds``.

        Misses (``None``) are cached too so an unknown id cannot hammer the
        repository.
        """
        now = self.clock()
        entry = self._entries.get(user_id)
        if entry is not None and entry.expires_at > now:
            return entry.user
        user = repo.get_by_id(user_id)
        self._entries[user_id] = _Entry(user=user, expires_at=now + self.ttl_seconds)
        return user

    def invalidate(self, user_id: str) -> None:
        self._entries.pop(user_id, None)
