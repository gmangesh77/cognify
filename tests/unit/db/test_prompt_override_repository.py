"""AUTHOR-012 — override repository contract (in-memory twin)."""

from __future__ import annotations

import pytest

from src.db.prompt_override_repository import InMemoryPromptOverrideRepository


@pytest.mark.asyncio
class TestInMemoryPromptOverrideRepository:
    async def test_upsert_then_load_all(self) -> None:
        repo = InMemoryPromptOverrideRepository()
        saved = await repo.upsert(
            "content_outline.user", template="T1", updated_by="user-1"
        )
        assert saved.key == "content_outline.user" and saved.template == "T1"
        assert saved.updated_by == "user-1" and saved.updated_at is not None
        assert await repo.load_all() == {"content_outline.user": "T1"}

    async def test_upsert_twice_keeps_one_row(self) -> None:
        repo = InMemoryPromptOverrideRepository()
        await repo.upsert("k.system", template="A", updated_by="u")
        await repo.upsert("k.system", template="B", updated_by="u2")
        assert await repo.load_all() == {"k.system": "B"}
        got = await repo.get("k.system")
        assert got is not None and got.updated_by == "u2"

    async def test_delete_returns_false_when_absent(self) -> None:
        repo = InMemoryPromptOverrideRepository()
        assert await repo.delete("k.system") is False
        await repo.upsert("k.system", template="A", updated_by="u")
        assert await repo.delete("k.system") is True
        assert await repo.get("k.system") is None
